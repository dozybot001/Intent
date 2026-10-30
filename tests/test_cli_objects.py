import json
import pytest
from intent_cli import store as intent_store

from tests.cli_support import _run, workspace


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

    def test_create_records_structured_checkpoint(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        r = _run(
            workspace,
            "snap", "create", "Made publication atomic", "--intent", "intent-001",
            "--why", "consumers must not see partial releases",
            "--constraints", "  keep the rollback path  ",
            "--blocker", "none",
            "--next", "switch staging to the new publisher",
            "--boundary", "发布器之外未改动",
            "--verified", "release suite passes",
        )
        assert r["ok"] is True
        expected = {
            "verified": "release suite passes",
            "boundary": "发布器之外未改动",
            "next": "switch staging to the new publisher",
            "blocker": "none",
            "constraints": "keep the rollback path",
        }
        assert r["result"]["checkpoint"] == expected
        assert list(r["result"]["checkpoint"]) == list(intent_store.CHECKPOINT_FIELDS)
        assert r["result"]["what"] == "Made publication atomic"
        assert r["result"]["why"] == "consumers must not see partial releases"
        stored = json.loads((workspace / ".intent" / "snaps" / "snap-001.json").read_text())
        assert stored == r["result"]

    def test_create_partial_checkpoint_omits_unrecorded_cells(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        r = _run(workspace, "snap", "create", "S", "--next", "review", "--blocker", "waiting for access")
        assert r["result"]["checkpoint"] == {"next": "review", "blocker": "waiting for access"}

    def test_create_without_checkpoint_keeps_legacy_shape(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        r = _run(workspace, "snap", "create", "Verified: legacy prose", "--why", "Next: unchanged")
        stored = json.loads((workspace / ".intent" / "snaps" / "snap-001.json").read_text())
        assert "checkpoint" not in r["result"]
        assert set(stored) - {"author", "git"} == {"id", "object", "created_at", "what", "why", "intent_id", "origin"}

    @pytest.mark.parametrize(
        ("flag", "value", "message"),
        [
            ("--next", "   ", "must not be blank"),
            ("--blocker", "", "must not be blank"),
            ("--verified", "x" * (intent_store.CHECKPOINT_FIELD_MAX_CHARS + 1), "exceeds"),
        ],
    )
    def test_create_rejects_unusable_checkpoint_before_writing(self, workspace, flag, value, message):
        _run(workspace, "intent", "create", "Goal")
        r = _run(workspace, "snap", "create", "S", "--intent", "intent-001", flag, value)
        assert r["ok"] is False
        assert r["error"]["code"] == "INVALID_INPUT"
        assert message in r["error"]["message"]
        assert r["error"]["details"]["field"] == flag.removeprefix("--")
        assert list((workspace / ".intent" / "snaps").iterdir()) == []
        intent = json.loads((workspace / ".intent" / "intents" / "intent-001.json").read_text())
        assert intent["snap_ids"] == []

    def test_create_accepts_checkpoint_cell_at_size_limit(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        value = "界" * intent_store.CHECKPOINT_FIELD_MAX_CHARS
        r = _run(workspace, "snap", "create", "S", "--verified", value)
        assert r["result"]["checkpoint"] == {"verified": value}


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
