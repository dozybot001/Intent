"""Teams, roles and visibility: who can read, push and manage a project, over the real HTTP API."""

import json
import os
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

from apps.inthub_api.auth import create_account_access_token
from apps.inthub_api.db import connect
from apps.inthub_api.history import push_history
from apps.inthub_api.product_deletion import delete_product_account
from apps.inthub_api.server import make_handler
from apps.inthub_api.tenon import ISSUER, account_for_identity, create_session
from intent_cli.hub.versions import revision_id, validate_project_ref

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://inthub.example"
SESSION = "__Host-inthub_session"


class Tenon:
    def authorization_url(self, redirect_uri, attempt):
        return "https://account.tenon.asia/api/auth/oauth2/authorize"


def request(url, method="GET", payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    sent = dict(headers or {})
    if data is not None:
        sent.setdefault("Content-Type", "application/json")
    try:
        response = urlopen(Request(url, data=data, headers=sent, method=method))
    except HTTPError as exc:
        response = exc
    with response:
        return response.status, json.loads(response.read().decode("utf-8"))


class Person:
    """Someone with a browser session and an access token, or a visitor with neither."""

    def __init__(self, hub, subject=None, name=None):
        self.hub, self.headers = hub, {}
        if subject:
            identity = {"sub": subject, "name": name or subject, "email": f"{subject}@example.com",
                        "platform_role": "user", "expires_at": time.time() + 900}
            self.id = account_for_identity(hub.db, identity)["id"]
            self.headers = {"Origin": SITE, "Cookie": f"{SESSION}={create_session(hub.db, self.id, identity)['token']}"}
            self.token = {"Authorization": "Bearer " + create_account_access_token(hub.db, self.id, ttl_seconds=3600)["token"]}

    def get(self, path, **query):
        return request(self.hub.url + path + ("?" + urlencode(query) if query else ""), headers=self.headers)

    def post(self, path, payload=None):
        return request(self.hub.url + path, "POST", payload if payload is not None else {}, {"Origin": SITE, **self.headers})

    def cli_get(self, path, **query):
        return request(self.hub.url + path + ("?" + urlencode(query) if query else ""), headers=self.token)

    def cli_post(self, path, payload):
        return request(self.hub.url + path, "POST", payload, self.token)

    def link(self, project):
        status, body = self.cli_post("/api/v2/link", {"project_name": project})
        assert status == 200, body
        return body["result"]["project_id"]

    def push(self, project, project_id, snapshot, parent=None):
        return self.cli_post("/api/v2/history", {
            "project_name": project, "project_id": project_id, "parent": parent, "snapshot": snapshot,
            "revision": revision_id(parent, snapshot), "pusher": {"name": "Ana", "email": "ana@private.example"}})


class Hub:
    def __init__(self, tmp_path):
        self.db = str(tmp_path / "inthub.db")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
            self.db, tenon_client_id="id", tenon_client_secret="secret", oauth_client=Tenon(), public_api_base_url=SITE))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"


@pytest.fixture
def hub(tmp_path):
    instance = Hub(tmp_path)
    yield instance
    instance.server.shutdown()
    instance.thread.join()
    instance.server.server_close()


def snapshot(*intents, blocker="none"):
    created = "2026-10-30T00:00:00+00:00"
    author = {"name": "Ana", "email": "ana@private.example"}
    return {
        "intents": [{"id": f"intent-{number:03d}", "object": "intent", "status": "active", "origin": "test", "created_at": created,
                     "what": what, "why": "", "snap_ids": [f"snap-{number:03d}"], "decision_ids": [], "author": author}
                    for number, what in enumerate(intents, 1)],
        "snaps": [{"id": f"snap-{number:03d}", "object": "snap", "status": "active", "origin": "test", "created_at": created,
                   "intent_id": f"intent-{number:03d}", "what": "step", "why": "", "author": author,
                   "checkpoint": {"verified": "yes", "boundary": "b", "next": "n", "blocker": blocker}}
                  for number in range(1, len(intents) + 1)],
        "decisions": [],
    }


def team(admin, slug="acme"):
    status, body = admin.post("/api/v1/teams", {"name": "Acme Inc", "slug": slug})
    assert status == 200, body
    return body["result"]["team"]["id"]


