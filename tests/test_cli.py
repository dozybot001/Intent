"""Tests for Intent CLI — covers all 20 commands, state machines, and error codes."""

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

import pytest

from apps.inthub_api.server import make_handler as make_inthub_api_handler
from apps.inthub_web.server import make_handler as make_inthub_web_handler

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATHS = [str(REPO_ROOT), str(REPO_ROOT / "src")]


@pytest.fixture
def workspace(tmp_path):
    """Create a git repo with .intent/ initialized."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=tmp_path, capture_output=True, check=True,
    )
    result = _run(tmp_path, "init")
    assert result["ok"] is True
    return tmp_path


@pytest.fixture
def inthub_server(tmp_path):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_inthub_api_handler(str(tmp_path / "inthub.db")),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


@pytest.fixture
def inthub_web_server(inthub_server):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_inthub_web_handler(api_base_url=inthub_server),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def _run(cwd, *args):
    """Run itt command and return parsed JSON."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        SOURCE_PATHS + ([existing] if existing else [])
    )
    r = subprocess.run(
        [sys.executable, "-m", "intent_cli", *args],
        cwd=cwd, capture_output=True, text=True, env=env,
    )
    return json.loads(r.stdout)


def _add_github_remote(cwd, remote_url="git@github.com:example/demo.git"):
    subprocess.run(
        ["git", "remote", "add", "origin", remote_url],
        cwd=cwd, capture_output=True, check=True,
    )


def _get_json(url):
    with urlopen(url) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _expected_cli_version():
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    in_project = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[project]":
            in_project = True
            continue
        if in_project and stripped.startswith("["):
            break
        if in_project:
            match = re.match(r'version\s*=\s*"([^"]+)"', stripped)
            if match:
                return match.group(1)
    raise AssertionError("Could not find project.version in pyproject.toml")


# ---------------------------------------------------------------------------
# Global commands
# ---------------------------------------------------------------------------

class TestGlobal:
    def test_version(self, workspace):
        r = _run(workspace, "version")
        assert r["ok"] is True
        assert r["result"]["version"] == _expected_cli_version()

    def test_init_already_exists(self, workspace):
        r = _run(workspace, "init")
        assert r["ok"] is False
        assert r["error"]["code"] == "ALREADY_EXISTS"

    def test_init_not_git(self, tmp_path):
        r = _run(tmp_path, "init")
        assert r["ok"] is False
        assert r["error"]["code"] == "GIT_STATE_INVALID"

    def test_inspect_empty(self, workspace):
        r = _run(workspace, "inspect")
        assert r["ok"] is True
        assert r["active_intents"] == []
        assert r["active_decisions"] == []
        assert r["recent_snaps"] == []

    def test_not_initialized(self, tmp_path):
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=tmp_path, capture_output=True, check=True,
        )
        r = _run(tmp_path, "inspect")
        assert r["ok"] is False
        assert r["error"]["code"] == "NOT_INITIALIZED"

    def test_doctor_healthy(self, workspace):
        r = _run(workspace, "doctor")
        assert r["ok"] is True
        assert r["result"]["healthy"] is True
        assert r["result"]["issue_count"] == 0


