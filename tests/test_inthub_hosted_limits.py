"""What keeps a hosted hub safe to open: quotas, rate limits, suspension, takedown and the check before going public."""

import json
import time

import pytest

from apps.inthub_api import admin, db, limits
from apps.inthub_api.db import connect
from apps.inthub_api.secret_scan import find_secrets
from apps.inthub_api.tenon import account_for_identity
from apps.inthub_api.common import APIError
from tests.test_inthub_teams import Hub, Person, request, snapshot, team


@pytest.fixture
def hub(tmp_path):
    instance = Hub(tmp_path)
    yield instance
    instance.server.shutdown()
    instance.thread.join()
    instance.server.server_close()


def test_an_owner_can_keep_a_bounded_number_of_projects(hub, monkeypatch):
    monkeypatch.setattr(limits, "PROJECTS_PER_OWNER", 2)
    ana = Person(hub, "ana")
    assert ana.link("one") and ana.link("two")
    status, body = ana.cli_post("/api/v2/link", {"project_name": "three"})
    assert status == 403 and body["error"]["code"] == "QUOTA_EXCEEDED"
    # Naming a project that already exists is not a new one.
    assert ana.link("one")
    # A team counts on its own, and a transfer needs room at the other end.
    team_id = team(ana)
    assert ana.link("acme/app") and ana.link("acme/web")
    assert ana.cli_post("/api/v2/link", {"project_name": "acme/third"})[0] == 403
    moved = ana.post(f"/api/v1/projects/{ana.link('one')}/transfer", {"team_id": team_id, "confirm": "one"})
    assert moved[0] == 403 and moved[1]["error"]["code"] == "QUOTA_EXCEEDED"


def test_storage_counts_every_revision_and_frees_with_the_project(hub, monkeypatch):
    ana = Person(hub, "ana")
    pid = ana.link("app")
    first = ana.push("app", pid, snapshot("Ship"))
    assert first[0] == 200
    usage = ana.get("/api/v1/usage")[1]["result"]["owners"][0]
    assert usage["type"] == "account" and usage["projects"] == 1 and usage["storage_bytes"] > 100
    assert usage["projects_limit"] == limits.PROJECTS_PER_OWNER and usage["storage_limit"] == limits.STORAGE_PER_OWNER

    monkeypatch.setattr(limits, "STORAGE_PER_OWNER", usage["storage_bytes"] + 10)
    refused = ana.push("app", pid, snapshot("Ship", "Scale"), first[1]["result"]["revision"])
    assert refused[0] == 403 and refused[1]["error"]["code"] == "QUOTA_EXCEEDED"
    assert ana.post(f"/api/v1/projects/{pid}/delete", {"confirm": "app"})[0] == 200
    assert ana.get("/api/v1/usage")[1]["result"]["owners"][0]["storage_bytes"] == 0


def test_usage_lists_the_viewers_teams(hub):
    ana, ben = Person(hub, "ana"), Person(hub, "ben")
    team(ana)
    owners = ana.get("/api/v1/usage")[1]["result"]["owners"]
    assert [owner["type"] for owner in owners] == ["account", "team"] and owners[1]["name"] == "Acme Inc"
    assert [owner["type"] for owner in ben.get("/api/v1/usage")[1]["result"]["owners"]] == ["account"]
    assert request(hub.url + "/api/v1/usage")[0] == 401


def test_storage_is_counted_in_bytes_by_pushes_and_by_the_migration(hub):
    ana = Person(hub, "ana")
    pid = ana.link("app")
    ana.push("app", pid, snapshot("把语义历史推送到托管服务"))
    stored = "SELECT stored_bytes FROM projects WHERE id = ?"
    with connect(hub.db) as conn:
        pushed = conn.execute(stored, (pid,)).fetchone()["stored_bytes"]
        text = conn.execute("SELECT snapshot_json FROM semantic_versions WHERE project_id = ?", (pid,)).fetchone()["snapshot_json"]
        # As a database at schema 7 would look: nothing counted yet.
        conn.execute("UPDATE projects SET stored_bytes = 0")
        conn.execute("DELETE FROM schema_migrations WHERE version = 8")
    assert pushed == len(text.encode("utf-8")) > len(text)
    db.migrate_target(hub.db, require_backward_compatible=True)
    with connect(hub.db) as conn:
        assert conn.execute(stored, (pid,)).fetchone()["stored_bytes"] == pushed


def test_one_address_cannot_flood_the_api_or_tenon(hub):
    # Only the limiter's size differs from production; the path is the real one.
    statuses = [request(hub.url + "/api/auth/tenon/delete/execute", "POST", {})[0] for _ in range(31)]
    assert statuses[-1] == 429 and 429 not in statuses[:30]


