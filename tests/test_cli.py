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


def _stored_intent(obj_id="intent-001"):
    return {
        "id": obj_id,
        "object": "intent",
        "created_at": "2026-08-02T00:00:00+00:00",
        "what": "Atomic fixture",
        "why": "Verify write semantics",
        "origin": "pytest",
        "status": "active",
        "decision_ids": [],
        "snap_ids": [],
    }


def _stored_snap(obj_id="snap-001", intent_id="intent-001"):
    return {
        "id": obj_id,
        "object": "snap",
        "created_at": "2026-08-02T00:01:00+00:00",
        "what": "Consistent checkpoint",
        "why": "Reader must see both sides of the relation",
        "origin": "pytest",
        "intent_id": intent_id,
    }


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


def _global_auth_env(tmp_path):
    git_config = tmp_path / "auth-gitconfig"
    credential_file = tmp_path / "auth-credentials"
    subprocess.run(
        [
            "git",
            "config",
            "--file",
            str(git_config),
            "credential.helper",
            f"store --file={credential_file}",
        ],
        capture_output=True,
        check=True,
    )
    return {
        "GIT_CONFIG_GLOBAL": str(git_config),
        "GIT_CONFIG_NOSYSTEM": "1",
        "INTENT_CONFIG_HOME": str(tmp_path / "global-intent-config"),
    }


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

    @pytest.mark.parametrize(
        "args",
        [
            (),
            ("intent",),
            ("unknown-command",),
            ("inspect", "--history", "nope"),
        ],
    )
    def test_argument_errors_use_json_contract(self, workspace, args):
        r = _run(workspace, *args)

        assert r["ok"] is False
        assert r["error"]["code"] == "INVALID_INPUT"
        assert r["error"]["details"]["usage"].startswith("usage: itt")

    def test_inspect_reports_truncated_json_without_traceback(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        path = workspace / ".intent" / "intents" / "intent-001.json"
        path.write_text('{"id": "intent-001",', encoding="utf-8")

        r = _run(workspace, "inspect")

        assert r["ok"] is False
        assert r["error"]["code"] == "STORAGE_PARSE_ERROR"
        assert r["error"]["details"]["path"] == str(path)

    def test_inspect_reports_schema_error_without_traceback(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        path = workspace / ".intent" / "intents" / "intent-001.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        del payload["what"]
        path.write_text(json.dumps(payload), encoding="utf-8")

        r = _run(workspace, "inspect")

        assert r["ok"] is False
        assert r["error"]["code"] == "STORAGE_SCHEMA_ERROR"
        assert r["error"]["details"]["field"] == "what"

    def test_relationship_fields_must_be_lists_of_valid_ids(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        path = workspace / ".intent" / "intents" / "intent-001.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["snap_ids"] = "snap-001"
        path.write_text(json.dumps(payload), encoding="utf-8")

        r = _run(workspace, "inspect")

        assert r["error"]["code"] == "STORAGE_SCHEMA_ERROR"
        assert r["error"]["details"]["field"] == "snap_ids"

    def test_doctor_aggregates_all_parse_and_schema_damage(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        _run(workspace, "snap", "create", "Checkpoint", "--intent", "intent-001")
        _run(workspace, "decision", "create", "Rule")
        base = workspace / ".intent"

        (base / "intents" / "intent-001.json").write_text(
            '{"id": "intent-001",', encoding="utf-8",
        )
        snap_path = base / "snaps" / "snap-001.json"
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
        del snap["what"]
        snap_path.write_text(json.dumps(snap), encoding="utf-8")
        decision_path = base / "decisions" / "decision-001.json"
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        decision["intent_ids"] = "intent-001"
        decision_path.write_text(json.dumps(decision), encoding="utf-8")

        r = _run(workspace, "doctor")

        assert r["ok"] is True
        assert r["result"]["healthy"] is False
        assert [issue["code"] for issue in r["result"]["issues"]] == [
            "OBJECT_PARSE_ERROR",
            "OBJECT_SCHEMA_ERROR",
            "OBJECT_SCHEMA_ERROR",
        ]
        assert {issue["object"] for issue in r["result"]["issues"]} == {
            "intent", "snap", "decision",
        }


class TestHub:
    def test_supported_remote_parser_requires_exact_github_or_gitee_host(self):
        cases = {
            "git@github.com:example/demo.git": ("github", "example/demo"),
            "https://github.com/example/demo.git": ("github", "example/demo"),
            "ssh://git@github.com/example/demo.git": ("github", "example/demo"),
            "git@gitee.com:example/demo.git": ("gitee", "example/demo"),
            "https://gitee.com/example/demo.git": ("gitee", "example/demo"),
            "ssh://git@gitee.com/example/demo.git": ("gitee", "example/demo"),
        }
        for remote, expected in cases.items():
            parsed = intent_store.parse_repository_remote(remote)
            assert (parsed["provider"], parsed["repo_id"]) == expected

        for remote in (
            "https://evilgithub.com/example/demo.git",
            "https://gitee.com.evil.example/example/demo.git",
            "git@example.com:example/demo.git",
            "https://github.com/example/demo/extra.git",
            "https://token@github.com/example/demo.git",
        ):
            assert intent_store.parse_repository_remote(remote) is None

    def test_hub_status_is_read_only_and_reports_missing_binding(
        self, workspace,
    ):
        auth_env = _global_auth_env(workspace)
        r = _run(workspace, "hub", "status", extra_env=auth_env)

        assert r["ok"] is True
        assert r["action"] == "hub.status"
        assert r["result"]["linked"] is False
        assert r["result"]["credential_available"] is False
        assert r["result"]["api_base_url"] == "https://inthub.tenon.asia"
        assert r["result"]["missing_fields"] == [
            "project_id", "workspace_id", "repo_binding",
        ]
        assert not (workspace / ".intent" / "hub.json").exists()

    def test_global_auth_reused_by_two_projects_and_push_alias(
        self, workspace, inthub_server,
    ):
        auth_env = _global_auth_env(workspace)
        token = "ith_pat_test-global"
        login = _run(
            workspace,
            "auth",
            "login",
            "--api-base-url",
            inthub_server,
            "--token",
            token,
            extra_env=auth_env,
        )
        assert login["ok"] is True
        assert login["result"]["credential_store"] == "git-credential-helper"

        _add_github_remote(workspace)
        first_link = _run(workspace, "hub", "link", extra_env=auth_env)
        _run(workspace, "intent", "create", "First goal", extra_env=auth_env)
        first_push = _run(workspace, "push", extra_env=auth_env)
        assert first_push["ok"] is True
        assert first_push["action"] == "push"

        second = workspace / "second-project"
        second.mkdir()
        _init_git_repo(second)
        _add_github_remote(second, "https://github.com/example/second.git")
        assert _run(second, "init", extra_env=auth_env)["ok"] is True
        second_link = _run(second, "hub", "link", extra_env=auth_env)
        _run(second, "intent", "create", "Second goal", extra_env=auth_env)
        second_push = _run(second, "push", "--dry-run", extra_env=auth_env)

        assert first_link["result"]["api_base_url"] == inthub_server
        assert second_link["result"]["api_base_url"] == inthub_server
        assert first_link["result"]["project_id"] != second_link["result"]["project_id"]
        assert second_push["ok"] is True
        assert second_push["action"] == "push"
        assert second_push["result"]["dry_run"] is True

        hub_status = _run(workspace, "hub", "status", extra_env=auth_env)
        assert hub_status["result"]["linked"] is True
        assert hub_status["result"]["credential_available"] is True
        assert hub_status["result"]["repo_binding"]["provider"] == "github"
        assert hub_status["result"]["missing_fields"] == []

        first_hub = json.loads((workspace / ".intent" / "hub.json").read_text())
        global_config = json.loads(
            (workspace / "global-intent-config" / "config.json").read_text()
        )
        assert "auth_token" not in first_hub
        assert token not in json.dumps(first_hub)
        assert token not in json.dumps(global_config)

        status = _run(workspace, "auth", "status", extra_env=auth_env)
        assert status["result"]["authenticated"] is True
        assert status["result"]["token_source"] == "credential-helper"

        logout = _run(workspace, "auth", "logout", extra_env=auth_env)
        assert logout["result"]["credential_removed"] is True
        status = _run(workspace, "auth", "status", extra_env=auth_env)
        assert status["result"]["authenticated"] is False

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

    def test_link_requires_supported_remote(self, workspace, inthub_server):
        _add_github_remote(workspace, "git@example.com:foo/bar.git")
        r = _run(workspace, "hub", "link", "--api-base-url", inthub_server)
        assert r["ok"] is False
        assert r["error"]["code"] == "PROVIDER_UNSUPPORTED"

    def test_link_and_push_support_gitee_without_changing_origin(
        self, workspace, inthub_server,
    ):
        remote = "https://gitee.com/dozybot/WeSaid.git"
        _add_github_remote(workspace, remote)

        linked = _run(workspace, "hub", "link", "--api-base-url", inthub_server)
        pushed = _run(workspace, "push", "--dry-run")

        assert linked["ok"] is True
        assert linked["result"]["repo_binding"] == {
            "provider": "gitee",
            "repo_id": "dozybot/WeSaid",
            "owner": "dozybot",
            "name": "WeSaid",
        }
        assert pushed["ok"] is True
        assert pushed["result"]["payload"]["repo"]["provider"] == "gitee"
        configured = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=workspace,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert configured == remote

    def test_push_rejects_origin_that_differs_from_saved_binding(
        self, workspace, inthub_server,
    ):
        _add_github_remote(workspace)
        _run(workspace, "hub", "link", "--api-base-url", inthub_server)
        subprocess.run(
            ["git", "remote", "set-url", "origin", "git@gitee.com:example/demo.git"],
            cwd=workspace,
            capture_output=True,
            check=True,
        )

        r = _run(workspace, "push", "--dry-run")

        assert r["ok"] is False
        assert r["error"]["code"] == "REPO_BINDING_MISMATCH"
        assert r["error"]["details"]["expected"] == {
            "provider": "github", "repo_id": "example/demo",
        }
        assert r["error"]["details"]["actual"] == {
            "provider": "gitee", "repo_id": "example/demo",
        }

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
        assert config["authRequired"] is False
        assert config["authMode"] == "none"
        html = urlopen(f"{inthub_web_server}/").read().decode("utf-8")
        assert "IntHub" in html
        assert 'id="sidebar-body"' in html
        deep_link = urlopen(f"{inthub_web_server}/projects/demo").read().decode("utf-8")
        assert "IntHub" in deep_link
        js = urlopen(f"{inthub_web_server}/app.js").read().decode("utf-8")
        assert "Raw JSON" in js
        assert "Linked Decisions" in js
        assert "card-cancelled" in js
        assert "itt push" in js
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
        assert r["active_intents"][0]["snap_count"] == 1
        assert r["active_intents"][0]["has_more"] is False
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
        assert r["suspended"][0]["snap_count"] == 1
        assert r["suspended"][0]["has_more"] is False
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

    def test_default_reports_when_more_snap_history_exists(self, workspace):
        _run(workspace, "intent", "create", "With history")
        _run(workspace, "intent", "create", "Without history")
        for index in range(3):
            _run(
                workspace,
                "snap", "create", f"S{index + 1}",
                "--intent", "intent-001",
            )
        _run(workspace, "intent", "suspend", "intent-002")

        r = _run(workspace, "inspect")

        assert r["active_intents"][0]["snap_count"] == 3
        assert r["active_intents"][0]["has_more"] is True
        assert r["active_intents"][0]["latest_snap"]["id"] == "snap-003"
        assert r["suspended"][0]["snap_count"] == 0
        assert r["suspended"][0]["has_more"] is False
        assert r["suspended"][0]["latest_snap"] is None

    def test_history_returns_recent_snaps_oldest_to_newest(self, workspace):
        _run(workspace, "intent", "create", "Target")
        _run(workspace, "intent", "create", "Other")
        _run(workspace, "decision", "create", "Keep this rule")
        for index in range(5):
            _run(
                workspace,
                "snap", "create", f"S{index + 1}",
                "--intent", "intent-001",
            )

        r = _run(
            workspace,
            "inspect", "--intent", "intent-001", "--history", "3",
        )

        assert [entry["id"] for entry in r["active_intents"]] == ["intent-001"]
        assert r["suspended"] == []
        target = r["active_intents"][0]
        assert target["snap_count"] == 5
        assert target["has_more"] is True
        assert [snap["id"] for snap in target["recent_snaps"]] == [
            "snap-003", "snap-004", "snap-005",
        ]
        assert target["latest_snap"] == target["recent_snaps"][-1]
        assert r["active_decisions"][0]["id"] == "decision-001"

    def test_history_can_return_all_snaps_for_suspended_intent(self, workspace):
        _run(workspace, "intent", "create", "Paused")
        _run(workspace, "snap", "create", "S1", "--intent", "intent-001")
        _run(workspace, "snap", "create", "S2", "--intent", "intent-001")
        _run(workspace, "intent", "suspend", "intent-001")

        r = _run(
            workspace,
            "inspect", "--intent", "intent-001", "--history", "3",
        )

        assert r["active_intents"] == []
        target = r["suspended"][0]
        assert target["snap_count"] == 2
        assert target["has_more"] is False
        assert [snap["id"] for snap in target["recent_snaps"]] == [
            "snap-001", "snap-002",
        ]
        assert target["latest_snap_id"] == "snap-002"

    def test_history_rejects_invalid_target_or_limit(self, workspace):
        _run(workspace, "intent", "create", "Done")
        _run(workspace, "intent", "done", "intent-001")

        missing_target = _run(workspace, "inspect", "--history", "3")
        assert missing_target["error"]["code"] == "INVALID_INPUT"

        for invalid_limit in ("0", "-1"):
            invalid = _run(
                workspace,
                "inspect", "--intent", "intent-001",
                "--history", invalid_limit,
            )
            assert invalid["error"]["code"] == "INVALID_INPUT"

        unknown = _run(workspace, "inspect", "--intent", "intent-999")
        assert unknown["error"]["code"] == "OBJECT_NOT_FOUND"

        terminal = _run(workspace, "inspect", "--intent", "intent-001")
        assert terminal["error"]["code"] == "INVALID_INPUT"
        assert terminal["error"]["details"]["status"] == "done"

    def test_history_preserves_missing_snap_positions(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        _run(workspace, "snap", "create", "S1", "--intent", "intent-001")
        intent_file = workspace / ".intent" / "intents" / "intent-001.json"
        data = json.loads(intent_file.read_text())
        data["snap_ids"].append("snap-999")
        intent_file.write_text(json.dumps(data, indent=2))

        r = _run(
            workspace,
            "inspect", "--intent", "intent-001", "--history", "2",
        )

        target = r["active_intents"][0]
        assert target["snap_count"] == 2
        assert target["recent_snaps"][0]["id"] == "snap-001"
        assert target["recent_snaps"][1] is None
        assert any(issue["code"] == "MISSING_REFERENCE" for issue in r["warnings"])

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


class TestCliStorageSecurity:
    @pytest.mark.parametrize(
        ("args", "object_type", "status"),
        [
            (("intent", "activate", "../../victim"), "intent", "suspend"),
            (("intent", "suspend", "../../victim"), "intent", "active"),
            (("intent", "done", "../../victim"), "intent", "active"),
            (("intent", "cancel", "../../victim"), "intent", "active"),
            (("snap", "create", "S", "--intent", "../../victim"), "intent", "active"),
            (("decision", "deprecate", "../../victim"), "decision", "active"),
            (("inspect", "--intent", "../../victim"), "intent", "active"),
        ],
    )
    def test_explicit_traversal_ids_return_json_without_touching_target(
        self, workspace, args, object_type, status
    ):
        victim = workspace / "victim.json"
        payload = {
            "id": "../../victim",
            "object": object_type,
            "status": status,
            "what": "outside target",
            "why": "must remain unchanged",
            "snap_ids": [],
            "decision_ids": [],
            "intent_ids": [],
        }
        original = json.dumps(payload, indent=2)
        victim.write_text(original, encoding="utf-8")

        r = _run(workspace, *args)

        assert r["ok"] is False
        assert r["error"]["code"] == "INVALID_OBJECT_ID"
        assert victim.read_text(encoding="utf-8") == original
        assert list((workspace / ".intent" / "snaps").glob("snap-*.json")) == []

    def test_absolute_id_cannot_read_or_modify_external_object(self, workspace):
        target_without_suffix = workspace.parent / "absolute-decision-target"
        victim = Path(f"{target_without_suffix}.json")
        payload = {
            "id": str(target_without_suffix),
            "object": "decision",
            "status": "active",
            "what": "outside target",
            "why": "must remain unchanged",
            "intent_ids": [],
        }
        original = json.dumps(payload, indent=2)
        victim.write_text(original, encoding="utf-8")

        r = _run(
            workspace,
            "decision", "deprecate", str(target_without_suffix),
        )

        assert r["error"]["code"] == "INVALID_OBJECT_ID"
        assert victim.read_text(encoding="utf-8") == original

    def test_poisoned_stored_id_stops_before_partial_write(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        intent_file = workspace / ".intent" / "intents" / "intent-001.json"
        payload = json.loads(intent_file.read_text(encoding="utf-8"))
        payload["id"] = "../../victim"
        intent_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        r = _run(workspace, "decision", "create", "Rule")

        assert r["ok"] is False
        assert r["error"]["code"] == "STORAGE_INTEGRITY_ERROR"
        assert list((workspace / ".intent" / "decisions").glob("decision-*.json")) == []

    def test_symlinked_intent_root_returns_structured_error(self, workspace):
        storage = workspace / ".intent"
        real_storage = workspace / ".intent-real"
        storage.rename(real_storage)
        try:
            storage.symlink_to(real_storage, target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            pytest.skip(f"symlinks are unavailable in this environment: {exc}")

        r = _run(workspace, "inspect")

        assert r["ok"] is False
        assert r["error"]["code"] == "UNSAFE_STORAGE"


class TestAtomicWrites:
    def test_create_object_links_complete_temp_without_replacing(
        self, workspace, monkeypatch
    ):
        base = workspace / ".intent"
        destination = base / "intents" / "intent-001.json"
        payload = _stored_intent()
        calls = []
        real_link = intent_store.os.link

        def record_link(source, target):
            source_path = Path(source)
            target_path = Path(target)
            calls.append((source_path, target_path))
            assert source_path.parent == target_path.parent
            assert json.loads(source_path.read_text()) == payload
            real_link(source, target)

        monkeypatch.setattr(intent_store.os, "link", record_link)
        intent_store.create_object(base, "intent", "intent-001", payload)

        assert calls and calls[0][1] == destination
        assert json.loads(destination.read_text()) == payload
        assert list(destination.parent.glob(f".{destination.name}.*.tmp")) == []

    def test_update_object_replaces_from_same_directory(self, workspace, monkeypatch):
        base = workspace / ".intent"
        destination = base / "intents" / "intent-001.json"
        original = _stored_intent()
        intent_store.create_object(base, "intent", "intent-001", original)
        updated = dict(original, status="suspend")
        calls = []
        real_replace = intent_store.os.replace

        def record_replace(source, target):
            source_path = Path(source)
            target_path = Path(target)
            calls.append((source_path, target_path))
            assert source_path.parent == target_path.parent
            assert json.loads(source_path.read_text()) == updated
            real_replace(source, target)

        monkeypatch.setattr(intent_store.os, "replace", record_replace)
        intent_store.update_object(base, "intent", "intent-001", updated)

        assert calls and calls[0][1] == destination
        assert json.loads(destination.read_text()) == updated
        assert list(destination.parent.glob(f".{destination.name}.*.tmp")) == []

    def test_update_object_cleans_temp_and_preserves_old_file_when_replace_fails(
        self, workspace, monkeypatch
    ):
        base = workspace / ".intent"
        destination = base / "intents" / "intent-001.json"
        original = _stored_intent()
        intent_store.create_object(base, "intent", "intent-001", original)
        updated = dict(original, status="suspend")

        def fail_replace(_source, _target):
            raise OSError("replace failed")

        monkeypatch.setattr(intent_store.os, "replace", fail_replace)
        with pytest.raises(OSError, match="replace failed"):
            intent_store.update_object(base, "intent", "intent-001", updated)

        assert json.loads(destination.read_text()) == original
        assert list(destination.parent.glob(f".{destination.name}.*.tmp")) == []

    def test_update_object_never_creates_a_missing_destination(self, workspace):
        base = workspace / ".intent"
        destination = base / "intents" / "intent-001.json"

        with pytest.raises(intent_store.StoredObjectWriteConflictError):
            intent_store.update_object(
                base, "intent", "intent-001", _stored_intent(),
            )

        assert not destination.exists()

    def test_create_cleans_temp_when_destination_appears_during_commit(
        self, workspace, monkeypatch
    ):
        base = workspace / ".intent"
        destination = base / "intents" / "intent-001.json"

        def destination_appeared(_source, _target):
            raise FileExistsError("racing creator won")

        monkeypatch.setattr(intent_store.os, "link", destination_appeared)
        with pytest.raises(intent_store.StoredObjectWriteConflictError):
            intent_store.create_object(
                base, "intent", "intent-001", _stored_intent(),
            )

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

    def test_casefold_occupied_id_is_counted_and_never_overwritten(self, workspace):
        base = workspace / ".intent"
        occupied = base / "intents" / "intent-001.JSON"
        original = json.dumps(_stored_intent(), indent=2)
        occupied.write_text(original, encoding="utf-8")

        result = _run(workspace, "intent", "create", "New goal")

        assert result["ok"] is True
        assert result["result"]["id"] == "intent-002"
        assert occupied.read_text(encoding="utf-8") == original
        assert (base / "intents" / "intent-002.json").is_file()

    def test_create_rejects_casefold_destination_conflict_without_overwrite(
        self, workspace
    ):
        base = workspace / ".intent"
        occupied = base / "intents" / "intent-001.JSON"
        original = json.dumps(_stored_intent(), indent=2)
        occupied.write_text(original, encoding="utf-8")

        with pytest.raises(intent_store.StoredObjectWriteConflictError):
            intent_store.create_object(
                base, "intent", "intent-001", _stored_intent(),
            )

        assert occupied.read_text(encoding="utf-8") == original

    def test_update_rejects_noncanonical_casefold_destination(self, workspace):
        base = workspace / ".intent"
        occupied = base / "intents" / "intent-001.JSON"
        original = json.dumps(_stored_intent(), indent=2)
        occupied.write_text(original, encoding="utf-8")

        with pytest.raises(intent_store.StoredObjectWriteConflictError):
            intent_store.update_object(
                base,
                "intent",
                "intent-001",
                dict(_stored_intent(), status="suspend"),
            )

        assert occupied.read_text(encoding="utf-8") == original

    def test_workspace_write_lock_times_out_for_second_writer(self, workspace):
        base = workspace / ".intent"
        with intent_store.workspace_write_lock(base):
            with pytest.raises(intent_store.WorkspaceBusyError):
                with intent_store.workspace_write_lock(base, timeout=0.01):
                    pass

    def test_inspect_waits_for_complete_multi_file_snapshot(self, workspace):
        base = workspace / ".intent"
        intent_store.create_object(
            base, "intent", "intent-001", _stored_intent(),
        )

        with ThreadPoolExecutor(max_workers=1) as pool:
            with intent_store.workspace_write_lock(base):
                intent_store.create_object(
                    base, "snap", "snap-001", _stored_snap(),
                )
                reader = pool.submit(_run, workspace, "inspect")
                threading.Event().wait(0.3)
                assert reader.done() is False

                intent = intent_store.read_object(
                    base, "intent", "intent-001",
                )
                intent["snap_ids"].append("snap-001")
                intent_store.update_object(
                    base, "intent", "intent-001", intent,
                )

            result = reader.result(timeout=5)

        assert result["ok"] is True
        assert result["active_intents"][0]["latest_snap"]["id"] == "snap-001"
        assert result["warnings"] == []

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
