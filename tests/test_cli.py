import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Optional


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "itt"


def run_cli(cwd: Path, *args: str, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        env=merged_env,
    )


def run_cli_json(cwd: Path, *args: str) -> tuple:
    result = run_cli(cwd, *args)
    return result, json.loads(result.stdout)


def init_git_repo(cwd: Path, *, with_commit: bool = True) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(cwd), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(cwd), check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(cwd), check=True, capture_output=True,
    )
    if with_commit:
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=str(cwd), check=True, capture_output=True,
        )


class IntentCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cwd = Path(self.tmp)
        init_git_repo(self.cwd)

    def itt(self, *args: str) -> dict:
        result = run_cli(self.cwd, *args)
        return json.loads(result.stdout)

    def itt_rc(self, *args: str) -> tuple:
        result = run_cli(self.cwd, *args)
        return json.loads(result.stdout), result.returncode

    # --- init ---

    def test_init_creates_workspace(self):
        d = self.itt("init")
        self.assertTrue(d["ok"])
        self.assertEqual(d["action"], "init")
        self.assertEqual(d["result"]["state"]["workspace_status"], "idle")
        self.assertTrue((self.cwd / ".intent" / "config.json").exists())
        self.assertTrue((self.cwd / ".intent" / "intents").is_dir())
        self.assertTrue((self.cwd / ".intent" / "snaps").is_dir())
        self.assertTrue((self.cwd / ".intent" / "decisions").is_dir())

    def test_init_fails_if_already_initialized(self):
        self.itt("init")
        d, rc = self.itt_rc("init")
        self.assertFalse(d["ok"])
        self.assertEqual(d["error"]["code"], "ALREADY_EXISTS")
        self.assertNotEqual(rc, 0)

    def test_init_requires_git(self):
        no_git = tempfile.mkdtemp()
        result = run_cli(Path(no_git), "init")
        d = json.loads(result.stdout)
        self.assertFalse(d["ok"])
        self.assertEqual(d["error"]["code"], "GIT_STATE_INVALID")

    # --- core lifecycle ---

    def test_full_lifecycle(self):
        self.itt("init")

        # start
        d = self.itt("start", "Fix the bug")
        self.assertEqual(d["result"]["status"], "open")
        self.assertIn("decision_ids", d["result"])
        intent_id = d["result"]["id"]

        # snap (always active)
        d = self.itt("snap", "First fix", "-m", "Root cause was X")
        self.assertEqual(d["result"]["status"], "active")
        self.assertEqual(d["result"]["rationale"], "Root cause was X")

        # inspect
        d = self.itt("inspect")
        self.assertEqual(d["workspace_status"], "active")
        self.assertEqual(d["intent"]["id"], intent_id)
        self.assertIsNotNone(d["latest_snap"])
        self.assertIn("active_decisions", d)

        # done
        d = self.itt("done")
        self.assertEqual(d["result"]["status"], "done")

        # inspect after done
        d = self.itt("inspect")
        self.assertEqual(d["workspace_status"], "idle")
        self.assertIsNone(d["intent"])

    # --- decision lifecycle ---

    def test_decision_lifecycle(self):
        self.itt("init")
        self.itt("start", "Task A")

        # create decision with active intent
        d = self.itt("decide", "Use PostgreSQL", "-m", "Team consensus")
        self.assertTrue(d["ok"])
        self.assertEqual(d["result"]["status"], "active")
        self.assertEqual(d["result"]["created_from_intent_id"], "intent-001")
        self.assertIn("intent-001", d["result"]["intent_ids"])
        decision_id = d["result"]["id"]

        # intent should have the decision attached
        d = self.itt("show", "intent-001")
        self.assertIn(decision_id, d["result"]["decision_ids"])

        # deprecate
        d = self.itt("deprecate", decision_id, "-m", "Switching to SQLite")
        self.assertEqual(d["result"]["status"], "deprecated")

    def test_decision_without_active_intent(self):
        self.itt("init")

        d = self.itt("decide", "Global convention")
        self.assertTrue(d["ok"])
        self.assertIsNone(d["result"]["created_from_intent_id"])
        self.assertEqual(d["result"]["intent_ids"], [])

    def test_deprecate_single_auto_selects(self):
        self.itt("init")
        self.itt("decide", "Only decision")

        d = self.itt("deprecate")
        self.assertEqual(d["result"]["status"], "deprecated")

    def test_deprecate_multiple_requires_id(self):
        self.itt("init")
        self.itt("decide", "Decision A")
        self.itt("decide", "Decision B")

        d, rc = self.itt_rc("deprecate")
        self.assertFalse(d["ok"])
        self.assertEqual(d["error"]["code"], "STATE_CONFLICT")

        d = self.itt("deprecate", "decision-001")
        self.assertEqual(d["result"]["status"], "deprecated")

    def test_deprecate_no_active_fails(self):
        self.itt("init")
        d, rc = self.itt_rc("deprecate")
        self.assertFalse(d["ok"])

    # --- auto-attach on start ---

    def test_start_attaches_active_decisions(self):
        self.itt("init")

        # create decisions without active intent
        self.itt("decide", "Decision 1")
        self.itt("decide", "Decision 2")

        # start intent — should attach both decisions
        d = self.itt("start", "New task")
        self.assertEqual(len(d["attached_decisions"]), 2)
        self.assertEqual(len(d["result"]["decision_ids"]), 2)

        # verify bidirectional: decisions should reference the intent
        d = self.itt("show", "decision-001")
        self.assertIn("intent-001", d["result"]["intent_ids"])

    # --- auto-attach on resume ---

    def test_resume_attaches_new_decisions(self):
        self.itt("init")
        self.itt("start", "Task A")
        self.itt("suspend")

        # create a decision while suspended
        self.itt("decide", "New decision during suspend")

        # resume — should pick up the new decision
        d = self.itt("resume")
        self.assertEqual(d["result"]["status"], "open")
        self.assertEqual(len(d["attached_decisions"]), 1)
        self.assertIn("decision-001", d["result"]["decision_ids"])

    # --- revert ---

    def test_revert(self):
        self.itt("init")
        self.itt("start", "Task")
        self.itt("snap", "Step 1")

        d = self.itt("revert", "-m", "Bad idea")
        self.assertEqual(d["result"]["status"], "reverted")

    def test_revert_without_active_snap_fails(self):
        self.itt("init")
        self.itt("start", "Task")

        d, rc = self.itt_rc("revert")
        self.assertFalse(d["ok"])
        self.assertEqual(d["error"]["code"], "STATE_CONFLICT")
        self.assertEqual(rc, 3)

    # --- intent lifecycle edge cases ---

    def test_start_while_open_fails(self):
        self.itt("init")
        self.itt("start", "First")

        d, rc = self.itt_rc("start", "Second")
        self.assertFalse(d["ok"])
        self.assertEqual(d["error"]["code"], "STATE_CONFLICT")

    def test_done_by_id(self):
        self.itt("init")
        self.itt("start", "A")
        self.itt("done")
        self.itt("start", "B")

        # close A by id (already done — should fail)
        d, rc = self.itt_rc("done", "intent-001")
        self.assertFalse(d["ok"])

    def test_done_when_idle_fails(self):
        self.itt("init")
        d, rc = self.itt_rc("done")
        self.assertFalse(d["ok"])

    # --- suspend and resume ---

    def test_suspend_and_resume(self):
        self.itt("init")
        self.itt("start", "Task A")

        # suspend
        d = self.itt("suspend")
        self.assertEqual(d["result"]["status"], "suspended")

        # workspace is idle
        d = self.itt("inspect")
        self.assertEqual(d["workspace_status"], "idle")
        self.assertEqual(len(d["suspended_intents"]), 1)

        # can start a new intent
        self.itt("start", "Task B")
        d = self.itt("inspect")
        self.assertEqual(d["intent"]["title"], "Task B")

        # done Task B
        self.itt("done")

        # resume Task A
        d = self.itt("resume")
        self.assertEqual(d["result"]["status"], "open")
        d = self.itt("inspect")
        self.assertEqual(d["intent"]["title"], "Task A")

    def test_suspend_when_idle_fails(self):
        self.itt("init")
        d, rc = self.itt_rc("suspend")
        self.assertFalse(d["ok"])

    def test_resume_when_active_fails(self):
        self.itt("init")
        self.itt("start", "A")
        self.itt("suspend")
        self.itt("start", "B")
        d, rc = self.itt_rc("resume", "intent-001")
        self.assertFalse(d["ok"])
        self.assertEqual(d["error"]["code"], "STATE_CONFLICT")

    def test_resume_multiple_requires_id(self):
        self.itt("init")
        self.itt("start", "A")
        self.itt("suspend")
        self.itt("start", "B")
        self.itt("suspend")

        # resume without id fails
        d, rc = self.itt_rc("resume")
        self.assertFalse(d["ok"])

        # resume with id works
        d = self.itt("resume", "intent-001")
        self.assertEqual(d["result"]["id"], "intent-001")
        self.assertEqual(d["result"]["status"], "open")

    # --- list and show ---

    def test_list_and_show(self):
        self.itt("init")
        self.itt("start", "Task")
        self.itt("snap", "Step 1")
        self.itt("snap", "Step 2")
        self.itt("decide", "A decision")

        d = self.itt("list", "snap")
        self.assertEqual(d["count"], 2)

        d = self.itt("list", "intent")
        self.assertEqual(d["count"], 1)

        d = self.itt("list", "decision")
        self.assertEqual(d["count"], 1)

        d = self.itt("show", "snap-001")
        self.assertEqual(d["result"]["title"], "Step 1")

        d = self.itt("show", "intent-001")
        self.assertEqual(d["result"]["title"], "Task")

        d = self.itt("show", "decision-001")
        self.assertEqual(d["result"]["title"], "A decision")

    def test_show_missing_object(self):
        self.itt("init")
        d, rc = self.itt_rc("show", "snap-999")
        self.assertFalse(d["ok"])
        self.assertEqual(d["error"]["code"], "OBJECT_NOT_FOUND")

    # --- inspect with decisions ---

    def test_inspect_shows_active_decisions(self):
        self.itt("init")
        self.itt("decide", "Global decision")
        self.itt("start", "Task")

        d = self.itt("inspect")
        self.assertEqual(len(d["active_decisions"]), 1)
        self.assertEqual(d["active_decisions"][0]["title"], "Global decision")
        self.assertNotIn("candidate_snaps", d)

    # --- json output ---

    def test_all_commands_output_json(self):
        self.itt("init")
        self.itt("decide", "D1")
        self.itt("start", "Task")

        for args in [
            ["inspect"],
            ["snap", "S1"],
            ["revert"],
            ["suspend"],
            ["resume"],
            ["list", "intent"],
            ["list", "snap"],
            ["list", "decision"],
            ["show", "intent-001"],
            ["show", "snap-001"],
            ["show", "decision-001"],
            ["deprecate"],
            ["done"],
            ["version"],
        ]:
            result = run_cli(self.cwd, *args)
            try:
                d = json.loads(result.stdout)
            except json.JSONDecodeError:
                self.fail(f"Command {args} did not output valid JSON: {result.stdout[:200]}")
            self.assertIn("ok", d, f"Command {args} missing 'ok' field")

    # --- version ---

    def test_version(self):
        d = self.itt("version")
        self.assertTrue(d["ok"])
        self.assertIn("version", d["result"])

    # --- not initialized ---

    def test_commands_fail_without_init(self):
        for args in [["start", "X"], ["snap", "X"], ["inspect"], ["done"], ["decide", "X"]]:
            d, rc = self.itt_rc(*args)
            self.assertFalse(d["ok"], f"Expected failure for {args}")
            self.assertEqual(d["error"]["code"], "NOT_INITIALIZED")

    # --- module entrypoint ---

    def test_module_entrypoint(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT / "src")
        result = subprocess.run(
            [sys.executable, "-m", "intent_cli", "version"],
            capture_output=True, text=True, env=env,
        )
        d = json.loads(result.stdout)
        self.assertTrue(d["ok"])

    # --- full three-object flow ---

    def test_full_three_object_flow(self):
        """init → decide → start → snap → done → deprecate → inspect"""
        self.itt("init")

        # decide before any intent
        d = self.itt("decide", "Use REST API", "-m", "Team standard")
        self.assertEqual(d["result"]["status"], "active")
        self.assertIsNone(d["result"]["created_from_intent_id"])

        # start — auto-attaches the decision
        d = self.itt("start", "Build user endpoint")
        self.assertEqual(len(d["attached_decisions"]), 1)
        self.assertIn("decision-001", d["result"]["decision_ids"])

        # snap
        d = self.itt("snap", "Implemented GET /users", "-m", "Basic CRUD")
        self.assertEqual(d["result"]["status"], "active")

        # done
        d = self.itt("done")
        self.assertEqual(d["result"]["status"], "done")

        # deprecate the decision
        d = self.itt("deprecate", "decision-001", "-m", "Switching to GraphQL")
        self.assertEqual(d["result"]["status"], "deprecated")

        # inspect — idle, no active decisions
        d = self.itt("inspect")
        self.assertEqual(d["workspace_status"], "idle")
        self.assertEqual(len(d["active_decisions"]), 0)


if __name__ == "__main__":
    unittest.main()