class TestHub:
    def test_login_and_link(self, workspace, inthub_server):
        _add_github_remote(workspace)
        r = _run(workspace, "hub", "login", "--api-base-url", inthub_server)
        assert r["ok"] is True
        r = _run(workspace, "hub", "link", "--project-name", "Demo Project")
        assert r["ok"] is True
        hub_config = json.loads((workspace / ".intent" / "hub.json").read_text())
        assert hub_config["api_base_url"] == inthub_server
        assert hub_config["project_id"].startswith("proj_")
        assert hub_config["workspace_id"].startswith("wks_")
        assert hub_config["repo_binding"]["repo_id"] == "example/demo"

    def test_link_requires_github_remote(self, workspace, inthub_server):
        _add_github_remote(workspace, "git@example.com:foo/bar.git")
        _run(workspace, "hub", "login", "--api-base-url", inthub_server)
        r = _run(workspace, "hub", "link")
        assert r["ok"] is False
        assert r["error"]["code"] == "PROVIDER_UNSUPPORTED"

    def test_sync_requires_link(self, workspace, inthub_server):
        _add_github_remote(workspace)
        _run(workspace, "hub", "login", "--api-base-url", inthub_server)
        r = _run(workspace, "hub", "sync")
        assert r["ok"] is False
        assert r["error"]["code"] == "NOT_LINKED"

    def test_sync_dry_run(self, workspace, inthub_server):
        _add_github_remote(workspace)
        _run(workspace, "hub", "login", "--api-base-url", inthub_server)
        _run(workspace, "hub", "link", "--project-name", "Demo Project")
        _run(workspace, "intent", "create", "Goal", "--query", "q")
        r = _run(workspace, "hub", "sync", "--dry-run")
        assert r["ok"] is True
        assert r["result"]["dry_run"] is True
        assert r["result"]["payload"]["snapshot"]["intents"][0]["id"] == "intent-001"

    def test_sync_updates_overview_and_handoff(self, workspace, inthub_server):
        _add_github_remote(workspace)
        _run(workspace, "hub", "login", "--api-base-url", inthub_server)
        _run(workspace, "hub", "link", "--project-name", "Demo Project")
        _run(workspace, "intent", "create", "Goal", "--query", "why?")
        _run(workspace, "decision", "create", "Rule", "--rationale", "r")
        _run(workspace, "snap", "create", "Did X", "--intent", "intent-001",
             "--summary", "details")
        r = _run(workspace, "hub", "sync")
        assert r["ok"] is True

        hub_config = json.loads((workspace / ".intent" / "hub.json").read_text())
        project_id = hub_config["project_id"]
        overview = _get_json(f"{inthub_server}/api/v1/projects/{project_id}/overview")
        assert overview["ok"] is True
        assert len(overview["result"]["active_intents"]) == 1
        assert overview["result"]["active_intents"][0]["id"] == "intent-001"
        assert len(overview["result"]["recent_snaps"]) == 1
        snap_remote_id = overview["result"]["recent_snaps"][0]["remote_id"]

        handoff = _get_json(f"{inthub_server}/api/v1/projects/{project_id}/handoff")
        assert handoff["ok"] is True
        assert handoff["result"]["intents"][0]["latest_snap"]["id"] == "snap-001"

        projects = _get_json(f"{inthub_server}/api/v1/projects")
        assert projects["ok"] is True
        assert projects["result"]["projects"][0]["id"] == project_id

        search = _get_json(f"{inthub_server}/api/v1/search?project_id={project_id}&q=Goal")
        assert search["ok"] is True
        assert search["result"]["matches"][0]["id"] == "intent-001"

        snap_detail = _get_json(f"{inthub_server}/api/v1/snaps/{snap_remote_id}")
        assert snap_detail["ok"] is True
        assert snap_detail["result"]["snap"]["id"] == "snap-001"

    def test_read_only_web_shell_serves_config(self, inthub_web_server, inthub_server):
        config = _get_json(f"{inthub_web_server}/config.json")
        assert config["apiBaseUrl"] == inthub_server
        html = urlopen(f"{inthub_web_server}/").read().decode("utf-8")
        assert "Read-only IntHub" in html
        assert "Semantic history, shared without re-explaining it." in html
        assert 'id="setup-guide"' in html
        deep_link = urlopen(f"{inthub_web_server}/projects/demo").read().decode("utf-8")
        assert "Read-only IntHub" in deep_link
        js = urlopen(f"{inthub_web_server}/app.js").read().decode("utf-8")
        assert "Open raw payload" in js
        assert "Linked decisions" in js
        assert "itt hub sync" in js


# ---------------------------------------------------------------------------
# Intent commands
# ---------------------------------------------------------------------------