def join(admin, team_id, role, person):
    status, body = admin.post(f"/api/v1/teams/{team_id}/invites", {"role": role})
    assert status == 200, body
    token = body["result"]["path"].split("token=")[1]
    status, body = person.post("/api/v1/invites/accept", {"token": token})
    assert status == 200 and body["result"]["joined"] is True and body["result"]["role"] == role
    return token


@pytest.fixture
def crew(hub):
    admin, member, viewer = Person(hub, "admin"), Person(hub, "member"), Person(hub, "viewer")
    team_id = team(admin)
    join(admin, team_id, "member", member)
    join(admin, team_id, "viewer", viewer)
    return admin, member, viewer, Person(hub, "stranger"), team_id


def test_a_project_ref_is_a_name_or_a_team_and_a_name():
    assert validate_project_ref("app") == "app"
    assert validate_project_ref("acme-co/app 2") == "acme-co/app 2"
    for bad in ("Acme/app", "acme/", "/app", "a/b/c", "-acme/app", "acme-/app", "a" * 40 + "/app", None, 3):
        with pytest.raises(ValueError):
            validate_project_ref(bad)


def test_roles_decide_who_reads_pushes_and_manages_a_team_project(hub, crew):
    admin, member, viewer, stranger, team_id = crew
    pid = member.link("acme/app")
    assert admin.link("acme/app") == pid and viewer.link("acme/app") == pid  # linking an existing project needs no write
    assert stranger.cli_post("/api/v2/link", {"project_name": "acme/app"})[0] == 404
    assert viewer.cli_post("/api/v2/link", {"project_name": "acme/other"})[1]["error"]["code"] == "PERMISSION_DENIED"

    status, body = member.push("acme/app", pid, snapshot("Ship"))
    assert status == 200 and body["result"]["project_name"] == "acme/app"
    first = body["result"]["revision"]
    assert admin.push("acme/app", pid, snapshot("Ship", "Scale"), first)[0] == 200
    status, body = viewer.push("acme/app", pid, snapshot("Ship", "Scale", "Nope"), first)
    assert status == 403 and body["error"]["code"] == "PERMISSION_DENIED"
    # A stranger's push fails as if the project did not exist.
    assert stranger.push("acme/app", pid, snapshot("x"))[1]["error"]["code"] == "NOT_LINKED"

    assert viewer.cli_get("/api/v2/history", project="acme/app")[1]["result"]["project_id"] == pid
    assert viewer.cli_get("/api/v1/projects/" + pid + "/export")[0] == 200
    assert stranger.cli_get("/api/v2/history", project="acme/app", project_id=pid)[1]["result"]["project_id"] is None
    assert stranger.get(f"/api/v1/projects/{pid}/overview")[0] == 404
    assert stranger.get(f"/api/v1/projects/{pid}/export")[0] == 404

    levels = {person: person.get(f"/api/v1/projects/{pid}/overview")[1]["result"]["project"]["permission"]
              for person in (admin, member, viewer)}
    assert levels == {admin: "admin", member: "write", viewer: "read"}
    project = admin.get(f"/api/v1/projects/{pid}/overview")[1]["result"]["project"]
    assert project["full_name"] == "acme/app" and project["owner"] == {"type": "team", "id": team_id, "slug": "acme", "name": "Acme Inc"}

    rename = f"/api/v1/projects/{pid}/rename"
    assert member.post(rename, {"name": "x"})[0] == 403 and viewer.post(rename, {"name": "x"})[0] == 403
    assert stranger.post(rename, {"name": "x"})[0] == 404
    assert member.post(f"/api/v1/projects/{pid}/delete", {"confirm": "app"})[0] == 403
    assert admin.post(rename, {"name": "web"})[1]["result"]["project"]["full_name"] == "acme/web"
    # The history API answers with the handle a clone should store.
    assert member.cli_get("/api/v2/history", project="acme/app", project_id=pid)[1]["result"]["project_name"] == "acme/web"

    listed = {project["id"]: project for project in viewer.get("/api/v1/projects")[1]["result"]["projects"]}
    assert listed[pid]["full_name"] == "acme/web" and listed[pid]["permission"] == "read" and listed[pid]["team"]["slug"] == "acme"
    assert stranger.get("/api/v1/projects")[1]["result"]["projects"] == []


