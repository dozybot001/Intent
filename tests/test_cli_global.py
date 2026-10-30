import json
import subprocess
from pathlib import Path
import pytest

from tests.cli_support import _expected_cli_version, _init_git_repo, _run, workspace


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
        assert r["ok"] is True
        assert (tmp_path / ".intent").is_dir()

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