class TestIntent:
    def test_create(self, workspace):
        r = _run(workspace, "intent", "create", "Fix bug", "--query", "why crash?")
        assert r["ok"] is True
        assert r["result"]["id"] == "intent-001"
        assert r["result"]["status"] == "active"
        assert r["result"]["source_query"] == "why crash?"

    def test_create_auto_attaches_decisions(self, workspace):
        _run(workspace, "intent", "create", "Goal A", "--query", "q")
        _run(workspace, "decision", "create", "Rule 1", "--rationale", "r")
        r = _run(workspace, "intent", "create", "Goal B", "--query", "q")
        assert "decision-001" in r["result"]["decision_ids"]

    def test_list(self, workspace):
        _run(workspace, "intent", "create", "A", "--query", "q")
        _run(workspace, "intent", "create", "B", "--query", "q")
        r = _run(workspace, "intent", "list")
        assert len(r["result"]) == 2

    def test_list_filter_status(self, workspace):
        _run(workspace, "intent", "create", "A", "--query", "q")
        _run(workspace, "intent", "create", "B", "--query", "q")
        _run(workspace, "intent", "suspend", "intent-001")
        r = _run(workspace, "intent", "list", "--status", "active")
        assert len(r["result"]) == 1
        assert r["result"][0]["id"] == "intent-002"

    def test_list_filter_decision(self, workspace):
        _run(workspace, "intent", "create", "A", "--query", "q")
        _run(workspace, "intent", "create", "B", "--query", "q")
        _run(workspace, "decision", "create", "Rule", "--rationale", "r")
        _run(workspace, "decision", "deprecate", "decision-001")
        _run(workspace, "decision", "create", "Rule 2", "--rationale", "r")
        r = _run(workspace, "intent", "list", "--decision", "decision-001")
        assert len(r["result"]) == 2

    def test_list_invalid_status(self, workspace):
        r = _run(workspace, "intent", "list", "--status", "paused")
        assert r["ok"] is False
        assert r["error"]["code"] == "INVALID_INPUT"

    def test_show(self, workspace):
        _run(workspace, "intent", "create", "A", "--query", "q")
        r = _run(workspace, "intent", "show", "intent-001")
        assert r["result"]["title"] == "A"

    def test_show_not_found(self, workspace):
        r = _run(workspace, "intent", "show", "intent-999")
        assert r["error"]["code"] == "OBJECT_NOT_FOUND"

    def test_suspend_activate(self, workspace):
        _run(workspace, "intent", "create", "A", "--query", "q")
        r = _run(workspace, "intent", "suspend", "intent-001")
        assert r["result"]["status"] == "suspend"
        r = _run(workspace, "intent", "activate", "intent-001")
        assert r["result"]["status"] == "active"

    def test_activate_catches_up_decisions(self, workspace):
        _run(workspace, "intent", "create", "A", "--query", "q")
        _run(workspace, "intent", "suspend", "intent-001")
        _run(workspace, "decision", "create", "New rule", "--rationale", "r")
        r = _run(workspace, "intent", "activate", "intent-001")
        assert "decision-001" in r["result"]["decision_ids"]

    def test_done(self, workspace):
        _run(workspace, "intent", "create", "A", "--query", "q")
        r = _run(workspace, "intent", "done", "intent-001")
        assert r["result"]["status"] == "done"

    def test_done_is_terminal(self, workspace):
        _run(workspace, "intent", "create", "A", "--query", "q")
        _run(workspace, "intent", "done", "intent-001")
        r = _run(workspace, "intent", "activate", "intent-001")
        assert r["error"]["code"] == "STATE_CONFLICT"

    def test_suspend_only_active(self, workspace):
        _run(workspace, "intent", "create", "A", "--query", "q")
        _run(workspace, "intent", "done", "intent-001")
        r = _run(workspace, "intent", "suspend", "intent-001")
        assert r["error"]["code"] == "STATE_CONFLICT"


# ---------------------------------------------------------------------------
# Snap commands
# ---------------------------------------------------------------------------

