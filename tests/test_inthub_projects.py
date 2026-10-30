"""Project management on IntHub: rename, delete and export, and clones following a rename."""

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
from apps.inthub_api.history import link_history, read_history
from apps.inthub_api.server import build_server, make_handler
from apps.inthub_api.tenon import account_for_identity, create_session

ROOT = Path(__file__).resolve().parents[1]
SESSION = "__Host-inthub_session"


def itt(cwd, *args):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
               INTENT_CONFIG_HOME=str(cwd.parent / "config"), GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    env.pop("INTHUB_TOKEN", None)
    result = subprocess.run([sys.executable, "-m", "intent_cli", *args], cwd=cwd, env=env, capture_output=True, text=True)
    payload = json.loads(result.stdout)
    assert result.returncode == (0 if payload["ok"] else 1), result.stderr
    return payload


def call(url, method="GET", payload=None, headers=None, origin=True):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    sent = dict(headers or {})
    if data is not None:
        sent.setdefault("Content-Type", "application/json")
    if origin and method == "POST":
        sent.setdefault("Origin", url.split("/api/")[0])
    try:
        response = urlopen(Request(url, data=data, headers=sent, method=method))
    except HTTPError as exc:
        response = exc
    with response:
        return response.status, json.loads(response.read().decode("utf-8"))