def test_a_team_project_name_is_unique_within_its_team_only(hub, crew):
    admin, member, _, _, team_id = crew
    assert admin.link("app") != admin.link("acme/app")
    other = team(admin, "beta")
    assert admin.link("beta/app") != admin.link("acme/app")
    second = admin.link("acme/second")
    status, body = admin.post(f"/api/v1/projects/{second}/rename", {"name": "app"})
    assert status == 409 and body["error"]["code"] == "NAME_TAKEN"
    assert other != team_id


def test_invite_links_work_once_and_never_for_a_session_they_cannot_see(hub):
    admin, ana, bo = Person(hub, "admin"), Person(hub, "ana"), Person(hub, "bo")
    team_id = team(admin)
    token = join(admin, team_id, "member", ana)
    assert bo.post("/api/v1/invites/accept", {"token": token})[1]["error"]["code"] == "INVITE_INVALID"
    assert bo.get("/api/v1/invites/preview", token=token)[0] == 410

    path = admin.post(f"/api/v1/teams/{team_id}/invites", {"role": "viewer"})[1]["result"]["path"]
    token = path.split("token=")[1]
    assert Person(hub).get("/api/v1/invites/preview", token=token)[0] == 401
    preview = bo.get("/api/v1/invites/preview", token=token)[1]["result"]
    assert preview["team"]["name"] == "Acme Inc" and preview["role"] == "viewer" and preview["invited_by"] == "admin"
    assert preview["already_member"] is False
    # A member opening the link leaves it for the person it was meant for.
    assert ana.post("/api/v1/invites/accept", {"token": token})[1]["result"]["joined"] is False
    # Accepting is a browser action, so a leaked access token cannot join teams.
    assert request(hub.url + "/api/v1/invites/accept", "POST", {"token": token}, {"Origin": SITE, **bo.token})[0] == 401
    assert bo.post("/api/v1/invites/accept", {"token": token})[1]["result"]["joined"] is True

    invite = admin.post(f"/api/v1/teams/{team_id}/invites", {"role": "admin"})[1]["result"]
    token = invite["path"].split("token=")[1]
    pending = admin.get(f"/api/v1/teams/{team_id}")[1]["result"]["invites"]
    assert [row["id"] for row in pending] == [invite["invite"]["id"]] and "token_hash" not in pending[0]
    assert ana.get(f"/api/v1/teams/{team_id}")[1]["result"]["invites"] == []
    assert ana.post(f"/api/v1/teams/{team_id}/invites", {"role": "admin"})[0] == 403
    assert admin.post(f"/api/v1/teams/{team_id}/invites/{invite['invite']['id']}/revoke")[0] == 200
    assert Person(hub, "cy").post("/api/v1/invites/accept", {"token": token})[0] == 410

    token = admin.post(f"/api/v1/teams/{team_id}/invites", {"role": "member"})[1]["result"]["path"].split("token=")[1]
    with connect(hub.db) as conn:
        conn.execute("UPDATE team_invites SET expires_at = ?", ("2020-01-01T00:00:00+00:00",))
    assert Person(hub, "dee").post("/api/v1/invites/accept", {"token": token})[0] == 410
    assert admin.post(f"/api/v1/teams/{team_id}/invites", {"role": "owner"})[0] == 400


def test_a_team_always_keeps_an_admin(hub, crew):
    admin, member, viewer, _, team_id = crew
    role = f"/api/v1/teams/{team_id}/members/{{}}/role"
    remove = f"/api/v1/teams/{team_id}/members/{{}}/remove"
    assert admin.post(role.format(admin.id), {"role": "member"})[1]["error"]["code"] == "LAST_ADMIN"
    assert admin.post(remove.format(admin.id))[1]["error"]["code"] == "LAST_ADMIN"
    assert member.post(role.format(viewer.id), {"role": "admin"})[0] == 403
    assert member.post(remove.format(viewer.id))[0] == 403
    assert admin.post(role.format(member.id), {"role": "admin"})[0] == 200
    assert admin.post(remove.format(admin.id))[0] == 200  # another admin remains, so leaving works
    assert admin.get(f"/api/v1/teams/{team_id}")[0] == 404
    assert viewer.post(remove.format(viewer.id))[0] == 200  # anyone can leave
    details = member.get(f"/api/v1/teams/{team_id}")[1]["result"]
    assert [(row["name"], row["role"], row["you"]) for row in details["members"]] == [("member", "admin", True)]
    assert member.post(role.format("acct_missing"), {"role": "member"})[0] == 404