class TestSnap:
    def test_create(self, workspace):
        _run(workspace, "intent", "create", "Goal", "--query", "q")
        r = _run(workspace, "snap", "create", "Did X", "--intent", "intent-001",
                 "--summary", "details")
        assert r["ok"] is True
        assert r["result"]["id"] == "snap-001"
        assert r["result"]["intent_id"] == "intent-001"

    def test_create_updates_intent_snap_ids(self, workspace):
        _run(workspace, "intent", "create", "Goal", "--query", "q")
        _run(workspace, "snap", "create", "S1", "--intent", "intent-001")
        _run(workspace, "snap", "create", "S2", "--intent", "intent-001")
        r = _run(workspace, "intent", "show", "intent-001")
        assert r["result"]["snap_ids"] == ["snap-001", "snap-002"]

    def test_create_requires_active_intent(self, workspace):
        _run(workspace, "intent", "create", "Goal", "--query", "q")
        _run(workspace, "intent", "done", "intent-001")
        r = _run(workspace, "snap", "create", "S", "--intent", "intent-001")
        assert r["error"]["code"] == "STATE_CONFLICT"

    def test_create_intent_not_found(self, workspace):
        r = _run(workspace, "snap", "create", "S", "--intent", "intent-999")
        assert r["error"]["code"] == "OBJECT_NOT_FOUND"

    def test_list(self, workspace):
        _run(workspace, "intent", "create", "Goal", "--query", "q")
        _run(workspace, "snap", "create", "S1", "--intent", "intent-001")
        _run(workspace, "snap", "create", "S2", "--intent", "intent-001")
        r = _run(workspace, "snap", "list")
        assert len(r["result"]) == 2

    def test_list_filter_intent(self, workspace):
        _run(workspace, "intent", "create", "A", "--query", "q")
        _run(workspace, "intent", "create", "B", "--query", "q")
        _run(workspace, "snap", "create", "S1", "--intent", "intent-001")
        _run(workspace, "snap", "create", "S2", "--intent", "intent-002")
        r = _run(workspace, "snap", "list", "--intent", "intent-002")
        assert len(r["result"]) == 1
        assert r["result"][0]["id"] == "snap-002"

    def test_list_invalid_status(self, workspace):
        r = _run(workspace, "snap", "list", "--status", "done")
        assert r["ok"] is False
        assert r["error"]["code"] == "INVALID_INPUT"

    def test_feedback(self, workspace):
        _run(workspace, "intent", "create", "Goal", "--query", "q")
        _run(workspace, "snap", "create", "S", "--intent", "intent-001")
        r = _run(workspace, "snap", "feedback", "snap-001", "looks good")
        assert r["result"]["feedback"] == "looks good"

    def test_feedback_overwrites(self, workspace):
        _run(workspace, "intent", "create", "Goal", "--query", "q")
        _run(workspace, "snap", "create", "S", "--intent", "intent-001")
        _run(workspace, "snap", "feedback", "snap-001", "first")
        r = _run(workspace, "snap", "feedback", "snap-001", "second")
        assert r["result"]["feedback"] == "second"

    def test_revert(self, workspace):
        _run(workspace, "intent", "create", "Goal", "--query", "q")
        _run(workspace, "snap", "create", "S", "--intent", "intent-001")
        r = _run(workspace, "snap", "revert", "snap-001")
        assert r["result"]["status"] == "reverted"

    def test_revert_is_terminal(self, workspace):
        _run(workspace, "intent", "create", "Goal", "--query", "q")
        _run(workspace, "snap", "create", "S", "--intent", "intent-001")
        _run(workspace, "snap", "revert", "snap-001")
        r = _run(workspace, "snap", "revert", "snap-001")
        assert r["error"]["code"] == "STATE_CONFLICT"


# ---------------------------------------------------------------------------
# Decision commands
# ---------------------------------------------------------------------------

