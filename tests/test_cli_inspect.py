import json

from tests.cli_support import _run, workspace


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

    def test_inspect_surfaces_latest_structured_checkpoint(self, workspace):
        _run(workspace, "intent", "create", "Structured")
        _run(workspace, "intent", "create", "Legacy")
        _run(workspace, "intent", "create", "Empty")
        _run(workspace, "snap", "create", "Older", "--intent", "intent-001",
             "--next", "superseded step")
        _run(workspace, "snap", "create", "Latest", "--intent", "intent-001",
             "--verified", "suite passes", "--boundary", "CLI only",
             "--next", "review", "--blocker", "none")
        _run(workspace, "snap", "create", "Verified: prose. Next: prose step.",
             "--intent", "intent-002")
        _run(workspace, "intent", "suspend", "intent-002")

        r = _run(workspace, "inspect")

        entries = {entry["id"]: entry for entry in r["active_intents"] + r["suspended"]}
        assert entries["intent-001"]["checkpoint"] == {
            "verified": "suite passes", "boundary": "CLI only",
            "next": "review", "blocker": "none",
        }
        assert entries["intent-001"]["checkpoint"] == entries["intent-001"]["latest_snap"]["checkpoint"]
        assert entries["intent-002"]["checkpoint"] is None
        assert entries["intent-002"]["latest_snap"]["what"] == "Verified: prose. Next: prose step."
        assert entries["intent-003"]["checkpoint"] is None

        focused = _run(workspace, "inspect", "--intent", "intent-001", "--history", "2")
        target = focused["active_intents"][0]
        assert target["checkpoint"]["next"] == "review"
        assert [snap.get("checkpoint") for snap in target["recent_snaps"]] == [
            {"next": "superseded step"}, target["checkpoint"],
        ]

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
