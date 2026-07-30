"""Tests for Intent CLI — covers the command surface, state machines, and error codes."""

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

import pytest

from apps.inthub_api.server import make_handler as make_inthub_api_handler
from apps.inthub_web.server import make_handler as make_inthub_web_handler
from intent_cli import store as intent_store

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATHS = [str(REPO_ROOT), str(REPO_ROOT / "src")]


@pytest.fixture
def workspace(tmp_path):
    """Create a git repo with .intent/ initialized."""
    _init_git_repo(tmp_path)
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


def _run(cwd, *args, extra_env=None):
    """Run itt command and return parsed JSON."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        SOURCE_PATHS + ([existing] if existing else [])
    )
    if extra_env:
        env.update(extra_env)
    r = subprocess.run(
        [sys.executable, "-m", "intent_cli", *args],
        cwd=cwd, capture_output=True, text=True, env=env,
    )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            "itt did not return JSON.\n"
            f"args={args}\n"
            f"returncode={r.returncode}\n"
            f"stdout={r.stdout!r}\n"
            f"stderr={r.stderr!r}"
        ) from exc


def _init_git_repo(cwd):
    """Create a hermetic test repository with repository-local author identity."""
    subprocess.run(["git", "init"], cwd=cwd, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Intent Tests"],
        cwd=cwd, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "intent-tests@example.invalid"],
        cwd=cwd, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=cwd, capture_output=True, check=True,
    )


def _add_github_remote(cwd, remote_url="git@github.com:example/demo.git"):
    subprocess.run(
        ["git", "remote", "add", "origin", remote_url],
        cwd=cwd, capture_output=True, check=True,
    )


def _get_json(url):
    with urlopen(url) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _expected_cli_version():
    from importlib.metadata import version
    try:
        return version("intent-cli")
    except Exception:
        from intent_cli import __version__
        return __version__


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

    def test_init_excludes_local_semantic_data_from_git(self, workspace):
        exclude_path = subprocess.run(
            ["git", "rev-parse", "--git-path", "info/exclude"],
            cwd=workspace, capture_output=True, text=True, check=True,
        ).stdout.strip()
        exclude_path = Path(exclude_path)
        if not exclude_path.is_absolute():
            exclude_path = workspace / exclude_path
        assert ".intent/" in exclude_path.read_text(encoding="utf-8").splitlines()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace, capture_output=True, text=True, check=True,
        )
        assert status.stdout == ""

    def test_inspect_empty(self, workspace):
        r = _run(workspace, "inspect")
        assert r["ok"] is True
        assert r["active_intents"] == []
        assert r["active_decisions"] == []
        assert r["suspended"] == []
        assert r["warnings"] == []

    def test_not_initialized(self, tmp_path):
        _init_git_repo(tmp_path)
        r = _run(tmp_path, "inspect")
        assert r["ok"] is False
        assert r["error"]["code"] == "NOT_INITIALIZED"

    def test_doctor_healthy(self, workspace):
        r = _run(workspace, "doctor")
        assert r["ok"] is True
        assert r["result"]["healthy"] is True
        assert r["result"]["issues"] == []


class TestHub:
    def test_link_configures_and_binds(self, workspace, inthub_server):
        _add_github_remote(workspace)
        r = _run(workspace, "hub", "link", "--api-base-url", inthub_server,
                 "--project-name", "Demo Project")
        assert r["ok"] is True
        hub_config = json.loads((workspace / ".intent" / "hub.json").read_text())
        assert hub_config["api_base_url"] == inthub_server
        assert hub_config["project_id"].startswith("proj_")
        assert hub_config["workspace_id"].startswith("wks_")
        assert hub_config["repo_binding"]["repo_id"] == "example/demo"

    def test_link_requires_github_remote(self, workspace, inthub_server):
        _add_github_remote(workspace, "git@example.com:foo/bar.git")
        r = _run(workspace, "hub", "link", "--api-base-url", inthub_server)
        assert r["ok"] is False
        assert r["error"]["code"] == "PROVIDER_UNSUPPORTED"

    def test_sync_requires_link(self, workspace, inthub_server):
        _add_github_remote(workspace)
        r = _run(workspace, "hub", "sync", "--api-base-url", inthub_server)
        assert r["ok"] is False
        assert r["error"]["code"] == "NOT_LINKED"

    def test_sync_dry_run(self, workspace, inthub_server):
        _add_github_remote(workspace)
        _run(workspace, "hub", "link", "--api-base-url", inthub_server,
             "--project-name", "Demo Project")
        _run(workspace, "intent", "create", "Goal")
        r = _run(workspace, "hub", "sync", "--dry-run")
        assert r["ok"] is True
        assert r["result"]["dry_run"] is True
        assert r["result"]["payload"]["snapshot"]["intents"][0]["id"] == "intent-001"

    def test_sync_updates_overview_and_handoff(self, workspace, inthub_server):
        _add_github_remote(workspace)
        _run(workspace, "hub", "link", "--api-base-url", inthub_server,
             "--project-name", "Demo Project")
        _run(workspace, "intent", "create", "Goal", "--why", "why?")
        _run(workspace, "decision", "create", "Rule", "--why", "reason")
        _run(workspace, "snap", "create", "Did X", "--intent", "intent-001",
             "--why", "details")
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
        assert "IntHub" in html
        assert 'id="sidebar-body"' in html
        deep_link = urlopen(f"{inthub_web_server}/projects/demo").read().decode("utf-8")
        assert "IntHub" in deep_link
        js = urlopen(f"{inthub_web_server}/app.js").read().decode("utf-8")
        assert "Raw JSON" in js
        assert "Linked Decisions" in js
        assert "card-cancelled" in js
        assert "itt hub sync" in js
        css = urlopen(f"{inthub_web_server}/styles.css").read().decode("utf-8")
        assert ".badge.status-cancelled" in css


# ---------------------------------------------------------------------------
# Intent commands
# ---------------------------------------------------------------------------

class TestIntent:
    def test_create(self, workspace):
        r = _run(workspace, "intent", "create", "Fix bug", "--why", "why crash?")
        assert r["ok"] is True
        assert r["result"]["id"] == "intent-001"
        assert r["result"]["status"] == "active"
        assert r["result"]["why"] == "why crash?"

    def test_create_with_why(self, workspace):
        r = _run(workspace, "intent", "create", "Fix bug",
                 "--why", "users report crashes on login")
        assert r["result"]["why"] == "users report crashes on login"

    def test_create_auto_attaches_decisions(self, workspace):
        _run(workspace, "intent", "create", "Goal A")
        _run(workspace, "decision", "create", "Rule 1", "--why", "reason")
        r = _run(workspace, "intent", "create", "Goal B")
        assert "decision_ids" not in r["result"]
        intent = json.loads((workspace / ".intent" / "intents" / "intent-002.json").read_text())
        assert "decision-001" in intent["decision_ids"]

    def test_suspend_activate(self, workspace):
        _run(workspace, "intent", "create", "A")
        r = _run(workspace, "intent", "suspend", "intent-001")
        assert r["result"]["status"] == "suspend"
        r = _run(workspace, "intent", "activate", "intent-001")
        assert r["result"]["status"] == "active"

    def test_suspend_omits_id_when_single_active(self, workspace):
        _run(workspace, "intent", "create", "A")
        r = _run(workspace, "intent", "suspend")
        assert r["ok"] is True
        assert r["result"]["id"] == "intent-001"
        assert any("Inferred intent intent-001" in w for w in r["warnings"])

    def test_done_omits_id_when_single_active(self, workspace):
        _run(workspace, "intent", "create", "A")
        r = _run(workspace, "intent", "done")
        assert r["ok"] is True
        assert r["result"]["id"] == "intent-001"
        assert any("Inferred intent intent-001" in w for w in r["warnings"])

    def test_activate_omits_id_when_single_suspended(self, workspace):
        _run(workspace, "intent", "create", "A")
        _run(workspace, "intent", "suspend", "intent-001")
        r = _run(workspace, "intent", "activate")
        assert r["ok"] is True
        assert r["result"]["id"] == "intent-001"
        assert any("Inferred intent intent-001" in w for w in r["warnings"])

    def test_activate_catches_up_decisions(self, workspace):
        _run(workspace, "intent", "create", "A")
        _run(workspace, "intent", "suspend", "intent-001")
        _run(workspace, "decision", "create", "New rule", "--why", "reason")
        r = _run(workspace, "intent", "activate", "intent-001")
        assert "decision_ids" not in r["result"]
        intent = json.loads((workspace / ".intent" / "intents" / "intent-001.json").read_text())
        assert "decision-001" in intent["decision_ids"]

    def test_done(self, workspace):
        _run(workspace, "intent", "create", "A")
        r = _run(workspace, "intent", "done", "intent-001")
        assert r["result"]["status"] == "done"

    def test_done_is_terminal(self, workspace):
        _run(workspace, "intent", "create", "A")
        _run(workspace, "intent", "done", "intent-001")
        r = _run(workspace, "intent", "activate", "intent-001")
        assert r["error"]["code"] == "STATE_CONFLICT"

    def test_cancel_active_with_reason(self, workspace):
        _run(workspace, "intent", "create", "A")
        r = _run(
            workspace, "intent", "cancel", "intent-001",
            "--reason", "The product direction changed",
        )
        assert r["ok"] is True
        assert r["result"]["status"] == "cancelled"
        assert r["result"]["reason"] == "The product direction changed"
        assert _run(workspace, "inspect")["active_intents"] == []

    def test_cancel_suspended_and_infer_unique_open_intent(self, workspace):
        _run(workspace, "intent", "create", "A")
        _run(workspace, "intent", "suspend")
        r = _run(workspace, "intent", "cancel")
        assert r["ok"] is True
        assert r["result"]["status"] == "cancelled"
        assert any("only open intent" in warning for warning in r["warnings"])

    def test_cancel_rejects_terminal_intent(self, workspace):
        _run(workspace, "intent", "create", "A")
        _run(workspace, "intent", "done")
        r = _run(workspace, "intent", "cancel", "intent-001")
        assert r["ok"] is False
        assert r["error"]["code"] == "STATE_CONFLICT"

    def test_cancel_without_id_requires_unique_open_intent(self, workspace):
        _run(workspace, "intent", "create", "A")
        _run(workspace, "intent", "create", "B")
        r = _run(workspace, "intent", "cancel")
        assert r["ok"] is False
        assert r["error"]["code"] == "MULTIPLE_OPEN_INTENTS"
        assert {item["id"] for item in r["error"]["details"]["candidates"]} == {
            "intent-001", "intent-002",
        }

    def test_suspend_only_active(self, workspace):
        _run(workspace, "intent", "create", "A")
        _run(workspace, "intent", "done", "intent-001")
        r = _run(workspace, "intent", "suspend", "intent-001")
        assert r["error"]["code"] == "STATE_CONFLICT"

    def test_suspend_without_id_requires_unique_active_intent(self, workspace):
        r = _run(workspace, "intent", "suspend")
        assert r["error"]["code"] == "NO_ACTIVE_INTENT"
        _run(workspace, "intent", "create", "A")
        _run(workspace, "intent", "create", "B")
        r = _run(workspace, "intent", "suspend")
        assert r["error"]["code"] == "MULTIPLE_ACTIVE_INTENTS"
        assert {c["id"] for c in r["error"]["details"]["candidates"]} == {"intent-001", "intent-002"}

    def test_activate_without_id_requires_unique_suspended_intent(self, workspace):
        r = _run(workspace, "intent", "activate")
        assert r["error"]["code"] == "NO_SUSPENDED_INTENT"
        _run(workspace, "intent", "create", "A")
        _run(workspace, "intent", "create", "B")
        _run(workspace, "intent", "suspend", "intent-001")
        _run(workspace, "intent", "suspend", "intent-002")
        r = _run(workspace, "intent", "activate")
        assert r["error"]["code"] == "MULTIPLE_SUSPENDED_INTENTS"
        assert {c["id"] for c in r["error"]["details"]["candidates"]} == {"intent-001", "intent-002"}


# ---------------------------------------------------------------------------
# Snap commands
# ---------------------------------------------------------------------------

class TestSnap:
    def test_create_with_why(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        r = _run(workspace, "snap", "create", "Did X", "--intent", "intent-001",
                 "--why", "reasoning here")
        assert r["ok"] is True
        assert r["result"]["id"] == "snap-001"
        assert r["result"]["intent_id"] == "intent-001"
        assert r["result"]["what"] == "Did X"
        assert r["result"]["why"] == "reasoning here"
        assert r["warnings"] == []
        assert "origin" in r["result"]

    def test_create_without_why(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        r = _run(workspace, "snap", "create", "Did X", "--intent", "intent-001")
        assert r["ok"] is True
        assert r["result"]["why"] == ""

    def test_create_with_all_fields(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        r = _run(workspace, "snap", "create", "Did X", "--intent", "intent-001",
                 "--why", "because", "--origin", "cli-override")
        assert r["result"]["why"] == "because"
        assert r["result"]["origin"] == "cli-override"

    def test_create_sets_origin_from_env(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        r = _run(
            workspace,
            "snap", "create", "S", "--intent", "intent-001",
            extra_env={"ITT_ORIGIN": "fixture-origin"},
        )
        assert r["ok"] is True
        assert r["result"]["origin"] == "fixture-origin"

    def test_create_origin_flag_overrides_env(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        r = _run(
            workspace,
            "snap", "create", "S", "--intent", "intent-001",
            "--origin", "cli-override",
            extra_env={"ITT_ORIGIN": "from-env"},
        )
        assert r["result"]["origin"] == "cli-override"

    def test_create_omits_intent_when_single_active(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        r = _run(workspace, "snap", "create", "Did X", "--why", "reason")
        assert r["ok"] is True
        assert r["result"]["intent_id"] == "intent-001"
        assert any("Inferred intent intent-001" in w for w in r["warnings"])

    def test_create_no_active_intent(self, workspace):
        r = _run(workspace, "snap", "create", "S")
        assert r["ok"] is False
        assert r["error"]["code"] == "NO_ACTIVE_INTENT"

    def test_create_multiple_active_requires_intent(self, workspace):
        _run(workspace, "intent", "create", "A")
        _run(workspace, "intent", "create", "B")
        r = _run(workspace, "snap", "create", "S")
        assert r["ok"] is False
        assert r["error"]["code"] == "MULTIPLE_ACTIVE_INTENTS"
        cand = r["error"]["details"]["candidates"]
        assert {c["id"] for c in cand} == {"intent-001", "intent-002"}

    def test_create_updates_intent_snap_ids(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        _run(workspace, "snap", "create", "S1", "--intent", "intent-001",
             "--why", "a")
        _run(workspace, "snap", "create", "S2", "--intent", "intent-001",
             "--why", "b")
        intent = json.loads((workspace / ".intent" / "intents" / "intent-001.json").read_text())
        assert intent["snap_ids"] == ["snap-001", "snap-002"]

    def test_create_requires_active_intent(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        _run(workspace, "intent", "done", "intent-001")
        r = _run(workspace, "snap", "create", "S", "--intent", "intent-001")
        assert r["error"]["code"] == "STATE_CONFLICT"

    def test_create_intent_not_found(self, workspace):
        r = _run(workspace, "snap", "create", "S", "--intent", "intent-999")
        assert r["error"]["code"] == "OBJECT_NOT_FOUND"


# ---------------------------------------------------------------------------
# Decision commands
# ---------------------------------------------------------------------------

class TestDecision:
    def test_create(self, workspace):
        r = _run(workspace, "decision", "create", "Rule", "--why", "reason")
        assert r["ok"] is True
        assert r["result"]["id"] == "decision-001"
        assert r["result"]["status"] == "active"
        assert r["result"]["what"] == "Rule"
        assert r["result"]["why"] == "reason"

    def test_create_without_why(self, workspace):
        r = _run(workspace, "decision", "create", "Rule")
        assert r["ok"] is True
        assert r["result"]["why"] == ""

    def test_create_auto_attaches_intents(self, workspace):
        _run(workspace, "intent", "create", "A")
        r = _run(workspace, "decision", "create", "Rule", "--why", "reason")
        assert "intent-001" in r["result"]["intent_ids"]
        intent = json.loads((workspace / ".intent" / "intents" / "intent-001.json").read_text())
        assert "decision-001" in intent["decision_ids"]

    def test_deprecate(self, workspace):
        _run(workspace, "decision", "create", "R", "--why", "reason")
        r = _run(workspace, "decision", "deprecate", "decision-001")
        assert r["result"]["status"] == "deprecated"

    def test_deprecate_with_reason(self, workspace):
        _run(workspace, "decision", "create", "R", "--why", "reason")
        r = _run(workspace, "decision", "deprecate", "decision-001",
                 "--reason", "no longer needed")
        assert r["result"]["status"] == "deprecated"
        assert r["result"]["reason"] == "no longer needed"

    def test_deprecate_is_terminal(self, workspace):
        _run(workspace, "decision", "create", "R", "--why", "reason")
        _run(workspace, "decision", "deprecate", "decision-001")
        r = _run(workspace, "decision", "deprecate", "decision-001")
        assert r["error"]["code"] == "STATE_CONFLICT"

    def test_deprecated_not_auto_attached(self, workspace):
        _run(workspace, "decision", "create", "R", "--why", "reason")
        _run(workspace, "decision", "deprecate", "decision-001")
        r = _run(workspace, "intent", "create", "New goal")
        assert "decision_ids" not in r["result"]
        intent = json.loads((workspace / ".intent" / "intents" / "intent-001.json").read_text())
        assert "decision-001" not in intent["decision_ids"]

# ---------------------------------------------------------------------------
# Inspect
# ---------------------------------------------------------------------------

class TestInspect:
    def test_full_graph(self, workspace):
        _run(workspace, "intent", "create", "Active", "--why", "active why")
        _run(workspace, "intent", "create", "Will suspend", "--why", "suspended why")
        _run(workspace, "snap", "create", "Paused checkpoint", "--intent", "intent-002",
             "--why", "pause reason", "--origin", "test-agent")
        _run(workspace, "intent", "suspend", "intent-002")
        _run(workspace, "decision", "create", "Rule", "--why", "reason")
        _run(workspace, "snap", "create", "S1", "--intent", "intent-001",
             "--why", "did something", "--origin", "test-agent")

        r = _run(workspace, "inspect")
        assert r["ok"] is True
        assert len(r["active_intents"]) == 1
        assert r["active_intents"][0]["id"] == "intent-001"
        assert r["active_intents"][0]["what"] == "Active"
        assert r["active_intents"][0]["why"] == "active why"
        assert r["active_intents"][0]["latest_snap"]["id"] == "snap-002"
        assert r["active_intents"][0]["latest_snap"]["what"] == "S1"
        assert r["active_intents"][0]["latest_snap"]["why"] == "did something"
        assert r["active_intents"][0]["latest_snap"] == json.loads(
            (workspace / ".intent" / "snaps" / "snap-002.json").read_text()
        )
        assert len(r["suspended"]) == 1
        assert r["suspended"][0]["id"] == "intent-002"
        assert r["suspended"][0]["what"] == "Will suspend"
        assert r["suspended"][0]["why"] == "suspended why"
        assert r["suspended"][0]["latest_snap_id"] == "snap-001"
        assert r["suspended"][0]["latest_snap"] == json.loads(
            (workspace / ".intent" / "snaps" / "snap-001.json").read_text()
        )
        assert len(r["active_decisions"]) == 1
        assert r["active_decisions"][0] == {
            "id": "decision-001",
            "what": "Rule",
            "why": "reason",
        }

    def test_orphan_snap_warning(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        _run(workspace, "snap", "create", "S", "--intent", "intent-001",
             "--why", "reason")
        # Delete intent file to create orphan
        intent_file = workspace / ".intent" / "intents" / "intent-001.json"
        intent_file.unlink()
        r = _run(workspace, "inspect")
        assert any(
            issue["code"] == "MISSING_REFERENCE"
            and issue["object"] == "snap"
            and issue["id"] == "snap-001"
            for issue in r["warnings"]
        )

    def test_inspect_warnings_match_doctor_issues(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        intent_file = workspace / ".intent" / "intents" / "intent-001.json"
        data = json.loads(intent_file.read_text())
        data["status"] = "paused"
        data["snap_ids"] = ["snap-999"]
        intent_file.write_text(json.dumps(data, indent=2))

        inspect = _run(workspace, "inspect")
        doctor = _run(workspace, "doctor")

        assert inspect["warnings"] == doctor["result"]["issues"]
        assert {issue["code"] for issue in inspect["warnings"]} == {
            "INVALID_STATUS",
            "MISSING_REFERENCE",
        }

    def test_doctor_reports_broken_links(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        _run(workspace, "snap", "create", "S", "--intent", "intent-001",
             "--why", "reason")
        snap_file = workspace / ".intent" / "snaps" / "snap-001.json"
        data = json.loads(snap_file.read_text())
        data["intent_id"] = "intent-999"
        snap_file.write_text(json.dumps(data, indent=2))
        r = _run(workspace, "doctor")
        assert r["result"]["healthy"] is False
        assert any(issue["code"] == "MISSING_REFERENCE" for issue in r["result"]["issues"])

    def test_doctor_reports_invalid_status(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        intent_file = workspace / ".intent" / "intents" / "intent-001.json"
        data = json.loads(intent_file.read_text())
        data["status"] = "paused"
        intent_file.write_text(json.dumps(data, indent=2))
        r = _run(workspace, "doctor")
        assert r["result"]["healthy"] is False
        assert any(issue["code"] == "INVALID_STATUS" for issue in r["result"]["issues"])


class TestAtomicWrites:
    def test_write_object_replaces_from_same_directory(self, workspace, monkeypatch):
        base = workspace / ".intent"
        destination = base / "intents" / "intent-001.json"
        calls = []
        real_replace = intent_store.os.replace

        def record_replace(source, target):
            source_path = Path(source)
            target_path = Path(target)
            calls.append((source_path, target_path))
            assert source_path.parent == target_path.parent
            assert json.loads(source_path.read_text()) == {"id": "intent-001"}
            real_replace(source, target)

        monkeypatch.setattr(intent_store.os, "replace", record_replace)
        intent_store.write_object(base, "intent", "intent-001", {"id": "intent-001"})

        assert calls and calls[0][1] == destination
        assert json.loads(destination.read_text()) == {"id": "intent-001"}
        assert list(destination.parent.glob(f".{destination.name}.*.tmp")) == []

    def test_write_object_cleans_temp_file_when_replace_fails(self, workspace, monkeypatch):
        base = workspace / ".intent"
        destination = base / "intents" / "intent-001.json"

        def fail_replace(_source, _target):
            raise OSError("replace failed")

        monkeypatch.setattr(intent_store.os, "replace", fail_replace)
        with pytest.raises(OSError, match="replace failed"):
            intent_store.write_object(base, "intent", "intent-001", {"id": "intent-001"})

        assert not destination.exists()
        assert list(destination.parent.glob(f".{destination.name}.*.tmp")) == []

    def test_write_hub_config_is_atomic(self, workspace, monkeypatch):
        base = workspace / ".intent"
        destination = base / "hub.json"
        real_replace = intent_store.os.replace
        calls = []

        def record_replace(source, target):
            calls.append((Path(source), Path(target)))
            real_replace(source, target)

        monkeypatch.setattr(intent_store.os, "replace", record_replace)
        intent_store.write_hub_config(base, {"api_base_url": "http://127.0.0.1"})

        assert calls and calls[0][0].parent == destination.parent
        assert calls[0][1] == destination
        assert json.loads(destination.read_text()) == {
            "api_base_url": "http://127.0.0.1"
        }

    def test_workspace_write_lock_times_out_for_second_writer(self, workspace):
        base = workspace / ".intent"
        with intent_store.workspace_write_lock(base):
            with pytest.raises(intent_store.WorkspaceBusyError):
                with intent_store.workspace_write_lock(base, timeout=0.01):
                    pass

    def test_concurrent_cli_writers_receive_unique_ids(self, workspace):
        def create(index):
            return _run(workspace, "intent", "create", f"Goal {index}")

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(create, range(8)))

        assert all(result["ok"] is True for result in results)
        assert {result["result"]["id"] for result in results} == {
            f"intent-{index:03d}" for index in range(1, 9)
        }
        assert _run(workspace, "doctor")["result"]["healthy"] is True