def test_a_suspended_account_has_no_way_in_until_restored(hub):
    ana = Person(hub, "ana")
    pid = ana.link("app")
    ana.push("app", pid, snapshot("Ship"))
    assert ana.post(f"/api/v1/projects/{pid}/visibility", {"visibility": "public", "confirm": "app"})[0] == 200

    result = admin.suspend(hub.db, ana.id)
    assert result == {"suspended": ana.id, "projects_taken_down": 1}
    assert ana.get("/api/v1/auth/me")[0] == 401
    assert ana.cli_get("/api/v1/projects")[0] == 401
    assert request(hub.url + f"/api/v1/projects/{pid}/overview")[0] in (401, 404)
    identity = {"sub": "ana", "name": "ana", "email": "ana@example.com", "platform_role": "user"}
    with pytest.raises(APIError) as refused:
        account_for_identity(hub.db, identity)
    assert refused.value.code == "ACCOUNT_SUSPENDED"

    assert admin.restore(hub.db, ana.id) == {"restored": ana.id}
    assert ana.cli_get("/api/v1/projects")[0] == 200, "tokens work again; the project stays down"
    assert account_for_identity(hub.db, identity)["id"] == ana.id


def test_a_takedown_keeps_a_project_private_until_reinstated(hub):
    ana = Person(hub, "ana")
    pid = ana.link("app")
    ana.push("app", pid, snapshot("Ship"))
    assert ana.post(f"/api/v1/projects/{pid}/visibility", {"visibility": "public", "confirm": "app"})[0] == 200
    assert request(hub.url + f"/api/v1/projects/{pid}/overview")[0] == 200

    assert admin.takedown(hub.db, pid) == {"taken_down": pid}
    assert request(hub.url + f"/api/v1/projects/{pid}/overview")[0] in (401, 404)
    assert ana.get(f"/api/v1/projects/{pid}/overview")[0] == 200, "its members keep their work"
    status, body = ana.post(f"/api/v1/projects/{pid}/visibility", {"visibility": "public", "confirm": "app"})
    assert status == 403 and body["error"]["code"] == "PROJECT_SUSPENDED"
    admin.reinstate(hub.db, pid)
    assert ana.post(f"/api/v1/projects/{pid}/visibility", {"visibility": "public", "confirm": "app"})[0] == 200


def test_operator_commands_find_people_and_refuse_unknown_ids(hub, capsys):
    ana = Person(hub, "ana")
    pid = ana.link("app")
    found = admin.find(hub.db, "ana@example.com")
    assert found["accounts"][0]["id"] == ana.id and found["accounts"][0]["projects"][0]["id"] == pid
    assert admin.find(hub.db, pid)["projects"][0]["repo_id"] == "app"
    with pytest.raises(SystemExit):
        admin.suspend(hub.db, "acct_missing")
    with pytest.raises(SystemExit):
        admin.takedown(hub.db, "proj_missing")
    admin.main(["find", ana.id, "--database-url", hub.db])
    assert json.loads(capsys.readouterr().out)["accounts"][0]["id"] == ana.id


@pytest.mark.parametrize("text, kind", [
    ("key ghp_" + "a1" * 18, "GitHub token"),
    ("-----BEGIN OPENSSH PRIVATE KEY-----", "private key"),
    ("export KEY=sk-ant-" + "b2" * 12, "API key"),
    ("AKIA" + "ABCDEFGHIJKLMNOP", "AWS access key"),
    ("postgresql://user:hunter2@db.example/app", "password in a URL"),
    ("ith_pat_" + "c3" * 16, "IntHub token"),
])
def test_credentials_are_found_by_kind(text, kind):
    found = find_secrets(snapshot(text))
    assert found[0]["id"] == "intent-001" and kind in found[0]["kinds"]
    assert text not in json.dumps(found)


def test_a_credential_after_a_line_break_is_still_found():
    assert find_secrets(snapshot("Key:\nghp_" + "a1" * 18))[0]["kinds"] == ["GitHub token"]
    assert find_secrets(snapshot("Key:\tAKIA" + "ABCDEFGHIJKLMNOP"))[0]["kinds"] == ["AWS access key"]


@pytest.mark.parametrize("fragment", ["a.", "sk-", "ghp_", "x://", "a:", "-----BEGIN ", "xoxb-", "ith_pat_"])
def test_a_crafted_field_cannot_stall_the_scan(fragment):
    started = time.monotonic()
    find_secrets(snapshot(fragment * (2_000_000 // len(fragment))))
    assert time.monotonic() - started < 2


def test_ordinary_prose_is_not_a_secret():
    assert find_secrets(snapshot("Rotate the sk- prefix docs", "https://example.com/a:b", "ghp_ tokens expire")) == []


def test_going_public_stops_on_a_likely_credential_until_acknowledged(hub):
    ana = Person(hub, "ana")
    pid = ana.link("app")
    ana.push("app", pid, snapshot("Deploy with ghp_" + "a1" * 18))
    status, body = ana.post(f"/api/v1/projects/{pid}/visibility", {"visibility": "public", "confirm": "app"})
    assert status == 409 and body["error"]["code"] == "POSSIBLE_SECRETS"
    assert body["error"]["details"]["objects"] == [{"id": "intent-001", "kinds": ["GitHub token"]}]
    assert request(hub.url + f"/api/v1/projects/{pid}/overview")[0] in (401, 404)
    status, _ = ana.post(f"/api/v1/projects/{pid}/visibility", {"visibility": "public", "confirm": "app", "acknowledge_secrets": True})
    assert status == 200
