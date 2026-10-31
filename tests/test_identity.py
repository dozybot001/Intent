"""Who recorded what: authors and commits on objects, pushers and history on IntHub."""

import json
import os
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from apps.inthub_api.auth import create_account_access_token
from apps.inthub_api.db import connect
from apps.inthub_api.history import link_history
from apps.inthub_api.queries import project_overview
from apps.inthub_api.revisions import LIST_LIMIT, project_revisions, revision_detail
from apps.inthub_api.server import build_server, make_handler
from apps.inthub_api.tenon import account_for_identity
from intent_cli import identity
from intent_cli.hub.changes import semantic_changes, summarize
from intent_cli.hub.snapshots import SnapshotError, require_fast_forward, validate_snapshot

ROOT = Path(__file__).resolve().parents[1]
ANA = {"name": "Ana Lee", "email": "ana@example.com"}


def itt(cwd, *args, **env):
    environ = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
                   INTENT_CONFIG_HOME=str(cwd.parent / "config"), **env)
    result = subprocess.run([sys.executable, "-m", "intent_cli", *args], cwd=cwd, env=environ, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    assert result.returncode == (0 if payload["ok"] else 1), result.stderr
    return payload


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def stored(project, kind, object_id):
    return json.loads((project / ".intent" / kind / f"{object_id}.json").read_text(encoding="utf-8"))


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.name", ANA["name"])
    git(root, "config", "user.email", ANA["email"])
    (root / "app.py").write_text("print('v1')\n", encoding="utf-8")
    git(root, "add", "app.py")
    git(root, "commit", "-q", "-m", "First")
    assert itt(root, "init")["ok"]
    return root


@pytest.fixture
def plain(tmp_path):
    root = tmp_path / "plain"
    root.mkdir()
    assert itt(root, "init")["ok"]
    return root


def test_objects_record_gits_identity_and_the_agent_stays_separate(repo):
    created = itt(repo, "intent", "create", "Goal", "--why", "test", ITT_ORIGIN="claude-code")["result"]
    assert created["author"] == ANA and created["origin"] == "claude-code"
    assert stored(repo, "intents", "intent-001")["author"] == ANA
    assert itt(repo, "snap", "create", "Checked")["result"]["author"] == ANA
    assert itt(repo, "decision", "create", "Rule", "--why", "test")["result"]["author"] == ANA


def test_the_environment_overrides_git_like_git_does(repo):
    assert identity.author({"ITT_AUTHOR_NAME": "A", "ITT_AUTHOR_EMAIL": "a@x", "GIT_AUTHOR_NAME": "B"}) == {"name": "A", "email": "a@x"}
    created = itt(repo, "intent", "create", "Goal", "--why", "test", GIT_AUTHOR_NAME="Bot", GIT_AUTHOR_EMAIL="bot@example.com")
    assert created["result"]["author"] == {"name": "Bot", "email": "bot@example.com"}


def test_without_an_identity_recording_continues_and_commands_say_so(plain):
    created = itt(plain, "intent", "create", "Goal", "--why", "test")
    assert created["ok"] and "author" not in created["result"]
    assert "author" not in stored(plain, "intents", "intent-001")
    for command in (("status",), ("doctor",)):
        assert identity.MISSING in itt(plain, *command)["warnings"]
    fresh = plain.parent / "fresh"
    fresh.mkdir()
    initialized = itt(fresh, "init")
    assert initialized["result"]["author"] == {} and identity.MISSING in initialized["warnings"]


def test_a_snap_records_the_commit_and_whether_work_was_uncommitted(repo):
    assert itt(repo, "intent", "create", "Goal", "--why", "test")["ok"]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    assert itt(repo, "snap", "create", "Clean")["result"]["git"] == {"commit": head}
    (repo / "app.py").write_text("print('v2')\n", encoding="utf-8")
    assert itt(repo, "snap", "create", "Dirty")["result"]["git"] == {"commit": head, "dirty": True}


def test_outside_git_a_snap_has_no_commit(plain):
    assert itt(plain, "intent", "create", "Goal", "--why", "test")["ok"]
    assert "git" not in itt(plain, "snap", "create", "Checked")["result"]


@pytest.mark.parametrize(("remote", "expected"), [
    ("https://github.com/acme/app.git", "https://github.com/acme/app"),
    ("https://user:secret@github.com/acme/app.git", "https://github.com/acme/app"),
    ("git@github.com:acme/app.git", "https://github.com/acme/app"),
    ("ssh://git@gitee.com/acme/app.git", "https://gitee.com/acme/app"),
    ("https://gitlab.com/acme/tools/app", "https://gitlab.com/acme/tools/app"),
    ("https://git.internal.example/acme/app.git", None),
    ("git@inthub-gitee:acme/app.git", None),
])
def test_only_known_hosts_become_a_repository_link_and_credentials_never_do(repo, monkeypatch, remote, expected):
    git(repo, "remote", "add", "origin", remote)
    monkeypatch.chdir(repo)
    assert identity.repository() == expected


def snapshot_with(**fields):
    intent = {"id": "intent-001", "object": "intent", "status": "active", "created_at": "2026-10-30T00:00:00+00:00",
              "origin": "", "what": "Goal", "why": "", "snap_ids": ["snap-001"], "decision_ids": []}
    snap = {"id": "snap-001", "object": "snap", "created_at": "2026-10-30T00:00:01+00:00", "origin": "",
            "what": "Done", "why": "", "intent_id": "intent-001", **fields}
    return {"intents": [intent], "snaps": [snap], "decisions": []}


@pytest.mark.parametrize("fields", [
    {"author": "Ana"}, {"author": {}}, {"author": {"name": 1}},
    {"git": "abc"}, {"git": {"commit": "xyz"}}, {"git": {"commit": "a" * 40, "dirty": "yes"}},
])
def test_invalid_identity_fields_are_rejected(fields):
    with pytest.raises(SnapshotError):
        validate_snapshot(snapshot_with(**fields))


def test_valid_identity_fields_are_accepted_and_cannot_be_rewritten():
    before = snapshot_with(author=ANA, git={"commit": "a" * 40, "dirty": True})
    validate_snapshot(before)
    rewritten = snapshot_with(author={"name": "Someone else"}, git={"commit": "a" * 40, "dirty": True})
    with pytest.raises(SnapshotError):
        require_fast_forward(before, rewritten)


def test_semantic_changes_list_additions_status_and_relations_but_not_link_growth():
    before = snapshot_with()
    before["intents"].append({**before["intents"][0], "id": "intent-002", "snap_ids": []})
    after = json.loads(json.dumps(before))
    goal, other = after["intents"]
    other["status"], other["reason"] = "cancelled", "Dropped"
    goal["relations"] = [{"type": "depends_on", "intent": "intent-002", "created_at": "now"}]
    goal["snap_ids"].append("snap-002")
    after["snaps"].append({**after["snaps"][0], "id": "snap-002"})
    changes = semantic_changes(before, after)
    assert [obj["id"] for obj in changes["snaps"]["added"]] == ["snap-002"]
    assert changes["intents"]["changed"][0]["changes"] == [
        {"field": "relation", "action": "added", "type": "depends_on", "intent": "intent-002"}]
    assert changes["intents"]["changed"][1]["changes"] == [
        {"field": "status", "from": "active", "to": "cancelled", "reason": "Dropped"}]
    assert summarize(changes)["snaps_added"] == 1 and summarize(changes)["intents_changed"] == 2
    withdrawn = json.loads(json.dumps(after))
    withdrawn["intents"][0]["relations"][0]["removed_at"] = "later"
    assert semantic_changes(after, withdrawn)["intents"]["changed"][0]["changes"] == [
        {"field": "relation", "action": "removed", "type": "depends_on", "intent": "intent-002"}]


@pytest.fixture
def hub(tmp_path):
    db = str(tmp_path / "hub.db")
    server = build_server("127.0.0.1", 0, db)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield db, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_a_push_records_the_declared_pusher_and_the_history_page_reads_it(repo, hub):
    db, url = hub
    git(repo, "remote", "add", "origin", "git@github.com:acme/app.git")
    assert itt(repo, "intent", "create", "Goal", "--why", "test")["ok"]
    assert itt(repo, "snap", "create", "First check")["ok"]
    assert itt(repo, "remote", "add", "origin", url, "--project", "app")["ok"]
    first = itt(repo, "push")["result"]
    assert itt(repo, "intent", "done", "intent-001")["ok"]
    second = itt(repo, "push")["result"]
    project_id = second["project_id"]

    assert project_overview(db, project_id)["project"]["repository_url"] == "https://github.com/acme/app"
    page = project_revisions(db, project_id, limit=1)
    assert page["total"] == 3 and page["has_more"] is True
    newest = page["revisions"][0]
    assert newest["revision"] == second["revision"] and newest["parent"] == first["revision"]
    assert newest["pusher"] == ANA and newest["pushed_by"] is None
    assert newest["summary"]["intents_changed"] == 1 and newest["summary"]["snaps_added"] == 0

    oldest = project_revisions(db, project_id)["revisions"][-1]
    detail = revision_detail(db, project_id, oldest["revision"])
    assert [obj["what"] for obj in detail["changes"]["intents"]["added"]] == ["Goal"]
    snap = revision_detail(db, project_id, first["revision"])["changes"]["snaps"]["added"][0]
    assert snap["author"] == ANA and snap["intent_id"] == "intent-001" and len(snap["git"]["commit"]) == 40
    changed = revision_detail(db, project_id, second["revision"])["changes"]["intents"]["changed"][0]
    assert changed["object"]["id"] == "intent-001"
    assert changed["changes"] == [{"field": "status", "from": "active", "to": "done"}]

    with urlopen(f"{url}/api/v1/projects/{project_id}/revisions") as response:
        assert json.load(response)["result"]["total"] == 3
    with pytest.raises(HTTPError) as missing:
        urlopen(f"{url}/api/v1/projects/{project_id}/revisions/nope")
    assert missing.value.code == 404


def test_the_timeline_lists_and_filters_by_author(repo, hub):
    db, url = hub
    assert itt(repo, "intent", "create", "Goal", "--why", "test")["ok"]
    assert itt(repo, "snap", "create", "Mine")["ok"]
    assert itt(repo, "snap", "create", "Also mine")["ok"]
    assert itt(repo, "snap", "create", "Theirs", ITT_AUTHOR_NAME="Bo", ITT_AUTHOR_EMAIL="bo@example.com")["ok"]
    assert itt(repo, "remote", "add", "origin", url, "--project", "app")["ok"]
    project_id = itt(repo, "push")["result"]["project_id"]
    overview = project_overview(db, project_id)
    assert overview["authors"] == [{"key": ANA["email"], "name": ANA["name"], "snaps": 2},
                                   {"key": "bo@example.com", "name": "Bo", "snaps": 1}]
    with urlopen(f"{url}/api/v1/projects/{project_id}/snaps?author=bo%40example.com") as response:
        page = json.load(response)["result"]
    assert [snap["what"] for snap in page["snaps"]] == ["Theirs"] and page["total"] == 1


def test_a_long_revision_is_cut_but_its_counts_stay_exact(hub):
    db, _ = hub
    intents = [{"id": f"intent-{number:03d}", "object": "intent", "status": "active", "created_at": "2026-10-30T00:00:00+00:00",
                "origin": "", "what": str(number), "why": "", "snap_ids": [], "decision_ids": []} for number in range(1, LIST_LIMIT + 6)]
    from apps.inthub_api.history import push_history
    from intent_cli.hub.versions import revision_id
    project_id = link_history(db, "big")["project_id"]
    snapshot = {"intents": intents, "snaps": [], "decisions": []}
    revision = revision_id(None, snapshot)
    push_history(db, {"project_name": "big", "project_id": project_id, "parent": None, "revision": revision, "snapshot": snapshot})
    detail = revision_detail(db, project_id, revision)
    assert len(detail["changes"]["intents"]["added"]) == LIST_LIMIT and detail["changes"]["intents"]["truncated"] is True
    assert detail["summary"]["intents_added"] == LIST_LIMIT + 5


def signed_in_hub(db):
    """A Tenon hub for one account with a verified email, and that account's access token."""
    account = account_for_identity(db, {"sub": "tenon-ana", "name": "Ana", "email": "ANA@example.com",
                                        "platform_role": "user", "expires_at": time.time() + 900})
    assert account["email"] == "ANA@example.com"
    token = create_account_access_token(db, account["id"], ttl_seconds=3600)["token"]

    class Tenon:
        def authorization_url(self, redirect_uri, attempt):
            return "https://account.tenon.asia/api/auth/oauth2/authorize"

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
        db, tenon_client_id="id", tenon_client_secret="secret", oauth_client=Tenon(), public_api_base_url="https://inthub.example"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, token, account


def test_an_object_pushed_by_its_authors_account_is_verified(repo, tmp_path):
    db = str(tmp_path / "tenon.db")
    server, token, account = signed_in_hub(db)
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        environment = {"INTHUB_TOKEN": token}
        assert itt(repo, "intent", "create", "Mine", "--why", "test")["ok"]
        assert itt(repo, "intent", "create", "Theirs", "--why", "test", ITT_AUTHOR_EMAIL="other@example.com")["ok"]
        assert itt(repo, "remote", "add", "origin", url, "--project", "app")["ok"]
        pushed = itt(repo, "push", **environment)["result"]
        overview = project_overview(db, pushed["project_id"], account_id=account["id"])
        verified = {intent["what"]: intent.get("verified") for intent in overview["active_intents"]}
        assert verified == {"Mine": True, "Theirs": None}

        revisions = project_revisions(db, pushed["project_id"], account_id=account["id"])["revisions"]
        assert revisions[0]["pushed_by"]["name"] == "Ana"
        added = [intent for revision in revisions for intent in revision_detail(
            db, pushed["project_id"], revision["revision"], account["id"])["changes"]["intents"]["added"]]
        assert {intent["what"]: intent.get("verified") for intent in added} == {"Mine": True, "Theirs": None}

        from apps.inthub_api.projects import delete_project
        delete_project(db, pushed["project_id"], "app", account["id"])
        with connect(db) as conn:
            assert conn.execute("SELECT count(*) AS n FROM verified_objects").fetchone()["n"] == 0
    finally:
        server.shutdown()
        server.server_close()


def test_the_stored_snapshot_never_carries_the_verified_flag(repo, tmp_path):
    db = str(tmp_path / "tenon.db")
    server, token, account = signed_in_hub(db)
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        assert itt(repo, "intent", "create", "Mine", "--why", "test")["ok"]
        assert itt(repo, "remote", "add", "origin", url, "--project", "app")["ok"]
        assert itt(repo, "push", INTHUB_TOKEN=token)["ok"]
        request = Request(f"{url}/api/v2/history?project=app", headers={"Authorization": f"Bearer {token}"})
        with urlopen(request) as response:
            assert "verified" not in json.load(response)["result"]["snapshot"]["intents"][0]
        assert itt(repo, "pull", INTHUB_TOKEN=token)["ok"]
    finally:
        server.shutdown()
        server.server_close()
