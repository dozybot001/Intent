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
        intent_id = d["result"]["id"]

        # snap (default = adopted)
        d = self.itt("snap", "First fix", "-m", "Root cause was X")
        self.assertEqual(d["result"]["status"], "adopted")
        self.assertEqual(d["result"]["rationale"], "Root cause was X")

        # inspect
        d = self.itt("inspect")
        self.assertEqual(d["workspace_status"], "active")
        self.assertEqual(d["intent"]["id"], intent_id)
        self.assertIsNotNone(d["latest_snap"])
        self.assertEqual(d["candidate_snaps"], [])

        # done
        d = self.itt("done")
        self.assertEqual(d["result"]["status"], "done")

        # inspect after done
        d = self.itt("inspect")
        self.assertEqual(d["workspace_status"], "idle")
        self.assertIsNone(d["intent"])

    # --- candidate workflow ---

    def test_candidate_workflow(self):
        self.itt("init")
        self.itt("start", "Choose approach")

        # create candidates
        d1 = self.itt("snap", "Option A", "--candidate")
        self.assertEqual(d1["result"]["status"], "candidate")
        d2 = self.itt("snap", "Option B", "--candidate")
        self.assertEqual(d2["result"]["status"], "candidate")

        # inspect shows candidates
        d = self.itt("inspect")
        self.assertEqual(len(d["candidate_snaps"]), 2)
        self.assertEqual(d["workspace_status"], "conflict")

        # adopt without id fails (multiple candidates)
        d, rc = self.itt_rc("adopt")
        self.assertFalse(d["ok"])
        self.assertEqual(d["error"]["code"], "STATE_CONFLICT")

        # adopt specific one
        d = self.itt("adopt", d2["result"]["id"], "-m", "B is better")
        self.assertEqual(d["result"]["status"], "adopted")
        self.assertEqual(d["result"]["rationale"], "B is better")

        # single candidate auto-adopts
        d = self.itt("inspect")
        self.assertEqual(len(d["candidate_snaps"]), 1)

    def test_adopt_single_candidate_auto_selects(self):
        self.itt("init")
        self.itt("start", "Task")
        self.itt("snap", "Only option", "--candidate")

        d = self.itt("adopt", "-m", "Obvious choice")
        self.assertEqual(d["result"]["status"], "adopted")

    # --- revert ---

    def test_revert(self):
        self.itt("init")
        self.itt("start", "Task")
        self.itt("snap", "Step 1")

        d = self.itt("revert", "-m", "Bad idea")
        self.assertEqual(d["result"]["status"], "reverted")

    def test_revert_without_adopted_fails(self):
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

    # --- list and show ---

    def test_list_and_show(self):
        self.itt("init")
        self.itt("start", "Task")
        self.itt("snap", "Step 1")
        self.itt("snap", "Step 2")

        d = self.itt("list", "snap")
        self.assertEqual(d["count"], 2)

        d = self.itt("list", "intent")
        self.assertEqual(d["count"], 1)

        d = self.itt("show", "snap-001")
        self.assertEqual(d["result"]["title"], "Step 1")

        d = self.itt("show", "intent-001")
        self.assertEqual(d["result"]["title"], "Task")

    def test_show_missing_object(self):
        self.itt("init")
        d, rc = self.itt_rc("show", "snap-999")
        self.assertFalse(d["ok"])
        self.assertEqual(d["error"]["code"], "OBJECT_NOT_FOUND")

    # --- json output ---

    def test_all_commands_output_json(self):
        self.itt("init")
        self.itt("start", "Task")

        for args in [
            ["inspect"],
            ["snap", "S1"],
            ["snap", "S2", "--candidate"],
            ["adopt"],
            ["revert"],
            ["list", "intent"],
            ["list", "snap"],
            ["show", "intent-001"],
            ["show", "snap-001"],
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
        for args in [["start", "X"], ["snap", "X"], ["inspect"], ["done"]]:
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


if __name__ == "__main__":
    unittest.main()