class TestDecision:
    def test_create(self, workspace):
        r = _run(workspace, "decision", "create", "Rule", "--rationale", "reason")
        assert r["ok"] is True
        assert r["result"]["id"] == "decision-001"
        assert r["result"]["status"] == "active"

    def test_create_auto_attaches_intents(self, workspace):
        _run(workspace, "intent", "create", "A", "--query", "q")
        r = _run(workspace, "decision", "create", "Rule", "--rationale", "r")
        assert "intent-001" in r["result"]["intent_ids"]
        # Verify bidirectional
        i = _run(workspace, "intent", "show", "intent-001")
        assert "decision-001" in i["result"]["decision_ids"]

    def test_list(self, workspace):
        _run(workspace, "decision", "create", "R1", "--rationale", "r")
        _run(workspace, "decision", "create", "R2", "--rationale", "r")
        r = _run(workspace, "decision", "list")
        assert len(r["result"]) == 2

    def test_list_filter_intent(self, workspace):
        _run(workspace, "intent", "create", "A", "--query", "q")
        _run(workspace, "intent", "create", "B", "--query", "q")
        _run(workspace, "decision", "create", "Rule A", "--rationale", "r")
        _run(workspace, "decision", "deprecate", "decision-001")
        _run(workspace, "intent", "done", "intent-002")
        _run(workspace, "decision", "create", "Rule B", "--rationale", "r")
        r = _run(workspace, "decision", "list", "--intent", "intent-002")
        assert len(r["result"]) == 1
        assert r["result"][0]["id"] == "decision-001"

    def test_list_invalid_status(self, workspace):
        r = _run(workspace, "decision", "list", "--status", "activeish")
        assert r["ok"] is False
        assert r["error"]["code"] == "INVALID_INPUT"

    def test_deprecate(self, workspace):
        _run(workspace, "decision", "create", "R", "--rationale", "r")
        r = _run(workspace, "decision", "deprecate", "decision-001")
        assert r["result"]["status"] == "deprecated"

    def test_deprecate_is_terminal(self, workspace):
        _run(workspace, "decision", "create", "R", "--rationale", "r")
        _run(workspace, "decision", "deprecate", "decision-001")
        r = _run(workspace, "decision", "deprecate", "decision-001")
        assert r["error"]["code"] == "STATE_CONFLICT"

    def test_deprecated_not_auto_attached(self, workspace):
        _run(workspace, "decision", "create", "R", "--rationale", "r")
        _run(workspace, "decision", "deprecate", "decision-001")
        r = _run(workspace, "intent", "create", "New goal", "--query", "q")
        assert "decision-001" not in r["result"]["decision_ids"]

    def test_attach(self, workspace):
        _run(workspace, "intent", "create", "A", "--query", "q")
        _run(workspace, "intent", "create", "B", "--query", "q")
        _run(workspace, "decision", "create", "R", "--rationale", "r")
        # decision-001 auto-attached to both. Manually attach to verify idempotency.
        r = _run(workspace, "decision", "attach", "decision-001", "--intent", "intent-001")
        assert r["ok"] is True

    def test_attach_not_found(self, workspace):
        _run(workspace, "decision", "create", "R", "--rationale", "r")
        r = _run(workspace, "decision", "attach", "decision-001", "--intent", "intent-999")
        assert r["error"]["code"] == "OBJECT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Inspect
# ---------------------------------------------------------------------------

class TestInspect:
    def test_full_graph(self, workspace):
        _run(workspace, "intent", "create", "Active", "--query", "q")
        _run(workspace, "intent", "create", "Will suspend", "--query", "q")
        _run(workspace, "intent", "suspend", "intent-002")
        _run(workspace, "decision", "create", "Rule", "--rationale", "r")
        _run(workspace, "snap", "create", "S1", "--intent", "intent-001",
             "--summary", "did something")

        r = _run(workspace, "inspect")
        assert r["ok"] is True
        assert len(r["active_intents"]) == 1
        assert r["active_intents"][0]["id"] == "intent-001"
        assert r["active_intents"][0]["latest_snap_id"] == "snap-001"
        assert len(r["suspend_intents"]) == 1
        assert r["suspend_intents"][0]["id"] == "intent-002"
        assert len(r["active_decisions"]) == 1
        assert len(r["recent_snaps"]) == 1

    def test_orphan_snap_warning(self, workspace):
        _run(workspace, "intent", "create", "Goal", "--query", "q")
        _run(workspace, "snap", "create", "S", "--intent", "intent-001")
        # Delete intent file to create orphan
        intent_file = workspace / ".intent" / "intents" / "intent-001.json"
        intent_file.unlink()
        r = _run(workspace, "inspect")
        assert any("Orphan" in w for w in r["warnings"])

    def test_doctor_reports_broken_links(self, workspace):
        _run(workspace, "intent", "create", "Goal", "--query", "q")
        _run(workspace, "snap", "create", "S", "--intent", "intent-001")
        snap_file = workspace / ".intent" / "snaps" / "snap-001.json"
        data = json.loads(snap_file.read_text())
        data["intent_id"] = "intent-999"
        snap_file.write_text(json.dumps(data, indent=2))
        r = _run(workspace, "doctor")
        assert r["result"]["healthy"] is False
        assert any(issue["code"] == "MISSING_REFERENCE" for issue in r["result"]["issues"])

    def test_doctor_reports_invalid_status(self, workspace):
        _run(workspace, "intent", "create", "Goal", "--query", "q")
        intent_file = workspace / ".intent" / "intents" / "intent-001.json"
        data = json.loads(intent_file.read_text())
        data["status"] = "paused"
        intent_file.write_text(json.dumps(data, indent=2))
        r = _run(workspace, "doctor")
        assert r["result"]["healthy"] is False
        assert any(issue["code"] == "INVALID_STATUS" for issue in r["result"]["issues"])
