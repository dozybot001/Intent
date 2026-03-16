import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "itt"
SMOKE = ROOT / "scripts" / "smoke.sh"
DEMO = ROOT / "scripts" / "demo_log.sh"
AGENT_DEMO = ROOT / "scripts" / "demo_agent.sh"


def run_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )


def run_module_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "intent_cli", *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(ROOT / "src")},
    )


def run_cli_json(cwd: Path, *args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = run_cli(cwd, *args)
    return result, json.loads(result.stdout)


def init_git_repo(cwd: Path, *, with_commit: bool = True) -> None:
    subprocess.run(["git", "init"], cwd=str(cwd), check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "intent@example.com"], cwd=str(cwd), check=True)
    subprocess.run(["git", "config", "user.name", "Intent"], cwd=str(cwd), check=True)
    if with_commit:
        (cwd / "README.md").write_text("seed\n")
        subprocess.run(["git", "add", "README.md"], cwd=str(cwd), check=True)
        subprocess.run(["git", "commit", "-m", "seed"], cwd=str(cwd), check=True, capture_output=True, text=True)


class IntentCliTests(unittest.TestCase):
    def test_init_requires_git(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            result = run_cli(repo, "init")
            self.assertEqual(result.returncode, 1)
            self.assertIn("GIT_STATE_INVALID", result.stderr)

    def test_module_entrypoint_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_git_repo(repo, with_commit=False)
            result = run_module_cli(repo, "init")
            self.assertEqual(result.returncode, 0)
            self.assertTrue((repo / ".intent").exists())

    def test_init_and_status_idle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_git_repo(repo, with_commit=False)

            init_result = run_cli(repo, "init")
            self.assertEqual(init_result.returncode, 0)
            self.assertTrue((repo / ".intent" / "config.json").exists())
            self.assertTrue((repo / ".intent" / "state.json").exists())

            status_result = run_cli(repo, "status", "--json")
            self.assertEqual(status_result.returncode, 0)
            payload = json.loads(status_result.stdout)
            self.assertEqual(payload["workspace_status"], "idle")
            self.assertIsNone(payload["active_intent"])

    def test_not_initialized_status_errors_inside_git(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_git_repo(repo, with_commit=False)

            result = run_cli(repo, "status", "--json")
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["error"]["code"], "NOT_INITIALIZED")

    def test_status_and_log_require_git_repository(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            status_json = run_cli(repo, "status", "--json")
            self.assertEqual(status_json.returncode, 1)
            self.assertEqual(json.loads(status_json.stdout)["error"]["code"], "GIT_STATE_INVALID")

            log_text = run_cli(repo, "log")
            self.assertEqual(log_text.returncode, 1)
            self.assertIn("Intent requires a Git repository", log_text.stderr)
            self.assertIn("git init", log_text.stderr)

    def test_full_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_git_repo(repo)

            self.assertEqual(run_cli(repo, "init").returncode, 0)
            self.assertEqual(run_cli(repo, "start", "Reduce onboarding confusion").returncode, 0)
            snap_result = run_cli(repo, "snap", "Landing page candidate B", "--json")
            self.assertEqual(snap_result.returncode, 0)
            checkpoint = json.loads(snap_result.stdout)["result"]

            status_payload = json.loads(run_cli(repo, "status", "--json").stdout)
            self.assertEqual(status_payload["workspace_status"], "candidate_ready")
            self.assertEqual(status_payload["current_checkpoint"]["id"], checkpoint["id"])
            self.assertIsNone(status_payload["latest_adoption"])

            adopt_result = run_cli(
                repo,
                "adopt",
                "--checkpoint",
                checkpoint["id"],
                "-m",
                "Adopt progressive disclosure layout",
                "--json",
            )
            self.assertEqual(adopt_result.returncode, 0)
            adoption = json.loads(adopt_result.stdout)["result"]

            inspect_payload = json.loads(run_cli(repo, "inspect", "--json").stdout)
            self.assertEqual(inspect_payload["state"]["workspace_status"], "adoption_recorded")
            self.assertIsNone(inspect_payload["current_checkpoint"])
            self.assertEqual(inspect_payload["latest_adoption"]["id"], adoption["id"])

            checkpoint_file = repo / ".intent" / "checkpoints" / f"{checkpoint['id']}.json"
            checkpoint_payload = json.loads(checkpoint_file.read_text())
            self.assertEqual(checkpoint_payload["status"], "adopted")
            self.assertFalse(checkpoint_payload["selected"])

            log_result = run_cli(repo, "log")
            self.assertEqual(log_result.returncode, 0)
            self.assertIn(adoption["id"], log_result.stdout)

            revert_result = run_cli(repo, "revert", "-m", "Revert progressive disclosure layout", "--json")
            self.assertEqual(revert_result.returncode, 0)
            reverted = json.loads(revert_result.stdout)["result"]
            self.assertEqual(reverted["reverts_adoption_id"], adoption["id"])

            reverted_checkpoint = json.loads(checkpoint_file.read_text())
            self.assertEqual(reverted_checkpoint["status"], "reverted")
            self.assertFalse(reverted_checkpoint["adopted"])

    def test_checkpoint_select_and_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_git_repo(repo)
            self.assertEqual(run_cli(repo, "init").returncode, 0)
            self.assertEqual(run_cli(repo, "start", "Refine onboarding").returncode, 0)

            cp1 = json.loads(run_cli(repo, "snap", "Candidate A", "--json").stdout)["result"]["id"]
            cp2 = json.loads(run_cli(repo, "snap", "Candidate B", "--json").stdout)["result"]["id"]

            checkpoint_file = repo / ".intent" / "checkpoints" / f"{cp2}.json"
            checkpoint_payload = json.loads(checkpoint_file.read_text())
            checkpoint_payload["selected"] = False
            checkpoint_payload["updated_at"] = checkpoint_payload["created_at"]
            checkpoint_file.write_text(json.dumps(checkpoint_payload, indent=2) + "\n")

            status_payload = json.loads(run_cli(repo, "status", "--json").stdout)
            self.assertEqual(status_payload["workspace_status"], "conflict_multiple_candidates")
            self.assertTrue(status_payload["warnings"])
            self.assertTrue(
                any("Multiple candidate checkpoints exist" in warning for warning in status_payload["warnings"])
            )
            self.assertIsNone(status_payload["current_checkpoint"])

            select_result = run_cli(repo, "checkpoint", "select", cp1, "--json")
            self.assertEqual(select_result.returncode, 0)
            payload = json.loads(select_result.stdout)
            self.assertEqual(payload["id"], cp1)

    def test_status_and_write_json_include_machine_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_git_repo(repo)
            self.assertEqual(run_cli(repo, "init").returncode, 0)

            start_result, start_payload = run_cli_json(repo, "start", "Refine onboarding", "--json")
            self.assertEqual(start_result.returncode, 0)
            self.assertEqual(start_payload["workspace_status"], "intent_active")
            self.assertEqual(start_payload["next_action"]["args"], ["snap", "First candidate"])

            snap_result, snap_payload = run_cli_json(repo, "snap", "Candidate A", "--json")
            self.assertEqual(snap_result.returncode, 0)
            self.assertEqual(snap_payload["workspace_status"], "candidate_ready")
            self.assertEqual(
                snap_payload["next_action"]["args"],
                ["adopt", "--checkpoint", snap_payload["id"], "-m", "Adopt candidate"],
            )

            status_result, status_payload = run_cli_json(repo, "status", "--json")
            self.assertEqual(status_result.returncode, 0)
            self.assertEqual(status_payload["workspace_status"], "candidate_ready")
            self.assertIn("workspace_status_reason", status_payload)
            self.assertEqual(
                status_payload["next_action"]["args"],
                ["adopt", "--checkpoint", snap_payload["id"], "-m", "Adopt candidate"],
            )

    def test_inspect_json_rich_states_for_conflict_and_revert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_git_repo(repo)
            self.assertEqual(run_cli(repo, "init").returncode, 0)
            self.assertEqual(run_cli(repo, "start", "Refine onboarding").returncode, 0)

            cp1 = json.loads(run_cli(repo, "snap", "Candidate A", "--json").stdout)["id"]
            cp2 = json.loads(run_cli(repo, "snap", "Candidate B", "--json").stdout)["id"]

            checkpoint_file = repo / ".intent" / "checkpoints" / f"{cp2}.json"
            checkpoint_payload = json.loads(checkpoint_file.read_text())
            checkpoint_payload["selected"] = False
            checkpoint_payload["updated_at"] = checkpoint_payload["created_at"]
            checkpoint_file.write_text(json.dumps(checkpoint_payload, indent=2) + "\n")

            inspect_result, inspect_payload = run_cli_json(repo, "inspect", "--json")
            self.assertEqual(inspect_result.returncode, 0)
            self.assertEqual(inspect_payload["state"]["workspace_status"], "conflict_multiple_candidates")
            self.assertEqual(len(inspect_payload["candidate_checkpoints"]), 2)
            self.assertIsNone(inspect_payload["latest_event"])
            self.assertEqual(
                inspect_payload["suggested_next_actions"][0]["args"],
                ["checkpoint", "select", cp2],
            )

            self.assertEqual(run_cli(repo, "checkpoint", "select", cp2).returncode, 0)
            adopt_result, adopt_payload = run_cli_json(
                repo,
                "adopt",
                "--checkpoint",
                cp2,
                "-m",
                "Adopt Candidate B",
                "--json",
            )
            self.assertEqual(adopt_result.returncode, 0)

            revert_result, revert_payload = run_cli_json(repo, "revert", "-m", "Revert Candidate B", "--json")
            self.assertEqual(revert_result.returncode, 0)
            self.assertEqual(revert_payload["workspace_status"], "adoption_recorded")

            inspect_after_revert, reverted_payload = run_cli_json(repo, "inspect", "--json")
            self.assertEqual(inspect_after_revert.returncode, 0)
            self.assertEqual(reverted_payload["latest_event"]["type"], "revert")
            self.assertEqual(
                reverted_payload["latest_event"]["reverts_adoption_id"],
                adopt_payload["id"],
            )
            self.assertEqual(len(reverted_payload["candidate_checkpoints"]), 1)
            self.assertEqual(reverted_payload["candidate_checkpoints"][0]["id"], cp1)
            self.assertEqual(reverted_payload["suggested_next_actions"][0]["args"], ["log"])

    def test_id_only_matrix_for_write_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_git_repo(repo)
            self.assertEqual(run_cli(repo, "init").returncode, 0)

            start_id = run_cli(repo, "start", "Refine onboarding", "--id-only")
            self.assertEqual(start_id.returncode, 0)
            self.assertEqual(start_id.stdout.strip(), "intent-001")

            checkpoint_id = run_cli(repo, "snap", "Candidate A", "--id-only")
            self.assertEqual(checkpoint_id.returncode, 0)
            self.assertEqual(checkpoint_id.stdout.strip(), "cp-001")

            select_id = run_cli(repo, "checkpoint", "select", "cp-001", "--id-only")
            self.assertEqual(select_id.returncode, 0)
            self.assertEqual(select_id.stdout.strip(), "cp-001")

            adoption_id = run_cli(repo, "adopt", "--checkpoint", "cp-001", "--id-only")
            self.assertEqual(adoption_id.returncode, 0)
            self.assertEqual(adoption_id.stdout.strip(), "adopt-001")

            revert_id = run_cli(repo, "revert", "--id-only")
            self.assertEqual(revert_id.returncode, 0)
            self.assertEqual(revert_id.stdout.strip(), "adopt-002")

    def test_read_side_commands_and_config_show(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_git_repo(repo)
            self.assertEqual(run_cli(repo, "init").returncode, 0)

            empty_intents = run_cli(repo, "intent", "list", "--json")
            self.assertEqual(empty_intents.returncode, 0)
            self.assertEqual(json.loads(empty_intents.stdout)["items"], [])

            config_result = run_cli(repo, "config", "show", "--json")
            self.assertEqual(config_result.returncode, 0)
            config_payload = json.loads(config_result.stdout)
            self.assertEqual(config_payload["object"], "config")
            self.assertFalse(config_payload["result"]["git"]["strict_adoption"])

            intent_result = run_cli(repo, "start", "Refine onboarding", "--json")
            self.assertEqual(intent_result.returncode, 0)
            intent_id = json.loads(intent_result.stdout)["id"]

            checkpoint_result = run_cli(repo, "snap", "Candidate A", "--json")
            self.assertEqual(checkpoint_result.returncode, 0)
            checkpoint_id = json.loads(checkpoint_result.stdout)["id"]

            intent_list = run_cli(repo, "intent", "list", "--json")
            self.assertEqual(intent_list.returncode, 0)
            intent_items = json.loads(intent_list.stdout)["items"]
            self.assertEqual(len(intent_items), 1)
            self.assertEqual(intent_items[0]["id"], intent_id)
            self.assertTrue(intent_items[0]["is_active"])

            intent_show = run_cli(repo, "intent", "show", intent_id, "--json")
            self.assertEqual(intent_show.returncode, 0)
            self.assertEqual(json.loads(intent_show.stdout)["result"]["id"], intent_id)

            checkpoint_list = run_cli(repo, "checkpoint", "list", "--json")
            self.assertEqual(checkpoint_list.returncode, 0)
            checkpoint_items = json.loads(checkpoint_list.stdout)["items"]
            self.assertEqual(len(checkpoint_items), 1)
            self.assertEqual(checkpoint_items[0]["id"], checkpoint_id)
            self.assertTrue(checkpoint_items[0]["selected"])
            self.assertTrue(checkpoint_items[0]["is_current"])

            checkpoint_show = run_cli(repo, "checkpoint", "show", checkpoint_id)
            self.assertEqual(checkpoint_show.returncode, 0)
            self.assertIn(checkpoint_id, checkpoint_show.stdout)
            self.assertIn("Selected: true", checkpoint_show.stdout)

            adoption_result = run_cli(
                repo,
                "adoption",
                "create",
                "--checkpoint",
                checkpoint_id,
                "--title",
                "Adopt Candidate A",
                "--json",
            )
            self.assertEqual(adoption_result.returncode, 0)
            adoption_id = json.loads(adoption_result.stdout)["id"]

            adoption_list = run_cli(repo, "adoption", "list", "--json")
            self.assertEqual(adoption_list.returncode, 0)
            adoption_items = json.loads(adoption_list.stdout)["items"]
            self.assertEqual(len(adoption_items), 1)
            self.assertEqual(adoption_items[0]["id"], adoption_id)
            self.assertTrue(adoption_items[0]["is_latest"])

            adoption_show = run_cli(repo, "adoption", "show", adoption_id, "--json")
            self.assertEqual(adoption_show.returncode, 0)
            adoption_payload = json.loads(adoption_show.stdout)["result"]
            self.assertEqual(adoption_payload["checkpoint_id"], checkpoint_id)

    def test_show_missing_object_returns_object_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_git_repo(repo, with_commit=False)
            self.assertEqual(run_cli(repo, "init").returncode, 0)

            result = run_cli(repo, "intent", "show", "intent-999", "--json")
            self.assertEqual(result.returncode, 4)
            self.assertEqual(json.loads(result.stdout)["error"]["code"], "OBJECT_NOT_FOUND")

    def test_canonical_commands_match_surface_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_git_repo(repo)
            self.assertEqual(run_cli(repo, "init").returncode, 0)

            intent_result = run_cli(repo, "intent", "create", "--title", "Refine onboarding", "--json")
            self.assertEqual(intent_result.returncode, 0)
            intent_payload = json.loads(intent_result.stdout)
            self.assertEqual(intent_payload["object"], "intent")

            checkpoint_result = run_cli(
                repo,
                "checkpoint",
                "create",
                "--title",
                "Candidate A",
                "--json",
            )
            self.assertEqual(checkpoint_result.returncode, 0)
            checkpoint_id = json.loads(checkpoint_result.stdout)["id"]

            adoption_result = run_cli(
                repo,
                "adoption",
                "create",
                "--checkpoint",
                checkpoint_id,
                "--title",
                "Adopt Candidate A",
                "--json",
            )
            self.assertEqual(adoption_result.returncode, 0)
            adoption_payload = json.loads(adoption_result.stdout)
            self.assertEqual(adoption_payload["object"], "adoption")
            self.assertEqual(adoption_payload["result"]["title"], "Adopt Candidate A")

            revert_result = run_cli(
                repo,
                "adoption",
                "revert",
                "--title",
                "Revert Candidate A",
                "--json",
            )
            self.assertEqual(revert_result.returncode, 0)
            revert_payload = json.loads(revert_result.stdout)
            self.assertEqual(revert_payload["action"], "revert")
            self.assertEqual(revert_payload["result"]["title"], "Revert Candidate A")

    def test_if_not_adopted_returns_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_git_repo(repo)
            self.assertEqual(run_cli(repo, "init").returncode, 0)
            self.assertEqual(run_cli(repo, "start", "Refine onboarding").returncode, 0)
            checkpoint_id = json.loads(run_cli(repo, "snap", "Candidate A", "--json").stdout)["id"]

            first = run_cli(
                repo,
                "adoption",
                "create",
                "--checkpoint",
                checkpoint_id,
                "--title",
                "Adopt Candidate A",
                "--json",
            )
            self.assertEqual(first.returncode, 0)

            second = run_cli(
                repo,
                "adoption",
                "create",
                "--checkpoint",
                checkpoint_id,
                "--title",
                "Adopt Candidate A",
                "--if-not-adopted",
                "--json",
            )
            self.assertEqual(second.returncode, 0)
            payload = json.loads(second.stdout)
            self.assertTrue(payload["noop"])
            self.assertFalse(payload["state_changed"])
            self.assertEqual(payload["reason"], "Checkpoint already adopted")

    def test_invalid_link_git_returns_invalid_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_git_repo(repo)
            self.assertEqual(run_cli(repo, "init").returncode, 0)
            self.assertEqual(run_cli(repo, "start", "Refine onboarding").returncode, 0)
            checkpoint_id = json.loads(run_cli(repo, "snap", "Candidate A", "--json").stdout)["id"]

            result = run_cli(
                repo,
                "adopt",
                "--checkpoint",
                checkpoint_id,
                "-m",
                "Adopt Candidate A",
                "--link-git",
                "missing-ref",
                "--json",
            )
            self.assertEqual(result.returncode, 2)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["error"]["code"], "INVALID_INPUT")

    def test_explicit_git_linkage_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_git_repo(repo)
            self.assertEqual(run_cli(repo, "init").returncode, 0)
            self.assertEqual(run_cli(repo, "start", "Refine onboarding").returncode, 0)
            checkpoint_id = json.loads(run_cli(repo, "snap", "Candidate A", "--json").stdout)["id"]

            adoption = run_cli(
                repo,
                "adoption",
                "create",
                "--checkpoint",
                checkpoint_id,
                "--title",
                "Adopt Candidate A",
                "--link-git",
                "HEAD",
                "--json",
            )
            self.assertEqual(adoption.returncode, 0)
            payload = json.loads(adoption.stdout)
            self.assertEqual(payload["result"]["git"]["linkage_quality"], "explicit_ref")
            self.assertIsNotNone(payload["result"]["git"]["head"])

    def test_strict_adoption_requires_clean_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_git_repo(repo)
            self.assertEqual(run_cli(repo, "init").returncode, 0)
            self.assertEqual(run_cli(repo, "start", "Refine onboarding").returncode, 0)
            checkpoint_id = json.loads(run_cli(repo, "snap", "Candidate A", "--json").stdout)["id"]

            config_path = repo / ".intent" / "config.json"
            config_payload = json.loads(config_path.read_text())
            config_payload["git"]["strict_adoption"] = True
            config_path.write_text(json.dumps(config_payload, indent=2) + "\n")

            dirty_attempt = run_cli(
                repo,
                "adopt",
                "--checkpoint",
                checkpoint_id,
                "-m",
                "Adopt Candidate A",
                "--json",
            )
            self.assertEqual(dirty_attempt.returncode, 1)
            self.assertEqual(json.loads(dirty_attempt.stdout)["error"]["code"], "GIT_STATE_INVALID")

            subprocess.run(["git", "add", ".intent"], cwd=str(repo), check=True)
            subprocess.run(
                ["git", "commit", "-m", "track intent metadata"],
                cwd=str(repo),
                check=True,
                capture_output=True,
                text=True,
            )

            clean_attempt = run_cli(
                repo,
                "adopt",
                "--checkpoint",
                checkpoint_id,
                "-m",
                "Adopt Candidate A",
                "--json",
            )
            self.assertEqual(clean_attempt.returncode, 0)
            self.assertEqual(json.loads(clean_attempt.stdout)["result"]["status"], "active")

    def test_smoke_script_runs(self) -> None:
        result = subprocess.run(
            [str(SMOKE)],
            cwd=str(ROOT),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("Smoke test passed", result.stdout)

    def test_demo_log_script_runs(self) -> None:
        result = subprocess.run(
            [str(DEMO)],
            cwd=str(ROOT),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("== git log --oneline ==", result.stdout)
        self.assertIn("== itt log ==", result.stdout)

    def test_demo_agent_script_runs(self) -> None:
        result = subprocess.run(
            [str(AGENT_DEMO)],
            cwd=str(ROOT),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("== inspect ==", result.stdout)
        self.assertIn("== next action ==", result.stdout)
        self.assertIn("Agent demo complete", result.stdout)


if __name__ == "__main__":
    unittest.main()
