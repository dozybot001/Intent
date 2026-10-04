"""Observable shared-history behavior across independent clients and writers."""

import copy
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.inthub_api.auth import upsert_github_account
from apps.inthub_api.common import APIError
from apps.inthub_api.db import connect
from apps.inthub_api.history import link_history, push_history, read_history
from apps.inthub_api.queries import project_overview, get_intent_detail, list_projects
from apps.inthub_api.server import build_server
from intent_cli.hub.snapshots import snapshot_sha256
from intent_cli.hub.versions import revision_id
from intent_cli.commands import shared

ROOT = Path(__file__).resolve().parents[1]


def run(directory, *args):
    env = dict(os.environ, PYTHONPATH=f"{ROOT / 'src'}{os.pathsep}{ROOT}",
               INTENT_CONFIG_HOME=str(directory.parent / "config"),
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    env.pop("INTHUB_TOKEN", None)
    result = subprocess.run([sys.executable, "-m", "intent_cli", *args], cwd=directory,
                            env=env, text=True, capture_output=True)
    payload = json.loads(result.stdout)
    assert result.returncode == (0 if payload["ok"] else 1), result.stderr
    return payload


@pytest.fixture
def clients(tmp_path):
    db = str(tmp_path / "hub.db")
    server = build_server("127.0.0.1", 0, db)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    directories = [tmp_path / "laptop", tmp_path / "desktop"]
    for directory in directories:
        directory.mkdir()
        assert run(directory, "init")["ok"]
        assert run(directory, "remote", "add", "origin", url, "--project", "demo")["ok"]
    try:
        yield (*directories, db, url)
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def seed(source):
    assert run(source, "intent", "create", "共享语义目标")["ok"]
    assert run(source, "snap", "create", "Verified: ready; Boundary: test; Next: proceed; Blocker: none",
               "--intent", "intent-001")["ok"]
    pushed = run(source, "push")
    assert pushed["ok"], pushed
    return pushed["result"]


def bytes_of(directory):
    return {str(path.relative_to(directory)): path.read_bytes()
            for path in (directory / ".intent").rglob("*.json")}


def test_two_clients_share_project_without_git_or_workspaces(clients):
    source, target, db, _ = clients
    first = seed(source)
    assert run(source, "status")["result"]["state"] == "up_to_date"
    assert run(target, "status")["result"]["state"] == "behind"
    assert run(target, "pull")["result"]["changed"]
    assert run(target, "push")["result"]["changed"] is False
    assert run(target, "snap", "create", "第二台机器已验证", "--intent", "intent-001")["ok"]
    second = run(target, "push")
    assert second["ok"] and second["result"]["parent"] == first["revision"]
    assert run(source, "status")["result"]["state"] == "behind"
    assert run(source, "pull")["result"]["counts"]["snaps"] == 2
    before = bytes_of(source)
    assert run(source, "pull")["result"]["changed"] is False
    assert bytes_of(source) == before
    with connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM projects").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM semantic_versions").fetchone()[0] == 2
    overview = project_overview(db, first["project_id"])
    assert overview["history"]["revision"] == second["result"]["revision"]
    assert len(overview["active_intents"]) == 1
    assert "workspaces" not in overview
    detail = get_intent_detail(db, first["project_id"] + "__intent-001")
    assert len(detail["snaps"]) == 2


def test_noop_preview_empty_and_offline_do_not_create_remote_history(clients):
    source, _, db, _ = clients
    assert run(source, "status", "--local")["ok"]
    assert run(source, "push")["result"]["changed"] is False
    assert list_projects(db)["projects"] == []
    assert run(source, "intent", "create", "offline first")["ok"]
    assert run(source, "push", "--dry-run")["result"]["changed"]
    assert list_projects(db)["projects"] == []


def test_maintenance_is_local_metadata_not_shared_history(clients):
    source, target, db, _ = clients
    seed(source)
    assert run(target, "maintenance", "off")["ok"]
    local_state = target / ".intent" / "maintenance.json"
    before = local_state.read_bytes()
    assert run(target, "pull")["ok"]
    assert local_state.read_bytes() == before
    assert not run(target, "maintenance", "status")["result"]["enabled"]
    assert run(source, "maintenance", "off")["ok"]
    assert run(source, "status")["result"]["state"] == "up_to_date"
    assert run(source, "push")["result"]["changed"] is False
    assert set(read_history(db, "demo")["snapshot"]) == {"intents", "snaps", "decisions"}


@pytest.mark.parametrize("option", ["--workspace", "--source-repo"])
def test_removed_workspace_options_are_structured_input_errors(clients, option):
    source, _, _, _ = clients
    result = run(source, "pull", option, "old")
    assert result["error"]["code"] == "INVALID_INPUT"


def test_divergence_preserves_both_snapshots_and_does_not_duplicate_versions(clients):
    source, target, db, _ = clients
    seed(source)
    assert run(target, "pull")["ok"]
    assert run(target, "snap", "create", "local result", "--intent", "intent-001")["ok"]
    before = bytes_of(target)
    assert run(target, "pull")["result"]["changed"] is False
    assert bytes_of(target) == before
    assert run(source, "snap", "create", "other result", "--intent", "intent-001")["ok"]
    assert run(source, "push")["ok"]
    assert run(target, "status")["result"]["state"] == "diverged"
    assert run(target, "push")["error"]["code"] == "NON_FAST_FORWARD"
    assert run(target, "pull")["error"]["code"] == "HISTORY_DIVERGED"
    assert bytes_of(target) == before
    remote = read_history(db, "demo")
    assert remote["snapshot"]["snaps"][-1]["what"] == "other result"