def test_only_admins_see_member_addresses_and_team_settings(hub, crew):
    admin, member, _, stranger, team_id = crew
    assert all("email" in row for row in admin.get(f"/api/v1/teams/{team_id}")[1]["result"]["members"])
    assert all("email" not in row for row in member.get(f"/api/v1/teams/{team_id}")[1]["result"]["members"])
    assert member.get("/api/v1/teams/acme")[1]["result"]["team"]["id"] == team_id
    assert admin.post("/api/v1/teams", {"name": "\ud800", "slug": "surrogate"})[0] == 400
    assert admin.post("/api/v1/teams", {"name": ["x"], "slug": "list"})[0] == 400
    assert admin.post("/api/v1/invites/accept", {"token": "\ud800"})[0] == 410
    assert admin.post("/api/v1/invites/accept", {"token": ["x"]})[0] == 410
    assert stranger.get(f"/api/v1/teams/{team_id}")[0] == 404
    assert member.post(f"/api/v1/teams/{team_id}", {"name": "New", "slug": "new"})[0] == 403
    assert admin.post(f"/api/v1/teams/{team_id}", {"name": "New", "slug": "bad slug"})[0] == 400
    assert admin.post("/api/v1/teams", {"name": "Other", "slug": "acme"})[1]["error"]["code"] == "NAME_TAKEN"
    other = team(admin, "other")
    assert admin.post(f"/api/v1/teams/{other}", {"name": "Other", "slug": "acme"})[1]["error"]["code"] == "NAME_TAKEN"
    assert [row["slug"] for row in member.get("/api/v1/teams")[1]["result"]["teams"]] == ["acme"]
    row = admin.get("/api/v1/teams")[1]["result"]["teams"][0]
    assert (row["slug"], row["role"], row["members"], row["projects"]) == ("acme", "admin", 3, 0)
    # A browser action: no access tokens, and only from the site itself.
    assert request(hub.url + "/api/v1/teams", "POST", {"name": "X", "slug": "x"}, {"Origin": SITE, **admin.token})[0] == 401
    assert request(hub.url + "/api/v1/teams", "POST", {"name": "X", "slug": "x"}, {**admin.headers, "Origin": "https://evil.example"})[0] == 403


def test_a_private_project_stays_hidden_and_a_public_one_is_read_only_for_visitors(hub):
    owner, stranger, visitor = Person(hub, "owner", "Ana Lee"), Person(hub, "stranger"), Person(hub)
    pid = owner.link("app")
    head = owner.push("app", pid, snapshot("Ship it"))[1]["result"]["revision"]
    remote = f"{pid}__intent-001"
    routes = [f"/api/v1/projects/{pid}/overview", f"/api/v1/projects/{pid}/handoff", f"/api/v1/projects/{pid}/snaps",
              f"/api/v1/projects/{pid}/revisions", f"/api/v1/projects/{pid}/revisions/{head}", f"/api/v1/intents/{remote}",
              f"/api/v1/snaps/{pid}__snap-001", "/api/v1/search?project_id=" + pid + "&q=ship"]
    for route in routes:
        assert visitor.get(route)[0] == 401, route
        assert stranger.get(route)[0] == 404, route
    # A private project and a missing one look the same to a visitor.
    assert visitor.get("/api/v1/projects/proj_missing/overview")[0] == 401

    visibility = f"/api/v1/projects/{pid}/visibility"
    status, body = owner.post(visibility, {"visibility": "public", "confirm": "nope"})
    assert status == 400 and body["error"]["code"] == "CONFIRMATION_MISMATCH"
    assert owner.post(visibility, {"visibility": "shared"})[0] == 400
    assert owner.post(visibility, {"visibility": "public", "confirm": "app"})[1]["result"]["project"]["visibility"] == "public"

    for route in routes:
        for reader in (visitor, stranger):
            status, body = reader.get(route)
            text = json.dumps(body)
            assert status == 200, route
            assert "private.example" not in text and "@example.com" not in text, route
    project = visitor.get(routes[0])[1]["result"]["project"]
    assert project["permission"] == "public" and project["visibility"] == "public"
    assert project["owner"] == {"type": "account", "name": "Ana Lee"}
    revision = visitor.get(routes[3])[1]["result"]["revisions"][0]
    assert revision["pushed_by"] == {"name": "Ana Lee"} and revision["pusher"] == {"name": "Ana"}
    assert visitor.get(routes[0])[1]["result"]["authors"][0]["key"] == "Ana"
    # An address cannot be probed through the author filter.
    assert visitor.get(routes[2], author="ana@private.example")[1]["result"]["total"] == 0
    assert visitor.get(routes[2], author="Ana")[1]["result"]["total"] == 1
    # Members still get what they recorded.
    assert "ana@private.example" in json.dumps(owner.get(routes[0])[1])

    # Reading is all a visitor gets: no list, no pull, no export, no management.
    for path in ("/api/v1/projects", "/api/v1/home", "/api/v1/teams", f"/api/v1/projects/{pid}/export"):
        assert visitor.get(path)[0] == 401, path
    assert visitor.get("/api/v2/history", project="app")[0] == 401
    assert stranger.get(f"/api/v1/projects/{pid}/export")[0] == 404
    # A pull carries author emails, so being able to read the page is not enough.
    assert stranger.cli_get("/api/v2/history", project="app", project_id=pid)[1]["result"]["project_id"] is None
    assert stranger.post(f"/api/v1/projects/{pid}/rename", {"name": "x"})[0] == 404
    assert stranger.post(visibility, {"visibility": "private"})[0] == 404
    assert stranger.push("app", pid, snapshot("x"), head)[0] == 404
    assert visitor.post(f"/api/v1/projects/{pid}/rename", {"name": "x"})[0] == 401
    # A bad token is an error, not a visitor.
    assert request(f"{hub.url}{routes[0]}", headers={"Authorization": "Bearer nope"})[0] == 401

    assert owner.post(visibility, {"visibility": "private"})[0] == 200
    assert visitor.get(routes[0])[0] == 401


