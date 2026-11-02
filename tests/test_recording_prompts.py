"""A project where recording is not happening says so, and an agent asks about it only once."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SOURCE = Path(__file__).resolve().parents[1]
AGENT_VARIABLES = ("CLAUDECODE", "CODEX_THREAD_ID", "CODEX_SHELL", "CODEX_CI", "CODEX_INTERNAL_ORIGINATOR_OVERRIDE")
HOOKS_NOT_RUN = "hooks have not run here yet"


@pytest.fixture
def run(tmp_path):
    def run(root, *argv, agent=None, stdin=None):
        environment = {key: value for key, value in os.environ.items() if key not in AGENT_VARIABLES}
        environment.update({"PYTHONPATH": os.pathsep.join((str(SOURCE / "src"), str(SOURCE))),
                            "INTENT_CONFIG_HOME": str(tmp_path / "config"), **({agent: "1"} if agent else {})})
        process = subprocess.run([sys.executable, "-m", "intent_cli", *argv], cwd=root, env=environment,
                                 input=stdin, text=True, capture_output=True, timeout=10)
        return json.loads(process.stdout)
    return run


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    return root


def _warned(result):
    return [text for text in result["warnings"] if HOOKS_NOT_RUN in text]


def test_status_and_inspect_name_the_trust_step_until_a_hook_runs(run, project):
    assert run(project, "init", "--host", "claude-code", agent="CLAUDECODE")["ok"]
    [warning] = _warned(run(project, "status", agent="CLAUDECODE"))
    assert "/hooks" in warning
    assert run(project, "inspect", agent="CLAUDECODE")["notices"] == [warning]

    event = {"session_id": "s", "prompt_id": "p", "prompt": "hello", "cwd": str(project),
             "transcript_path": "", "permission_mode": "default", "hook_event_name": "UserPromptSubmit"}
    run_hook = ["maintenance", "hook", "--host", "claude-code", "--root", str(project)]
    assert "hookSpecificOutput" in run(project, *run_hook, stdin=json.dumps(event))

    assert not _warned(run(project, "status", agent="CLAUDECODE"))
    assert "notices" not in run(project, "inspect", agent="CLAUDECODE")


def test_a_host_without_hooks_here_is_told_to_install_them(run, project):
    assert run(project, "init", "--host", "codex")["ok"]
    [warning] = _warned(run(project, "status", agent="CLAUDECODE"))
    assert "itt maintenance on --host claude-code" in warning


def test_no_notice_once_recording_is_off_or_for_a_script(run, project):
    assert run(project, "init", "--host", "codex")["ok"]
    assert not _warned(run(project, "status"))
    assert "notices" not in run(project, "inspect")
    assert run(project, "maintenance", "off")["ok"]
    assert not _warned(run(project, "status", agent="CODEX_THREAD_ID"))


def test_an_agent_asks_once_and_a_no_is_remembered_outside_the_project(run, project):
    assert run(project, "maintenance", "status")["result"]["offer"] is True
    declined = run(project, "maintenance", "decline")
    assert declined["ok"] and declined["result"] == {"root": str(project.resolve()), "offer": False}
    assert run(project, "maintenance", "status")["result"]["offer"] is False
    assert not list(project.iterdir()), "a no leaves nothing in the project"
    assert run(project, "init", "--host", "codex")["ok"], "the owner can still start"


def test_a_project_with_intent_is_not_declined(run, project):
    assert run(project, "init", "--host", "codex")["ok"]
    result = run(project, "maintenance", "decline")
    assert result["error"]["code"] == "ALREADY_EXISTS" and "maintenance off" in result["error"]["suggested_fix"]


def test_a_broken_list_of_declined_projects_only_means_asking_again(run, project, tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "declined-projects.json").write_text("{not json", encoding="utf-8")
    assert run(project, "maintenance", "status")["result"]["offer"] is True
    assert run(project, "maintenance", "decline")["ok"]
    assert run(project, "maintenance", "status")["result"]["offer"] is False


def test_the_skill_teaches_both_prompts():
    for document in ("SKILL.md", "SKILL_CN.md"):
        text = (SOURCE / document).read_text(encoding="utf-8")
        assert "offer: true" in text and "itt maintenance decline" in text and "notices" in text