def test_lost_push_response_converges_without_second_version(clients):
    source, _, db, _ = clients
    seed(source)
    config_path = source / ".intent/hub.json"
    baseline = config_path.read_bytes()
    assert run(source, "snap", "create", "accepted but response lost", "--intent", "intent-001")["ok"]
    assert run(source, "push")["ok"]
    config_path.write_bytes(baseline)  # Simulate losing only the final client acknowledgement.
    assert run(source, "push")["result"]["changed"] is False
    assert run(source, "status")["result"]["state"] == "up_to_date"
    with connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM semantic_versions").fetchone()[0] == 2


def test_parallel_push_has_one_winner_and_retries_are_idempotent(clients):
    source, _, db, _ = clients
    first = seed(source)
    remote = read_history(db, "demo")
    barrier = threading.Barrier(2)
    def push(label):
        snapshot = copy.deepcopy(remote["snapshot"])
        snap = copy.deepcopy(snapshot["snaps"][0])
        snap.update(id="snap-002", what=label)
        snapshot["snaps"].append(snap)
        snapshot["intents"][0]["snap_ids"].append("snap-002")
        payload = {"project_name": "demo", "project_id": first["project_id"],
                   "parent": first["revision"], "snapshot": snapshot,
                   "revision": revision_id(first["revision"], snapshot)}
        barrier.wait()
        try:
            return push_history(db, payload)
        except APIError as exc:
            return {"error": exc.code}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(push, ["first", "second"]))
    assert sum(result.get("changed") is True for result in results) == 1
    assert sum(result.get("error") == "NON_FAST_FORWARD" for result in results) == 1
    with connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM semantic_versions").fetchone()[0] == 2


def test_account_isolation_and_invalid_revision(clients):
    _, _, db, _ = clients
    first = upsert_github_account(db, {"id": 1, "login": "first"})
    second = upsert_github_account(db, {"id": 2, "login": "second"})
    linked = link_history(db, "private", first["id"])
    assert read_history(db, "private", second["id"])["project_id"] is None
    snapshot = {"intents": [], "snaps": [], "decisions": []}
    with pytest.raises(APIError, match="Revision"):
        push_history(db, {"project_name": "private", "project_id": linked["project_id"],
                          "parent": None, "revision": "0" * 64, "snapshot": snapshot}, first["id"])


def test_project_names_are_safe_url_independent_identities(clients):
    _, _, db, _ = clients
    name = "项目 Demo"
    with ThreadPoolExecutor(max_workers=2) as pool:
        links = list(pool.map(lambda _: link_history(db, name), range(2)))
    assert links[0] == links[1]
    assert shared._project_id(links[0]["project_id"])
    assert read_history(db, name)["project_id"] == links[0]["project_id"]
    with pytest.raises(APIError):
        link_history(db, "../project")


def test_server_preserves_history_when_object_is_rewritten(clients):
    source, _, db, _ = clients
    first = seed(source)
    snapshot = copy.deepcopy(read_history(db, "demo")["snapshot"])
    snapshot["snaps"][0]["what"] = "rewrite"
    with pytest.raises(APIError) as failure:
        push_history(db, {"project_name": "demo", "project_id": first["project_id"],
                          "parent": first["revision"], "revision": revision_id(first["revision"], snapshot),
                          "snapshot": snapshot})
    assert failure.value.code == "HISTORY_CONFLICT"
    assert read_history(db, "demo")["revision"] == first["revision"]


@pytest.mark.parametrize("result", [
    {"format_version": 2, "project_name": "demo"},
    {"format_version": 2, "project_name": "demo", "project_id": "bad/id", "revision": None,
     "parent": None, "snapshot": None, "snapshot_sha256": None},
])
def test_malformed_remote_never_escapes_json_contract(clients, monkeypatch, capsys, result):
    source, _, _, url = clients
    monkeypatch.chdir(source)
    monkeypatch.setattr(shared, "http_json", lambda *a, **k: result)
    with pytest.raises(SystemExit):
        shared.cmd_status(SimpleNamespace(local=False, project=None, api_base_url=url, token=None))
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "INVALID_REMOTE_SNAPSHOT"


def test_pull_rechecks_local_state_after_download(clients, monkeypatch, capsys):
    source, target, db, url = clients
    seed(source)
    monkeypatch.chdir(target)
    remote = read_history(db, "demo")
    def download(*args, **kwargs):
        assert run(target, "intent", "create", "local concurrent goal")["ok"]
        return remote
    monkeypatch.setattr(shared, "http_json", download)
    with pytest.raises(SystemExit):
        shared.cmd_pull(SimpleNamespace(project=None, api_base_url=url, token=None, dry_run=False,
                                        ))
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "LOCAL_STATE_CHANGED"
    assert json.loads((target / ".intent/intents/intent-001.json").read_text())["what"] == "local concurrent goal"