def test_visitors_are_rate_limited_but_members_are_not(hub, crew):
    admin = crew[0]
    pid = admin.link("app")
    admin.post(f"/api/v1/projects/{pid}/visibility", {"visibility": "public", "confirm": "app"})
    visitor = Person(hub)
    assert all(visitor.get(f"/api/v1/projects/{pid}/overview")[0] == 200 for _ in range(300))
    assert visitor.get(f"/api/v1/projects/{pid}/overview")[1]["error"]["code"] == "RATE_LIMITED"
    assert admin.get(f"/api/v1/projects/{pid}/overview")[0] == 200


def test_a_project_transfers_to_a_team_and_back_keeping_its_id(hub, crew):
    admin, member, _, stranger, team_id = crew
    pid = admin.link("app")
    head = admin.push("app", pid, snapshot("Ship"))[1]["result"]["revision"]
    transfer = f"/api/v1/projects/{pid}/transfer"
    assert admin.post(transfer, {"team_id": team_id, "confirm": "nope"})[1]["error"]["code"] == "CONFIRMATION_MISMATCH"
    assert member.post(transfer, {"team_id": team_id, "confirm": "app"})[0] == 404
    assert admin.post(transfer, {"team_id": "team_missing", "confirm": "app"})[0] == 404
    assert admin.post(transfer, {"team_id": ["x"], "confirm": "app"})[0] == 404
    other = team(member, "other")  # a team the caller does not administer
    assert admin.post(transfer, {"team_id": other, "confirm": "app"})[1]["error"]["code"] == "TEAM_NOT_FOUND"
    taken = admin.link("acme/app")
    assert admin.post(transfer, {"team_id": team_id, "confirm": "app"})[1]["error"]["code"] == "NAME_TAKEN"
    assert admin.post(f"/api/v1/projects/{taken}/delete", {"confirm": "app"})[0] == 200

    assert admin.post(transfer, {"team_id": team_id, "confirm": "app"})[1]["result"]["project"]["full_name"] == "acme/app"
    # The personal name is free again, and a clone that knows the ID follows the move.
    assert admin.cli_get("/api/v2/history", project="app")[1]["result"]["project_id"] is None
    followed = admin.cli_get("/api/v2/history", project="app", project_id=pid)[1]["result"]
    assert followed["project_id"] == pid and followed["project_name"] == "acme/app" and followed["revision"] == head
    assert member.cli_get("/api/v2/history", project="acme/app")[1]["result"]["project_id"] == pid
    assert member.push("acme/app", pid, snapshot("Ship", "Scale"), head)[0] == 200

    assert member.post(transfer, {"team_id": None, "confirm": "app"})[0] == 403
    assert admin.post(transfer, {"team_id": None, "confirm": "app"})[1]["result"]["project"]["full_name"] == "app"
    assert member.get(f"/api/v1/projects/{pid}/overview")[0] == 404
    assert admin.cli_get("/api/v2/history", project="app")[1]["result"]["project_id"] == pid
    assert stranger.get(f"/api/v1/projects/{pid}/overview")[0] == 404


