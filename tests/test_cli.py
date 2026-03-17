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
SMOKE = ROOT / "scripts" / "smoke.sh"
DEMO = ROOT / "scripts" / "demo_log.sh"
AGENT_DEMO = ROOT / "scripts" / "demo_agent.sh"
INSTALL = ROOT / "setup" / "install.sh"


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


def run_module_cli(cwd: Path, *args: str, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    merged_env["PYTHONPATH"] = str(ROOT / "src")
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "intent_cli", *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        env=merged_env,
    )


def run_cli_json(
    cwd: Path,
    *args: str,
    env: Optional[Dict[str, str]] = None,
) -> tuple[subprocess.CompletedProcess[str], dict]:
    result = run_cli(cwd, *args, env=env)
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
    def make_repo(self, *, with_commit: bool = True, initialize_intent: bool = False) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name)
        init_git_repo(repo, with_commit=with_commit)
        if initialize_intent:
            init_result = run_cli(repo, "init")
            self.assertEqual(init_result.returncode, 0)
        return repo

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

    def test_version_flag_and_command_work_without_git(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            version_flag = run_cli(repo, "--version")
            self.assertEqual(version_flag.returncode, 0)
            self.assertIn("intent-cli 0.2.0rc1", version_flag.stdout)

            version_command = run_cli(repo, "version")
            self.assertEqual(version_command.returncode, 0)
            self.assertEqual(version_command.stdout.strip(), "intent-cli 0.2.0rc1")

            version_json = run_cli(repo, "version", "--json")
            self.assertEqual(version_json.returncode, 0)
            self.assertEqual(json.loads(version_json.stdout)["version"], "0.2.0rc1")

    def test_help_output_is_informative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            top_help = run_cli(repo, "--help")
            self.assertEqual(top_help.returncode, 0)
            self.assertIn("Intent CLI records semantic history on top of Git.", top_help.stdout)
            self.assertIn("checkpoint", top_help.stdout)
            self.assertIn("decision", top_help.stdout)
            self.assertIn("setup", top_help.stdout)
            self.assertIn("doctor", top_help.stdout)
            self.assertIn("integrations", top_help.stdout)

            checkpoint_help = run_cli(repo, "checkpoint", "--help")
            self.assertEqual(checkpoint_help.returncode, 0)
            self.assertIn("List checkpoints", checkpoint_help.stdout)

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

    def test_distribution_commands_work_without_git(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            home = repo / "home"
            intent_home = repo / "intent-home"
            codex_home = home / ".codex"
            codex_home.mkdir(parents=True)

            env = {
                "HOME": str(home),
                "INTENT_HOME": str(intent_home),
                "CODEX_HOME": str(codex_home),
            }

            list_result = run_cli(repo, "integrations", "list", "--json", env=env)
            self.assertEqual(list_result.returncode, 0)
            list_payload = json.loads(list_result.stdout)["result"]["integrations"]
            codex = next(item for item in list_payload if item["id"] == "codex")
            self.assertTrue(codex["detected"])
            self.assertTrue(codex["auto_install_supported"])
            self.assertEqual(codex["status"], "not_installed")

            setup_result = run_cli(repo, "setup", "--agent", "auto", "--json", env=env)
            self.assertEqual(setup_result.returncode, 0)
            setup_payload = json.loads(setup_result.stdout)
            self.assertEqual(setup_payload["result"]["selected_agent"], "codex")
            self.assertEqual(setup_payload["result"]["install_mode"], "skill_dir")
            self.assertEqual(setup_payload["result"]["repo_root"], str(ROOT))
            skill_root = Path(setup_payload["result"]["target_path"])
            self.assertTrue((skill_root / "SKILL.md").exists())

            second_setup = run_cli(repo, "setup", "codex", "--json", env=env)
            self.assertEqual(second_setup.returncode, 0)
            second_payload = json.loads(second_setup.stdout)
            self.assertTrue(second_payload["noop"])
            self.assertFalse(second_payload["state_changed"])

            doctor_result = run_cli(repo, "doctor", "--agent", "codex", "--json", env=env)
            self.assertEqual(doctor_result.returncode, 0)
            doctor_payload = json.loads(doctor_result.stdout)
            self.assertTrue(doctor_payload["ok"])
            self.assertEqual(doctor_payload["result"]["checks"][0]["status"], "installed")

    def test_setup_claude_installs_skill_into_global_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            home = repo / "home"
            intent_home = repo / "intent-home"
            claude_home = home / ".claude"
            claude_home.mkdir(parents=True)

            env = {
                "HOME": str(home),
                "INTENT_HOME": str(intent_home),
                "CLAUDE_HOME": str(claude_home),
            }

            setup_result = run_cli(repo, "setup", "claude", "--json", env=env)
            self.assertEqual(setup_result.returncode, 0)
            setup_payload = json.loads(setup_result.stdout)
            self.assertEqual(setup_payload["result"]["selected_agent"], "claude")
            self.assertTrue((claude_home / "skills" / "intent-cli" / "SKILL.md").exists())

            doctor_result = run_cli(repo, "doctor", "--agent", "claude", "--json", env=env)
            self.assertEqual(doctor_result.returncode, 0)
            self.assertTrue(json.loads(doctor_result.stdout)["ok"])

    def test_auto_setup_skips_manual_only_cursor_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            home = repo / "home"
            intent_home = repo / "intent-home"
            cursor_home = home / ".cursor"
            cursor_home.mkdir(parents=True)
            env = {
                "HOME": str(home),
                "INTENT_HOME": str(intent_home),
                "CURSOR_HOME": str(cursor_home),
            }

            setup_auto = run_cli(repo, "setup", "--agent", "auto", "--json", env=env)
            self.assertEqual(setup_auto.returncode, 0)
            auto_payload = json.loads(setup_auto.stdout)
            self.assertIsNone(auto_payload["result"]["selected_agent"])
            self.assertEqual(auto_payload["result"]["status"], "no_auto_installable_agent_detected")
            self.assertIn("cursor", auto_payload["result"]["manual_detected_agents"])

            setup_cursor = run_cli(repo, "setup", "cursor", "--json", env=env)
            self.assertEqual(setup_cursor.returncode, 0)
            cursor_payload = json.loads(setup_cursor.stdout)
            self.assertEqual(cursor_payload["result"]["selected_agent"], "cursor")
            self.assertEqual(cursor_payload["result"]["status"], "manual_helper_ready")
            helper_path = Path(cursor_payload["result"]["target_path"])
            self.assertTrue(helper_path.exists())
            self.assertEqual(helper_path, intent_home / "generated" / "cursor" / "intent.mdc")

            doctor_result = run_cli(repo, "doctor", "--agent", "cursor", "--json", env=env)
            self.assertEqual(doctor_result.returncode, 1)
            doctor_payload = json.loads(doctor_result.stdout)
            self.assertFalse(doctor_payload["ok"])
            self.assertEqual(doctor_payload["result"]["checks"][0]["status"], "manual_helper_ready")

    def test_install_script_supports_dry_run(self) -> None:
        result = subprocess.run(
            [str(INSTALL), "--agent", "codex", "--dry-run"],
            cwd=str(ROOT),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn(".intent/repo", result.stdout)
        self.assertIn(".intent/bin/itt", result.stdout)
        self.assertIn(".intent/repo/itt setup --agent codex", result.stdout)
        self.assertNotIn("pip install", result.stdout)

    def test_install_script_creates_repo_backed_launcher(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            codex_home = home / ".codex"
            codex_home.mkdir(parents=True)

            env = os.environ.copy()
            env.update(
                {
                    "HOME": str(home),
                    "SHELL": "/bin/zsh",
                    "CODEX_HOME": str(codex_home),
                }
            )

            result = subprocess.run(
                [str(INSTALL), "--agent", "codex"],
                cwd=str(ROOT),
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            intent_home = home / ".intent"
            repo_dir = intent_home / "repo"
            launcher = intent_home / "bin" / "itt"
            skill_file = codex_home / "skills" / "intent-cli" / "SKILL.md"
            rc_file = home / ".zshrc"

            self.assertTrue((repo_dir / "itt").exists())
            self.assertTrue(launcher.exists())
            self.assertEqual(launcher.resolve(), (repo_dir / "itt").resolve())
            self.assertTrue(skill_file.exists())
            self.assertTrue(rc_file.exists())
            self.assertIn(str(intent_home / "bin"), rc_file.read_text())

            launcher_result = subprocess.run(
                [str(launcher), "integrations", "list", "--json"],
                cwd=str(home),
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(launcher_result.returncode, 0, msg=launcher_result.stderr)
            launcher_payload = json.loads(launcher_result.stdout)
            self.assertEqual(launcher_payload["result"]["repo_root"], str(repo_dir))

    def test_show_selectors_resolve_active_current_and_latest_objects(self) -> None:
        repo = self.make_repo(initialize_intent=True)

        intent_result, intent_payload = run_cli_json(repo, "intent", "create", "--title", "Refine onboarding", "--json")
        self.assertEqual(intent_result.returncode, 0)
        intent_id = intent_payload["id"]

        checkpoint_result, checkpoint_payload = run_cli_json(
            repo,
            "checkpoint",
            "create",
            "--title",
            "Candidate A",
            "--json",
        )
        self.assertEqual(checkpoint_result.returncode, 0)
        checkpoint_id = checkpoint_payload["id"]

        active_intent = run_cli(repo, "intent", "show", "@active", "--json")
        self.assertEqual(active_intent.returncode, 0)
        self.assertEqual(json.loads(active_intent.stdout)["result"]["id"], intent_id)

        current_before_adopt = run_cli(repo, "checkpoint", "show", "@current", "--json")
        self.assertEqual(current_before_adopt.returncode, 0)
        self.assertEqual(json.loads(current_before_adopt.stdout)["result"]["id"], checkpoint_id)

        adoption_result, adoption_payload = run_cli_json(
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
        adoption_id = adoption_payload["id"]

        latest_adoption = run_cli(repo, "adoption", "show", "@latest", "--json")
        self.assertEqual(latest_adoption.returncode, 0)
        self.assertEqual(json.loads(latest_adoption.stdout)["result"]["id"], adoption_id)

        revert_result, revert_payload = run_cli_json(
            repo,
            "adoption",
            "revert",
            "--title",
            "Revert Candidate A",
            "--json",
        )
        self.assertEqual(revert_result.returncode, 0)

        latest_after_revert = run_cli(repo, "adoption", "show", "@latest", "--json")
        self.assertEqual(latest_after_revert.returncode, 0)
        self.assertEqual(json.loads(latest_after_revert.stdout)["result"]["id"], revert_payload["id"])

    def test_show_selectors_handle_missing_or_invalid_targets(self) -> None:
        repo = self.make_repo(initialize_intent=True)

        missing_current = run_cli(repo, "checkpoint", "show", "@current", "--json")
        self.assertEqual(missing_current.returncode, 4)
        missing_payload = json.loads(missing_current.stdout)
        self.assertEqual(missing_payload["error"]["code"], "OBJECT_NOT_FOUND")

        invalid_selector = run_cli(repo, "intent", "show", "@latest", "--json")
        self.assertEqual(invalid_selector.returncode, 2)
        invalid_payload = json.loads(invalid_selector.stdout)
        self.assertEqual(invalid_payload["error"]["code"], "INVALID_INPUT")

    def test_write_commands_accept_current_and_latest_selectors(self) -> None:
        repo = self.make_repo(initialize_intent=True)
        self.assertEqual(run_cli(repo, "start", "Refine onboarding").returncode, 0)

        checkpoint_id = json.loads(run_cli(repo, "snap", "Candidate A", "--json").stdout)["id"]

        adopt_result = run_cli(
            repo,
            "adopt",
            "--checkpoint",
            "@current",
            "-m",
            "Adopt current candidate",
            "--json",
        )
        self.assertEqual(adopt_result.returncode, 0)
        adopt_payload = json.loads(adopt_result.stdout)["result"]
        self.assertEqual(adopt_payload["checkpoint_id"], checkpoint_id)

        decide_result = run_cli(
            repo,
            "decide",
            "Keep the current adoption rationale",
            "--adoption",
            "@latest",
            "--json",
        )
        self.assertEqual(decide_result.returncode, 0)
        decide_payload = json.loads(decide_result.stdout)["result"]
        self.assertEqual(decide_payload["adoption_id"], adopt_payload["id"])
        self.assertEqual(decide_payload["checkpoint_id"], checkpoint_id)

    def test_adopt_conflict_error_surfaces_candidate_recovery(self) -> None:
        repo = self.make_repo(initialize_intent=True)
        self.assertEqual(run_cli(repo, "start", "Refine onboarding").returncode, 0)

        cp1 = json.loads(run_cli(repo, "snap", "Candidate A", "--json").stdout)["id"]
        cp2 = json.loads(run_cli(repo, "snap", "Candidate B", "--json").stdout)["id"]

        checkpoint_file = repo / ".intent" / "checkpoints" / f"{cp2}.json"
        checkpoint_payload = json.loads(checkpoint_file.read_text())
        checkpoint_payload["selected"] = False
        checkpoint_payload["updated_at"] = checkpoint_payload["created_at"]
        checkpoint_file.write_text(json.dumps(checkpoint_payload, indent=2) + "\n")

        conflict = run_cli(
            repo,
            "adopt",
            "--checkpoint",
            "@current",
            "-m",
            "Adopt candidate",
            "--json",
        )
        self.assertEqual(conflict.returncode, 3)
        conflict_payload = json.loads(conflict.stdout)
        self.assertEqual(conflict_payload["error"]["code"], "STATE_CONFLICT")
        self.assertEqual(conflict_payload["error"]["suggested_fix"], f"itt checkpoint select {cp2}")
        candidate_ids = [item["id"] for item in conflict_payload["error"]["details"]["candidate_checkpoints"]]
        self.assertEqual(candidate_ids, [cp2, cp1])

    def test_run_start_end_updates_state_and_links_new_objects(self) -> None:
        repo = self.make_repo(initialize_intent=True)
        intent_result, intent_payload = run_cli_json(repo, "start", "Refine onboarding", "--json")
        self.assertEqual(intent_result.returncode, 0)

        run_result, run_payload = run_cli_json(
            repo,
            "run",
            "start",
            "--title",
            "Agent exploration",
            "--json",
        )
        self.assertEqual(run_result.returncode, 0)
        run_id = run_payload["id"]
        self.assertEqual(run_payload["result"]["status"], "active")
        self.assertEqual(run_payload["result"]["intent_id"], intent_payload["id"])

        inspect_active = json.loads(run_cli(repo, "inspect", "--json").stdout)
        self.assertEqual(inspect_active["state"]["active_run_id"], run_id)
        self.assertEqual(inspect_active["active_run"]["id"], run_id)

        status_active = json.loads(run_cli(repo, "status", "--json").stdout)
        self.assertEqual(status_active["active_run"]["id"], run_id)

        run_list = run_cli(repo, "run", "list", "--json")
        self.assertEqual(run_list.returncode, 0)
        run_items = json.loads(run_list.stdout)["items"]
        self.assertEqual(len(run_items), 1)
        self.assertEqual(run_items[0]["id"], run_id)
        self.assertTrue(run_items[0]["is_active"])

        run_show = run_cli(repo, "run", "show", "@active", "--json")
        self.assertEqual(run_show.returncode, 0)
        self.assertEqual(json.loads(run_show.stdout)["result"]["id"], run_id)

        checkpoint_result, checkpoint_payload = run_cli_json(repo, "snap", "Candidate A", "--json")
        self.assertEqual(checkpoint_result.returncode, 0)
        checkpoint_id = checkpoint_payload["id"]
        self.assertEqual(checkpoint_payload["result"]["run_id"], run_id)

        adoption_result, adoption_payload = run_cli_json(
            repo,
            "adopt",
            "--checkpoint",
            checkpoint_id,
            "-m",
            "Adopt Candidate A",
            "--json",
        )
        self.assertEqual(adoption_result.returncode, 0)
        self.assertEqual(adoption_payload["result"]["run_id"], run_id)

        revert_result, revert_payload = run_cli_json(repo, "revert", "-m", "Revert Candidate A", "--json")
        self.assertEqual(revert_result.returncode, 0)
        self.assertEqual(revert_payload["result"]["run_id"], run_id)

        end_result, end_payload = run_cli_json(repo, "run", "end", "--json")
        self.assertEqual(end_result.returncode, 0)
        self.assertEqual(end_payload["id"], run_id)
        self.assertEqual(end_payload["result"]["status"], "completed")

        inspect_after_end = json.loads(run_cli(repo, "inspect", "--json").stdout)
        self.assertIsNone(inspect_after_end["state"]["active_run_id"])
        self.assertIsNone(inspect_after_end["active_run"])

        completed_run = run_cli(repo, "run", "show", run_id, "--json")
        self.assertEqual(completed_run.returncode, 0)
        self.assertEqual(json.loads(completed_run.stdout)["result"]["status"], "completed")

    def test_run_requires_active_intent_and_prevents_nested_runs(self) -> None:
        repo = self.make_repo(initialize_intent=True)

        no_intent = run_cli(repo, "run", "start", "--json")
        self.assertEqual(no_intent.returncode, 3)
        self.assertEqual(json.loads(no_intent.stdout)["error"]["code"], "STATE_CONFLICT")

        self.assertEqual(run_cli(repo, "start", "Refine onboarding").returncode, 0)

        first_run = run_cli(repo, "run", "start", "--id-only")
        self.assertEqual(first_run.returncode, 0)
        self.assertEqual(first_run.stdout.strip(), "run-001")

        start_while_run_active = run_cli(repo, "start", "Another intent", "--json")
        self.assertEqual(start_while_run_active.returncode, 3)
        self.assertEqual(json.loads(start_while_run_active.stdout)["error"]["code"], "STATE_CONFLICT")

        second_run = run_cli(repo, "run", "start", "--json")
        self.assertEqual(second_run.returncode, 3)
        self.assertEqual(json.loads(second_run.stdout)["error"]["code"], "STATE_CONFLICT")

        self.assertEqual(run_cli(repo, "run", "end").returncode, 0)

        no_active_run = run_cli(repo, "run", "end", "--json")
        self.assertEqual(no_active_run.returncode, 4)
        self.assertEqual(json.loads(no_active_run.stdout)["error"]["code"], "OBJECT_NOT_FOUND")

        missing_active_selector = run_cli(repo, "run", "show", "@active", "--json")
        self.assertEqual(missing_active_selector.returncode, 4)
        self.assertEqual(json.loads(missing_active_selector.stdout)["error"]["code"], "OBJECT_NOT_FOUND")

    def test_decision_create_defaults_to_latest_adoption_and_supports_read_side(self) -> None:
        repo = self.make_repo(initialize_intent=True)
        self.assertEqual(run_cli(repo, "start", "Refine onboarding").returncode, 0)
        checkpoint_id = json.loads(run_cli(repo, "snap", "Candidate A", "--json").stdout)["id"]
        adoption_id = json.loads(
            run_cli(
                repo,
                "adopt",
                "--checkpoint",
                checkpoint_id,
                "-m",
                "Adopt Candidate A",
                "--json",
            ).stdout
        )["id"]

        decision_result, decision_payload = run_cli_json(
            repo,
            "decide",
            "Prefer progressive disclosure",
            "--because",
            "Lower cognitive load for first-time users.",
            "--json",
        )
        self.assertEqual(decision_result.returncode, 0)
        decision_id = decision_payload["id"]
        self.assertEqual(decision_payload["result"]["adoption_id"], adoption_id)
        self.assertEqual(decision_payload["result"]["checkpoint_id"], checkpoint_id)

        decision_list = run_cli(repo, "decision", "list", "--json")
        self.assertEqual(decision_list.returncode, 0)
        decision_items = json.loads(decision_list.stdout)["items"]
        self.assertEqual(len(decision_items), 1)
        self.assertEqual(decision_items[0]["id"], decision_id)
        self.assertEqual(decision_items[0]["adoption_id"], adoption_id)

        decision_show = run_cli(repo, "decision", "show", "@latest", "--json")
        self.assertEqual(decision_show.returncode, 0)
        show_payload = json.loads(decision_show.stdout)["result"]
        self.assertEqual(show_payload["id"], decision_id)
        self.assertEqual(show_payload["rationale"], "Lower cognitive load for first-time users.")

        inspect_payload = json.loads(run_cli(repo, "inspect", "--json").stdout)
        self.assertEqual(inspect_payload["latest_decision"]["id"], decision_id)

        log_result = run_cli(repo, "log")
        self.assertEqual(log_result.returncode, 0)
        self.assertIn(f"Decision: {decision_id}  Prefer progressive disclosure", log_result.stdout)
        self.assertIn("Because: Lower cognitive load for first-time users.", log_result.stdout)

    def test_decision_create_can_exist_without_adoption_and_validates_explicit_adoption(self) -> None:
        repo = self.make_repo(initialize_intent=True)
        self.assertEqual(run_cli(repo, "start", "Refine onboarding").returncode, 0)

        no_adoption_decision = run_cli(
            repo,
            "decision",
            "create",
            "--title",
            "Keep the scope narrow",
            "--because",
            "Avoid adding platform concerns too early.",
            "--json",
        )
        self.assertEqual(no_adoption_decision.returncode, 0)
        no_adoption_payload = json.loads(no_adoption_decision.stdout)["result"]
        self.assertIsNone(no_adoption_payload["adoption_id"])
        self.assertIsNone(no_adoption_payload["checkpoint_id"])

        checkpoint_id = json.loads(run_cli(repo, "snap", "Candidate A", "--json").stdout)["id"]
        adoption_id = json.loads(
            run_cli(
                repo,
                "adopt",
                "--checkpoint",
                checkpoint_id,
                "-m",
                "Adopt Candidate A",
                "--json",
            ).stdout
        )["id"]

        self.assertEqual(run_cli(repo, "start", "Another problem").returncode, 0)

        wrong_intent = run_cli(
            repo,
            "decide",
            "Keep previous reasoning",
            "--adoption",
            adoption_id,
            "--json",
        )
        self.assertEqual(wrong_intent.returncode, 3)
        self.assertEqual(json.loads(wrong_intent.stdout)["error"]["code"], "STATE_CONFLICT")

        no_latest_in_new_intent = run_cli(repo, "decision", "show", "@latest", "--json")
        self.assertEqual(no_latest_in_new_intent.returncode, 4)
        self.assertEqual(json.loads(no_latest_in_new_intent.stdout)["error"]["code"], "OBJECT_NOT_FOUND")

    def test_log_shows_standalone_decisions_when_no_adoptions_exist(self) -> None:
        repo = self.make_repo(initialize_intent=True)
        self.assertEqual(run_cli(repo, "start", "Refine onboarding").returncode, 0)

        decision_result = run_cli(
            repo,
            "decide",
            "Keep the scope narrow",
            "--because",
            "Avoid adding platform concerns too early.",
            "--json",
        )
        self.assertEqual(decision_result.returncode, 0)
        decision_id = json.loads(decision_result.stdout)["id"]

        log_result = run_cli(repo, "log")
        self.assertEqual(log_result.returncode, 0)
        self.assertIn("Standalone decisions", log_result.stdout)
        self.assertIn(decision_id, log_result.stdout)
        self.assertIn("Because: Avoid adding platform concerns too early.", log_result.stdout)


if __name__ == "__main__":
    unittest.main()