def serve(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def stop(server, thread):
    server.shutdown()
    thread.join()
    server.server_close()


@pytest.fixture
def hub(tmp_path):
    db = str(tmp_path / "hub.db")
    server = build_server("127.0.0.1", 0, db)
    thread = serve(server)
    try:
        yield db, f"http://127.0.0.1:{server.server_port}"
    finally:
        stop(server, thread)


@pytest.fixture
def pushed(tmp_path, hub):
    db, url = hub
    root = tmp_path / "project"
    root.mkdir()
    assert itt(root, "init")["ok"]
    assert itt(root, "intent", "create", "Support mobile payments", "--why", "test")["ok"]
    assert itt(root, "remote", "add", "origin", url, "--project", "payments")["ok"]
    project_id = itt(root, "push")["result"]["project_id"]
    return db, url, root, project_id


def hub_config(root):
    return json.loads((root / ".intent" / "hub.json").read_text(encoding="utf-8"))


def test_a_clone_follows_a_rename_made_on_inthub(tmp_path, pushed):
    db, url, root, project_id = pushed
    status, body = call(f"{url}/api/v1/projects/{project_id}/rename", "POST", {"name": "checkout"})
    assert status == 200 and body["result"]["project"] == {
        "id": project_id, "name": "checkout", "created_at": body["result"]["project"]["created_at"]}

    assert itt(root, "status")["result"]["renamed_from"] == "payments"
    assert hub_config(root)["project_name"] == "payments"  # status never writes
    assert itt(root, "intent", "create", "Add Apple Pay", "--why", "test")["ok"]
    pushed_again = itt(root, "push")["result"]
    assert pushed_again["project_name"] == "checkout" and pushed_again["renamed_from"] == "payments"
    assert pushed_again["project_id"] == project_id
    assert hub_config(root)["project_name"] == "checkout"
    assert "renamed_from" not in itt(root, "push")["result"]

    # The old name no longer resolves, so a client without the ID cannot create a duplicate silently.
    assert read_history(db, "payments")["project_id"] is None
    assert read_history(db, "payments", project_id=project_id)["project_name"] == "checkout"


def test_an_older_clone_reports_the_rename_instead_of_creating_a_project(tmp_path, pushed):
    db, url, root, project_id = pushed
    call(f"{url}/api/v1/projects/{project_id}/rename", "POST", {"name": "checkout"})
    # itt 7.2 asked by name only.
    status, body = call(f"{url}/api/v2/history?{urlencode({'project': 'payments'})}")
    assert status == 200 and body["result"]["project_id"] is None
    # Naming the project explicitly sends no ID, which is what itt 7.2 does on every push.
    assert itt(root, "push", "--project", "payments")["error"]["code"] == "REMOTE_CHANGED"


def test_rename_validates_the_name_and_keeps_names_unique(pushed):
    db, url, root, project_id = pushed
    link_history(db, "billing")
    rename = f"{url}/api/v1/projects/{project_id}/rename"
    status, body = call(rename, "POST", {"name": "billing"})
    assert status == 409 and body["error"]["code"] == "NAME_TAKEN"
    assert call(rename, "POST", {"name": "a/b"})[1]["error"]["code"] == "INVALID_INPUT"
    assert call(rename, "POST", {})[1]["error"]["code"] == "INVALID_INPUT"
    assert call(rename, "POST", {"name": "payments"})[0] == 200  # unchanged is fine
    assert call(f"{url}/api/v1/projects/proj_missing/rename", "POST", {"name": "x"})[0] == 404
    # A browser action: same origin and JSON only.
    assert call(rename, "POST", {"name": "x"}, headers={"Origin": "https://evil.example"})[0] == 403
    assert call(rename, "POST", {"name": "x"}, origin=False)[0] == 403
    assert call(rename, "POST", {"name": "x"}, headers={"Content-Type": "text/plain"})[0] == 415


def test_a_new_local_project_can_take_a_renamed_projects_old_name(pushed):
    db, url, root, project_id = pushed
    call(f"{url}/api/v1/projects/{project_id}/rename", "POST", {"name": "checkout"})
    again = link_history(db, "payments")
    assert again["project_id"] != project_id
    assert link_history(db, "payments") == again
    assert call(f"{url}/api/v1/projects/{project_id}/rename", "POST", {"name": "payments"})[0] == 409


def test_delete_needs_the_exact_name_and_removes_only_that_project(tmp_path, pushed):
    db, url, root, project_id = pushed
    other = link_history(db, "billing")["project_id"]
    delete = f"{url}/api/v1/projects/{project_id}/delete"
    assert call(delete, "POST", {"confirm": "Payments"})[1]["error"]["code"] == "CONFIRMATION_MISMATCH"
    assert call(delete, "POST", {"confirm": "payments"}) == (200, {"ok": True, "result": {"deleted": True, "id": project_id}})
    projects = call(f"{url}/api/v1/projects")[1]["result"]["projects"]
    assert [project["id"] for project in projects] == [other]
    assert call(f"{url}/api/v1/projects/{project_id}/overview")[0] == 404
    assert call(delete, "POST", {"confirm": "payments"})[0] == 404
    # The clone keeps its history and must relink explicitly.
    refused = itt(root, "push")["error"]
    assert refused["code"] == "REMOTE_CHANGED" and "itt hub link" in refused["suggested_fix"]
    assert itt(root, "hub", "link")["ok"]
    republished = itt(root, "push")["result"]
    assert republished["changed"] is True and republished["project_id"] != other


def test_export_holds_the_current_snapshot_and_the_revision_chain(pushed):
    db, url, root, project_id = pushed
    assert itt(root, "intent", "create", "Add Apple Pay", "--why", "test")["ok"]
    head = itt(root, "push")["result"]
    status, body = call(f"{url}/api/v1/projects/{project_id}/export")
    exported = body["result"]
    assert status == 200 and exported["format"] == "inthub-export" and exported["format_version"] == 1
    assert exported["project"]["name"] == "payments"
    assert exported["head"]["revision"] == head["revision"]
    assert [intent["what"] for intent in exported["snapshot"]["intents"]] == ["Support mobile payments", "Add Apple Pay"]
    chain = exported["revisions"]
    assert len(chain) == 2 and chain[0]["revision"] == head["revision"]
    assert chain[0]["parent"] == chain[1]["revision"] and chain[1]["parent"] is None
    assert call(f"{url}/api/v1/projects/proj_missing/export")[0] == 404


def test_on_a_tenon_hub_only_the_owners_browser_session_manages_a_project(tmp_path):
    db = str(tmp_path / "inthub.db")
    site = "https://inthub.example"

    def signed_in(subject):
        identity = {"sub": subject, "name": subject, "platform_role": "user", "expires_at": time.time() + 900}
        account = account_for_identity(db, identity)
        return account, {"Origin": site, "Cookie": f"{SESSION}={create_session(db, account['id'], identity)['token']}"}

    owner, owner_cookie = signed_in("tenon-owner")
    _, other_cookie = signed_in("tenon-other")
    token = create_account_access_token(db, owner["id"], ttl_seconds=3600)["token"]
    project_id = link_history(db, "payments", owner["id"])["project_id"]

    class Tenon:
        def authorization_url(self, redirect_uri, attempt):
            return "https://account.tenon.asia/api/auth/oauth2/authorize"

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
        db, tenon_client_id="id", tenon_client_secret="secret", oauth_client=Tenon(), public_api_base_url=site))
    thread = serve(server)
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        rename = f"{url}/api/v1/projects/{project_id}/rename"
        # An access token reads history but cannot rename or delete.
        assert call(rename, "POST", {"name": "checkout"}, headers={"Origin": site, "Authorization": f"Bearer {token}"})[0] == 401
        assert call(rename, "POST", {"name": "checkout"}, headers=other_cookie)[0] == 404
        assert call(f"{url}/api/v1/projects/{project_id}/delete", "POST", {"confirm": "payments"}, headers=other_cookie)[0] == 404
        assert call(f"{url}/api/v1/projects/{project_id}/export", headers=other_cookie)[0] == 404
        assert call(rename, "POST", {"name": "checkout"}, headers=owner_cookie)[0] == 200
        assert call(f"{url}/api/v1/projects/{project_id}/export",
                    headers={"Authorization": f"Bearer {token}"})[1]["result"]["project"]["name"] == "checkout"
        status, body = call(f"{url}/api/v1/projects/{project_id}/delete", "POST", {"confirm": "checkout"}, headers=owner_cookie)
        assert status == 200 and body["result"]["deleted"] is True
    finally:
        stop(server, thread)