def test_the_home_view_counts_blocked_intents_for_each_project(hub, crew):
    admin, member, viewer, _, _ = crew
    mine = admin.link("mine")
    admin.push("mine", mine, snapshot("One", "Two", blocker="Waiting for keys"))
    shared = member.link("acme/app")
    member.push("acme/app", shared, snapshot("Three", blocker="无"))
    empty = admin.link("acme/empty")
    rows = {row["id"]: row for row in admin.get("/api/v1/home")[1]["result"]["projects"]}
    assert (rows[mine]["active_intents"], rows[mine]["blocked_intents"], rows[mine]["total_snaps"]) == (2, 2, 2)
    assert (rows[shared]["active_intents"], rows[shared]["blocked_intents"]) == (1, 0)
    assert rows[empty]["active_intents"] == 0 and "snapshot_json" not in rows[shared]
    assert {row["id"] for row in viewer.get("/api/v1/home")[1]["result"]["projects"]} == {shared, empty}


def test_deleting_a_team_removes_its_projects_after_typing_its_url(hub, crew):
    admin, member, _, _, team_id = crew
    pid = member.link("acme/app")
    member.push("acme/app", pid, snapshot("Ship"))
    keep = admin.link("app")
    assert member.post(f"/api/v1/teams/{team_id}/delete", {"confirm": "acme"})[0] == 403
    assert admin.post(f"/api/v1/teams/{team_id}/delete", {"confirm": "Acme"})[1]["error"]["code"] == "CONFIRMATION_MISMATCH"
    assert admin.post(f"/api/v1/teams/{team_id}/delete", {"confirm": "acme"})[0] == 200
    assert [row["id"] for row in admin.get("/api/v1/projects")[1]["result"]["projects"]] == [keep]
    with connect(hub.db) as conn:
        assert conn.execute("SELECT count(*) AS n FROM semantic_versions WHERE project_id = ?", (pid,)).fetchone()["n"] == 0
        assert conn.execute("SELECT count(*) AS n FROM team_members").fetchone()["n"] == 0


def proof(subject):
    return {"issuer": ISSUER, "sub": subject, "productId": "inthub", "operationId": "6f0f3b5a-8f1d-4b7e-9c3a-2d1e0f9a8b7c"}


def test_deleting_an_account_hands_its_teams_on(hub, crew):
    admin, member, viewer, _, team_id = crew
    solo = team(admin, "solo")
    pid = admin.link("solo/app")
    admin.push("solo/app", pid, snapshot("Ship"))
    delete_product_account(hub.db, proof("admin"))
    # The longest-standing member takes over; a team with nobody left goes with its projects.
    roles = {row["name"]: row["role"] for row in member.get(f"/api/v1/teams/{team_id}")[1]["result"]["members"]}
    assert roles == {"member": "admin", "viewer": "viewer"}
    with connect(hub.db) as conn:
        assert conn.execute("SELECT id FROM teams WHERE id = ?", (solo,)).fetchone() is None
        assert conn.execute("SELECT id FROM projects WHERE id = ?", (pid,)).fetchone() is None


def test_a_viewer_becomes_admin_only_when_nobody_else_can(hub):
    admin, viewer = Person(hub, "admin"), Person(hub, "viewer")
    team_id = team(admin)
    join(admin, team_id, "viewer", viewer)
    delete_product_account(hub.db, proof("admin"))
    assert viewer.get(f"/api/v1/teams/{team_id}")[1]["result"]["role"] == "admin"


def itt(cwd, token, *args):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT)]), INTHUB_TOKEN=token,
               INTENT_CONFIG_HOME=str(cwd.parent / "config"), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    result = subprocess.run([sys.executable, "-m", "intent_cli", *args], cwd=cwd, env=env, capture_output=True, text=True)
    return json.loads(result.stdout)


def test_the_cli_pushes_a_team_project_and_a_clone_follows_a_transfer(tmp_path, hub, crew):
    admin, member, viewer, stranger, team_id = crew
    token = member.token["Authorization"].split(" ")[1]
    root = tmp_path / "team-clone"
    root.mkdir()
    assert itt(root, token, "init")["ok"]
    assert itt(root, token, "intent", "create", "Ship together", "--why", "test")["ok"]
    assert itt(root, token, "remote", "add", "origin", hub.url, "--project", "acme/app")["ok"]
    pushed = itt(root, token, "push")
    assert pushed["ok"] and pushed["result"]["project_name"] == "acme/app"
    assert itt(root, token, "status")["result"]["project_name"] == "acme/app"

    # A viewer can pull the team's project into a fresh clone, but not push to it.
    clone = tmp_path / "viewer-clone"
    clone.mkdir()
    viewer_token = viewer.token["Authorization"].split(" ")[1]
    assert itt(clone, viewer_token, "init")["ok"]
    assert itt(clone, viewer_token, "remote", "add", "origin", hub.url, "--project", "acme/app")["ok"]
    assert itt(clone, viewer_token, "pull")["ok"]
    assert itt(clone, viewer_token, "intent", "create", "Mine", "--why", "test")["ok"]
    assert itt(clone, viewer_token, "push")["error"]["code"] == "PERMISSION_DENIED"

    assert itt(root, token, "remote", "add", "origin", hub.url, "--project", "Bad/app")["error"]["code"] == "INVALID_INPUT"

    # A personal clone follows its project into a team.
    solo = tmp_path / "solo"
    solo.mkdir()
    admin_token = admin.token["Authorization"].split(" ")[1]
    assert itt(solo, admin_token, "init")["ok"]
    assert itt(solo, admin_token, "intent", "create", "Move me", "--why", "test")["ok"]
    assert itt(solo, admin_token, "remote", "add", "origin", hub.url, "--project", "moving")["ok"]
    pid = itt(solo, admin_token, "push")["result"]["project_id"]
    assert admin.post(f"/api/v1/projects/{pid}/transfer", {"team_id": team_id, "confirm": "moving"})[0] == 200
    assert itt(solo, admin_token, "intent", "create", "Still mine", "--why", "test")["ok"]
    followed = itt(solo, admin_token, "push")["result"]
    assert followed["project_name"] == "acme/moving" and followed["renamed_from"] == "moving"
    assert json.loads((solo / ".intent" / "hub.json").read_text())["project_name"] == "acme/moving"

    # So does a clone of a team whose URL changed.
    assert admin.post(f"/api/v1/teams/{team_id}", {"name": "Acme Inc", "slug": "acme-labs"})[0] == 200
    assert itt(solo, admin_token, "intent", "create", "One more", "--why", "test")["ok"]
    followed = itt(solo, admin_token, "push")["result"]
    assert followed["project_name"] == "acme-labs/moving" and followed["renamed_from"] == "acme/moving"


def test_a_local_hub_has_no_teams_and_every_project_stays_open(tmp_path):
    db = str(tmp_path / "local.db")
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(db))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        origin = {"Origin": url}
        assert request(f"{url}/api/v2/link", "POST", {"project_name": "acme/app"})[0] == 404
        pid = request(f"{url}/api/v2/link", "POST", {"project_name": "app"})[1]["result"]["project_id"]
        assert request(f"{url}/api/v1/projects/{pid}/overview")[1]["result"]["project"]["permission"] == "admin"
        assert request(f"{url}/api/v1/projects")[1]["result"]["projects"][0]["permission"] == "admin"
        assert request(f"{url}/api/v1/home")[1]["result"]["projects"][0]["active_intents"] == 0
        assert request(f"{url}/api/v1/teams", "POST", {"name": "X", "slug": "x"}, origin)[0] == 404
        assert request(f"{url}/api/v1/teams")[0] == 404
        assert request(f"{url}/api/v1/projects/{pid}/visibility", "POST", {"visibility": "public", "confirm": "app"}, origin)[0] == 404
        assert request(f"{url}/api/v1/projects/{pid}/transfer", "POST", {"confirm": "app"}, origin)[0] == 404
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_push_history_reports_the_team_handle_directly(hub, crew):
    # The same path the HTTP API takes, for callers such as the PostgreSQL tests.
    member = crew[1]
    pid = member.link("acme/app")
    data = snapshot("Ship")
    result = push_history(hub.db, {"project_name": "acme/app", "project_id": pid, "parent": None,
                                   "revision": revision_id(None, data), "snapshot": data}, member.id)
    assert result["project_name"] == "acme/app"
