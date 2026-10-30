"""Project isolation, quiet closure, recovery, replay and bounded hook work."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shlex
import shutil
import subprocess
import sys

import pytest

from intent_cli import store
from intent_cli import maintenance_hooks
from intent_cli.commands.maintenance import configure
from intent_cli.maintenance import MaintenanceError, MAX_TURNS, close_turn, read_state, set_enabled
from intent_cli.maintenance_hooks import (
    MAX_CONTEXT_BYTES, claude_hook_status, handle_event, hook_status, install_claude_hooks, install_hooks,
)


SOURCE = Path(__file__).resolve().parents[1]
CLAUDE_SETTINGS = Path(".claude") / "settings.local.json"


def cli(root, *argv, stdin=None):
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(SOURCE / "src"), str(SOURCE)))
    process = subprocess.run([sys.executable, "-m", "intent_cli", *argv], cwd=root,
                             env=environment, input=stdin, text=True, capture_output=True, timeout=10)
    result = json.loads(process.stdout)
    if argv[:2] != ("maintenance", "hook"):
        assert process.returncode == (0 if result["ok"] else 1), process.stderr
    return result


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    monkeypatch.chdir(root)
    base, error = store.init_workspace()
    assert error is None
    configure(base, True)
    return root, base


@pytest.fixture
def claude_project(tmp_path, monkeypatch):
    root = tmp_path / "claude project's root"
    root.mkdir()
    monkeypatch.chdir(root)
    base, error = store.init_workspace()
    assert error is None
    configure(base, True, "claude-code")
    return root, base


def event(root, name="UserPromptSubmit", turn="t1", session="s1", **extra):
    return {"cwd": str(root), "hook_event_name": name, "session_id": session, "turn_id": turn, **extra}


def claude_event(root, name="UserPromptSubmit", session="c1", prompt_id="p1", **extra):
    """Claude Code's documented hook input: no turn ID; prompt_id is absent in older releases."""
    payload = {"session_id": session, "transcript_path": str(root.parent / "transcript.jsonl"),
               "cwd": str(root), "permission_mode": "default", "hook_event_name": name}
    if prompt_id is not None:
        payload["prompt_id"] = prompt_id
    payload.update({"prompt": "Continue the task"} if name == "UserPromptSubmit" else {"stop_hook_active": False})
    return {**payload, **extra}


def claude(root, name="UserPromptSubmit", **extra):
    return handle_event(claude_event(root, name, **extra), root, "claude-code")


def begin(root, base, **extra):
    result = handle_event(event(root, **extra), root)
    assert "additionalContext" in result["hookSpecificOutput"]
    return next(reversed(read_state(base)["turns"]))


def intent(base, number=1, text="Verified project objective"):
    identifier = f"intent-{number:03}"
    value = {"id": identifier, "object": "intent", "created_at": datetime.now(timezone.utc).isoformat(),
             "what": text, "why": "Independent continuation boundary", "origin": "pytest",
             "status": "active", "decision_ids": [], "snap_ids": []}
    with store.workspace_write_lock(base):
        store.create_object(base, "intent", identifier, value)
    return identifier


def test_new_init_defaults_to_project_local_continuous_maintenance(tmp_path):
    result = cli(tmp_path, "init")
    assert result["ok"]
    assert result["result"]["maintenance"]["enabled"] is True
    assert result["result"]["maintenance"]["hooks"]["configured"] is True
    assert result["result"]["maintenance"]["hooks"]["enforcement"] == "not_attested"
    setup = result["result"]["maintenance"]["hooks"]["setup"]
    assert setup["review_argv"] == ["codex", "--cd", str(tmp_path.resolve())]
    assert setup["scope"] == "project"
    assert result["result"]["maintenance"]["hooks"]["host"] == "codex"
    assert not (tmp_path / ".claude").exists()
    assert cli(tmp_path, "maintenance", "status")["result"]["mode"] == "continuous"
    assert cli(tmp_path, "maintenance", "off")["result"]["enabled"] is False
    assert cli(tmp_path, "maintenance", "on")["result"]["enabled"] is True


def test_uninitialized_status_does_not_create_history(tmp_path):
    assert cli(tmp_path, "maintenance", "status")["result"]["enabled"] is False
    assert not (tmp_path / ".intent").exists()
    assert handle_event(event(tmp_path)) == {}


def test_legacy_histories_are_not_silently_enabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    base, _ = store.init_workspace()
    before = sorted(path.name for path in base.iterdir())
    assert not read_state(base)["enabled"]
    assert handle_event(event(tmp_path)) == {}
    assert sorted(path.name for path in base.iterdir()) == before
    assert cli(tmp_path, "maintenance", "status")["result"]["enabled"] is False


def test_project_switch_isolation_and_nested_cwd(project, tmp_path, monkeypatch):
    root, base = project
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    other_base, _ = store.init_workspace()
    configure(other_base, True)
    configure(base, False)
    assert read_state(other_base)["enabled"]
    disabled_before = (base / "maintenance.json").read_bytes()
    assert handle_event(event(root)) == {}
    assert (base / "maintenance.json").read_bytes() == disabled_before
    assert read_state(other_base)["turns"] == {}
    configure(base, True)
    nested = root / "src"
    nested.mkdir()
    handle_event(event(nested), root)
    assert len(read_state(base)["turns"]) == 1
    assert read_state(other_base)["turns"] == {}
    assert handle_event(event(other), root) == {}


def test_nested_git_project_does_not_inherit_parent_switch(project):
    root, base = project
    nested = root / "independent"
    nested.mkdir()
    (nested / ".git").mkdir()
    assert handle_event(event(nested), root) == {}
    assert not read_state(base)["turns"]


def test_independent_nested_semantic_root_does_not_inherit_parent_flag(project):
    root, base = project
    nested = root / "independent"
    nested.mkdir()
    assert cli(nested, "init")["ok"]
    assert cli(nested, "maintenance", "off")["ok"]
    assert read_state(base)["enabled"]
    assert handle_event(event(nested), root) == {}
    assert not read_state(base)["turns"]


def test_windows_command_parser_preserves_root_and_runtime_paths(monkeypatch):
    words = [r"C:\Program Files\Python\python.exe", "-m", "intent_cli", "maintenance", "hook",
             "--root", r"C:\Projects\semantic history"]
    handler = {"type": "command", "command": subprocess.list2cmdline(words)}
    with monkeypatch.context() as patch:
        patch.setattr(maintenance_hooks.os, "name", "nt")
        assert maintenance_hooks._command_words(handler) == words
        assert maintenance_hooks._our_handler(handler)


def test_install_preserves_unrelated_hooks_and_is_idempotent(project):
    root, _ = project
    path = root / ".codex" / "hooks.json"
    custom = {"description": "user hook configuration", "hooks": {
        "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "echo custom"}]}],
        "Stop": [{"hooks": [{"type": "command", "command": "echo other"}]}],
        "SessionStart": [{"hooks": [{"type": "command", "command": "echo start"}]}]}}
    path.write_text(json.dumps(custom))
    install_hooks(root)
    updated = json.loads(path.read_text())
    assert updated["description"] == custom["description"]
    assert updated["hooks"]["SessionStart"] == custom["hooks"]["SessionStart"]
    for name in ("Stop", "UserPromptSubmit"):
        assert updated["hooks"][name][0] == custom["hooks"][name][0]
        assert len(updated["hooks"][name]) == 2
    before = path.read_bytes()
    install_hooks(root)
    assert path.read_bytes() == before


def test_broken_hook_config_cannot_block_revocation(project):
    root, base = project
    hooks = root / ".codex" / "hooks.json"
    hooks.write_text("{")
    status = cli(root, "maintenance", "status")
    assert status["ok"] and status["result"]["enabled"]
    assert status["result"]["hooks"]["configuration_unavailable"] and status["warnings"]
    result = cli(root, "maintenance", "off")
    assert result["ok"] and not read_state(base)["enabled"]
    assert hooks.read_text() == "{"
    result = cli(root, "maintenance", "on")
    assert result["error"]["code"] == "HOOK_CONFIG_INVALID"
    assert not read_state(base)["enabled"]


def test_hook_status_requires_command_handler_scoped_to_this_root(project):
    root, _ = project
    path = root / ".codex" / "hooks.json"
    data = json.loads(path.read_text())
    data["hooks"]["Stop"][0]["hooks"][0]["command"] = None
    path.write_text(json.dumps(data))
    assert hook_status(root)["configured"] is False
    install_hooks(root)
    data = json.loads(path.read_text())
    data["hooks"]["Stop"][-1]["hooks"][0]["command"] += "/wrong-root"
    path.write_text(json.dumps(data))
    assert hook_status(root)["configured"] is False
    install_hooks(root)
    assert hook_status(root)["configured"] is True


def test_init_reports_unavailable_hooks_without_destroying_existing_config(tmp_path):
    directory = tmp_path / ".codex"
    directory.mkdir()
    (directory / "hooks.json").write_text("{")
    result = cli(tmp_path, "init")
    assert result["ok"]
    assert result["result"]["maintenance"]["enabled"]
    assert not result["result"]["maintenance"]["hooks"]["configured"]
    assert (directory / "hooks.json").read_text() == "{"


def test_entry_is_cached_and_does_not_store_raw_prompt(project, monkeypatch):
    root, base = project
    identifier = intent(base)
    original = store.load_graph_once
    reads = []
    monkeypatch.setattr(store, "load_graph_once", lambda *args, **kwargs: (reads.append(1), original(*args, **kwargs))[1])
    request = event(root, prompt="do not store this raw prompt or any secret transcript")
    first = handle_event(request, root)
    state_bytes = (base / "maintenance.json").read_bytes()
    second = handle_event(request, root)
    assert first == second and len(reads) == 1
    assert (base / "maintenance.json").read_bytes() == state_bytes
    assert b"do not store this raw prompt" not in state_bytes
    assert identifier in first["hookSpecificOutput"]["additionalContext"]


def test_quiet_noop_has_a_receipt_without_semantic_objects(project):
    root, base = project
    key = begin(root, base)
    result = cli(root, "maintenance", "close", "no-op", "--turn", key, "--reason", "Only inspected existing facts")
    assert result["ok"] and result["result"]["objects"] == []
    assert not cli(root, "maintenance", "close", "no-op", "--turn", key, "--reason", "Only inspected existing facts")["result"]["changed"]
    assert handle_event(event(root, "Stop"), root) == {}
    assert read_state(base)["turns"][key]["stop_checked"] is True
    assert cli(root, "maintenance", "status")["result"]["observations"]["stop_checked_receipt"] is True
    assert all(not list((base / subdir).iterdir()) for subdir in store.SUBDIRS.values())


def test_recorded_receipt_requires_verified_changed_objects(project):
    root, base = project
    old = intent(base)
    key = begin(root, base)
    with pytest.raises(MaintenanceError, match="changed"):
        close_turn(base, key, "recorded", "", [old])
    new = intent(base, 2)
    result = close_turn(base, key, "recorded", "", [new])
    assert result["verified"] and result["objects"] == [new]
    assert handle_event(event(root, "Stop"), root) == {}


def test_receipt_is_bound_to_project_and_turn(project, tmp_path):
    root, base = project
    key = begin(root, base)
    with pytest.raises(MaintenanceError):
        close_turn(base, "../outside", "no-op", "read only", None)
    other = tmp_path / "other"
    other.mkdir()
    cli(other, "init")
    result = cli(other, "maintenance", "close", "no-op", "--turn", key, "--reason", "read only")
    assert result["error"]["code"] == "TURN_NOT_ACTIVE"
    assert read_state(base)["turns"][key]["receipt"] is None


def test_stop_retry_maps_new_host_turn_to_original_obligation(project):
    root, base = project
    key = begin(root, base)
    retry = handle_event(event(root, "Stop"), root)
    assert retry["decision"] == "block"
    continued = event(root, turn="continued", prompt=retry["reason"])
    handle_event(continued, root)
    state = read_state(base)
    assert len(state["turns"]) == 1
    assert state["turns"][key]["aliases"] == ["continued"]
    close_turn(base, key, "no-op", "No continuation-critical change", None)
    assert handle_event(event(root, "Stop", turn="continued", stop_hook_active=True), root) == {}


def test_duplicate_events_never_reset_retry_budget(project):
    root, base = project
    key = begin(root, base)
    first = handle_event(event(root, "Stop"), root)
    second = handle_event(event(root, "Stop"), root)
    assert first["decision"] == "block" and "decision" not in second
    assert "incomplete" in second["systemMessage"]
    continued = event(root, turn="continued", prompt=first["reason"])
    handle_event(continued, root)
    handle_event(continued, root)
    stop = handle_event(event(root, "Stop", turn="continued", stop_hook_active=True), root)
    assert "decision" not in stop
    assert read_state(base)["turns"][key]["retry_count"] == 1
    assert len(read_state(base)["turns"]) == 1


def test_host_continuation_guard_and_missing_entry_are_not_infinite(project):
    root, base = project
    assert "decision" not in handle_event(event(root, "Stop"), root)
    begin(root, base)
    assert "decision" not in handle_event(event(root, "Stop", stop_hook_active=True), root)


def test_verified_receipt_detects_later_object_changes(project):
    root, base = project
    key = begin(root, base)
    identifier = intent(base)
    close_turn(base, key, "recorded", "", [identifier])
    with store.workspace_write_lock(base):
        value = store.read_object(base, "intent", identifier)
        value["status"] = "suspend"
        store.update_object(base, "intent", identifier, value)
    assert handle_event(event(root, "Stop"), root)["decision"] == "block"
    close_turn(base, key, "failed", "Latest state was not reverified", None)
    result = handle_event(event(root, "Stop", stop_hook_active=True), root)
    assert "failed" in result["systemMessage"] and "decision" not in result


def test_damaged_history_can_acknowledge_failure_without_fake_snap(project):
    root, base = project
    path = base / "intents" / "intent-001.json"
    path.write_text("{")
    key = begin(root, base)
    assert read_state(base)["turns"][key]["baseline"] is None
    close_turn(base, key, "failed", "Stored JSON is truncated", None)
    assert "failed" in handle_event(event(root, "Stop"), root)["systemMessage"]
    assert path.read_text() == "{" and not list((base / "snaps").iterdir())


def test_recovered_history_can_record_verified_new_objects_same_turn(project):
    root, base = project
    path = base / "intents" / "intent-001.json"
    path.write_text("{")
    key = begin(root, base)
    # Fixture-only restoration models an independently authorized repair.
    path.unlink()
    identifier = intent(base)
    assert close_turn(base, key, "recorded", "", [identifier])["verified"]
    assert handle_event(event(root, "Stop"), root) == {}


def test_mid_turn_off_takes_precedence_and_reenable_invalidates_old_receipt(project):
    root, base = project
    key = begin(root, base)
    configure(base, False)
    assert handle_event(event(root, "Stop"), root) == {}
    configure(base, True)
    with pytest.raises(MaintenanceError):
        close_turn(base, key, "no-op", "Old authorization", None)
    assert "decision" not in handle_event(event(root, "Stop"), root)


def test_concurrent_replayed_hooks_make_one_entry_and_one_retry(project):
    root, base = project
    with ThreadPoolExecutor(max_workers=2) as pool:
        entries = list(pool.map(lambda _: handle_event(event(root), root), range(2)))
    assert entries[0] == entries[1] and len(read_state(base)["turns"]) == 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        stops = list(pool.map(lambda _: handle_event(event(root, "Stop"), root), range(2)))
    assert sum(result.get("decision") == "block" for result in stops) == 1


def test_two_sessions_have_independent_closure(project):
    root, base = project
    first = begin(root, base, session="one")
    second = begin(root, base, session="two")
    close_turn(base, first, "no-op", "Only a question", None)
    assert handle_event(event(root, "Stop", session="one"), root) == {}
    assert handle_event(event(root, "Stop", session="two"), root)["decision"] == "block"
    assert read_state(base)["turns"][second]["receipt"] is None


def test_entry_context_is_bounded_and_clipping_is_explicit(project):
    root, base = project
    for number in range(1, 18):
        intent(base, number, text="Long verified fact " * 200)
    output = handle_event(event(root), root)["hookSpecificOutput"]["additionalContext"]
    assert len(output.encode("utf-8")) <= MAX_CONTEXT_BYTES
    assert '"context_truncated": true' in output
    assert "Inspect the selected Intent" in output


def test_entry_context_carries_bounded_latest_checkpoint(project):
    root, base = project
    intent(base)
    snap = {"id": "snap-001", "object": "snap", "created_at": datetime.now(timezone.utc).isoformat(),
            "what": "Verified milestone", "why": "", "origin": "pytest", "intent_id": "intent-001",
            "checkpoint": {"next": "review the publisher", "constraints": "c" * 900}}
    with store.workspace_write_lock(base):
        store.create_object(base, "snap", "snap-001", snap)
        linked = store.read_object(base, "intent", "intent-001")
        linked["snap_ids"].append("snap-001")
        store.update_object(base, "intent", "intent-001", linked)
    output = handle_event(event(root), root)["hookSpecificOutput"]["additionalContext"]
    records = json.loads(output[output.index("{"):])
    latest = records["active_intents"][0]["latest_snap"]
    assert latest["checkpoint"] == {"next": "review the publisher", "constraints": "c" * 800}
    assert records["context_truncated"] is True


def test_receipt_retention_is_bounded(project):
    root, base = project
    for number in range(MAX_TURNS + 3):
        key = begin(root, base, turn=f"turn-{number}")
        close_turn(base, key, "no-op", "No new semantic facts", None)
    assert len(read_state(base)["turns"]) == MAX_TURNS
    assert handle_event(event(root, "Stop", turn=f"turn-{MAX_TURNS + 2}"), root) == {}


@pytest.mark.parametrize("content", ["{", "[]", '{"version":true,"enabled":true,"generation":0,"turns":{}}'])
def test_bad_metadata_follows_json_error_contract(project, content):
    root, base = project
    (base / "maintenance.json").write_text(content)
    result = cli(root, "maintenance", "status")
    assert result["error"]["code"] == "MAINTENANCE_STATE_INVALID"
    result = cli(root, "maintenance", "hook", "--root", str(root), stdin=json.dumps(event(root)))
    assert "systemMessage" in result and "decision" not in result


def test_metadata_symlink_cannot_write_outside_project(project, tmp_path):
    root, base = project
    outside = tmp_path / "outside.json"
    outside.write_text("untouched")
    path = base / "maintenance.json"
    path.unlink()
    path.symlink_to(outside)
    result = cli(root, "maintenance", "off")
    assert result["error"]["code"] == "UNSAFE_STORAGE"
    assert outside.read_text() == "untouched"


def test_hook_directory_symlink_is_not_followed(tmp_path, monkeypatch):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / ".codex").symlink_to(outside, target_is_directory=True)
    monkeypatch.chdir(root)
    result = cli(root, "init")
    assert result["ok"] and not result["result"]["maintenance"]["hooks"]["configured"]
    assert list(outside.iterdir()) == []


def test_oversized_and_invalid_hook_events_release_main_work(project):
    root, _ = project
    for payload in ("{", "x" * (256 * 1024 + 1)):
        result = cli(root, "maintenance", "hook", "--root", str(root), stdin=payload)
        assert "systemMessage" in result and "decision" not in result
    assert handle_event(event(root, session=123), root).get("systemMessage")


# ---- Claude Code host ----

def intent_handler_words(settings, name):
    return [shlex.split(handler["command"]) for group in settings["hooks"][name] for handler in group["hooks"]
            if shlex.split(handler["command"])[1:5] == ["-m", "intent_cli", "maintenance", "hook"]]


def test_claude_code_host_is_explicit_and_leaves_codex_untouched(tmp_path):
    result = cli(tmp_path, "init", "--host", "claude-code")
    hooks = result["result"]["maintenance"]["hooks"]
    assert hooks["host"] == "claude-code" and hooks["configured"] and hooks["enforcement"] == "not_attested"
    assert hooks["setup"]["review_cwd"] == str(tmp_path.resolve()) and hooks["setup"]["review_argv"] == ["claude"]
    assert any("Claude Code" in warning for warning in result["warnings"])
    assert not (tmp_path / ".codex").exists()
    settings = json.loads((tmp_path / CLAUDE_SETTINGS).read_text())
    for name in ("UserPromptSubmit", "Stop"):
        [words] = intent_handler_words(settings, name)
        assert words[1:] == ["-m", "intent_cli", "maintenance", "hook", "--host", "claude-code",
                             "--root", str(tmp_path.resolve())]
    status = cli(tmp_path, "maintenance", "status", "--host", "claude-code")["result"]
    assert status["hooks"]["configured"] and not status["observations"]["entry_seen"]
    # Without --host, status reports the host this project is configured for.
    assert cli(tmp_path, "maintenance", "status")["result"]["hooks"]["host"] == "claude-code"
    assert cli(tmp_path, "maintenance", "status", "--host", "codex")["result"]["hooks"]["configured"] is False


@pytest.mark.parametrize("environment, folders, expected", [
    ({"CLAUDECODE": "1"}, (), "claude-code"),
    ({"CODEX_THREAD_ID": "t"}, (".claude",), "codex"),
    ({}, (".claude",), "claude-code"),
    ({}, (".codex",), "codex"),
    ({}, (".codex", ".claude"), "codex"),  # ambiguous without a terminal to ask: the documented default
])
def test_init_picks_the_agent_in_use(tmp_path, monkeypatch, environment, folders, expected):
    home = tmp_path / "home"
    for folder in folders:
        (home / folder).mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    project = tmp_path / "project"
    project.mkdir()
    result = cli(project, "init")
    assert result["result"]["maintenance"]["hooks"]["host"] == expected


def test_claude_merge_preserves_settings_and_off_removes_only_intent_entries(tmp_path):
    path = tmp_path / CLAUDE_SETTINGS
    path.parent.mkdir()
    stale = {"type": "command", "command": "/old/python -m intent_cli maintenance hook --host claude-code --root /old"}
    custom = {"permissions": {"allow": ["Bash(npm test)"]}, "env": {"FOO": "1"}, "hooks": {
        "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "echo custom"}, stale]}],
        "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "echo pre"}]}],
        "Stop": [{"hooks": [stale]}]}}
    path.write_text(json.dumps(custom))
    assert cli(tmp_path, "init", "--host", "claude-code")["ok"]
    updated = json.loads(path.read_text())
    assert {key: updated[key] for key in ("permissions", "env")} == {key: custom[key] for key in ("permissions", "env")}
    assert updated["hooks"]["PreToolUse"] == custom["hooks"]["PreToolUse"]
    assert updated["hooks"]["UserPromptSubmit"][0] == {"hooks": [{"type": "command", "command": "echo custom"}]}
    assert [len(intent_handler_words(updated, name)) for name in ("UserPromptSubmit", "Stop")] == [1, 1]
    assert len(updated["hooks"]["Stop"]) == 1
    before = path.read_bytes()
    assert cli(tmp_path, "maintenance", "on", "--host", "claude-code")["ok"]
    assert path.read_bytes() == before
    result = cli(tmp_path, "maintenance", "off")
    assert result["ok"] and not result["result"]["enabled"]
    assert json.loads(path.read_text()) == {
        "permissions": custom["permissions"], "env": custom["env"], "hooks": {
            "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "echo custom"}]}],
            "PreToolUse": custom["hooks"]["PreToolUse"]}}


def test_claude_off_deletes_only_a_settings_file_left_empty(tmp_path):
    (tmp_path / ".codex").mkdir()
    assert cli(tmp_path, "init")["ok"]
    codex = (tmp_path / ".codex" / "hooks.json").read_bytes()
    assert cli(tmp_path, "maintenance", "on", "--host", "claude-code")["result"]["hooks"]["configured"]
    assert cli(tmp_path, "maintenance", "off", "--host", "claude-code")["result"]["hooks"]["configured"] is False
    assert not (tmp_path / ".claude").exists()
    assert (tmp_path / ".codex" / "hooks.json").read_bytes() == codex
    assert cli(tmp_path, "maintenance", "on", "--host", "claude-code")["result"]["hooks"]["configured"]


def test_broken_claude_settings_cannot_block_revocation(claude_project):
    root, base = claude_project
    path = root / CLAUDE_SETTINGS
    path.write_text("{")
    status = cli(root, "maintenance", "status", "--host", "claude-code")
    assert status["result"]["hooks"]["configuration_unavailable"] and status["warnings"]
    result = cli(root, "maintenance", "off", "--host", "claude-code")
    assert result["ok"] and not read_state(base)["enabled"]
    assert result["result"]["hooks"]["configuration_unavailable"] and path.read_text() == "{"
    assert cli(root, "maintenance", "on", "--host", "claude-code")["error"]["code"] == "HOOK_CONFIG_INVALID"
    assert not read_state(base)["enabled"]


def test_claude_settings_directory_symlink_is_not_followed(tmp_path):
    root, outside = tmp_path / "root", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / ".claude").symlink_to(outside, target_is_directory=True)
    result = cli(root, "init", "--host", "claude-code")
    assert result["ok"] and not result["result"]["maintenance"]["hooks"]["configured"]
    assert list(outside.iterdir()) == []


def test_claude_status_requires_handlers_scoped_to_this_root(claude_project):
    root, _ = claude_project
    path = root / CLAUDE_SETTINGS
    data = json.loads(path.read_text())
    data["hooks"]["Stop"][0]["hooks"][0]["command"] += "/elsewhere"
    path.write_text(json.dumps(data))
    assert claude_hook_status(root)["configured"] is False
    install_claude_hooks(root)
    data = json.loads(path.read_text())
    assert claude_hook_status(root)["configured"] is True and len(data["hooks"]["Stop"]) == 1
    data["disableAllHooks"] = True
    path.write_text(json.dumps(data))
    assert claude_hook_status(root)["blocked_by"] == "disableAllHooks"


def test_claude_entry_issues_token_and_stop_allows_one_closure_retry(claude_project):
    root, base = claude_project
    context = claude(root)["hookSpecificOutput"]["additionalContext"]
    [key] = read_state(base)["turns"]
    assert f"--turn {key}" in context and read_state(base)["turns"][key]["host"] == "claude-code"
    retry = claude(root, "Stop")
    assert retry["decision"] == "block" and f"--turn {key}" in retry["reason"]
    # The blocked Stop continues the same Claude Code turn without a new prompt.
    close_turn(base, key, "no-op", "Only answered a question", None)
    assert claude(root, "Stop", stop_hook_active=True) == {}
    assert read_state(base)["turns"][key]["stop_checked"] is True
    observations = cli(root, "maintenance", "status", "--host", "claude-code")["result"]["observations"]
    assert observations["entry_seen"] and observations["stop_checked_receipt"]
    assert cli(root, "maintenance", "status", "--host", "codex")["result"]["observations"]["entry_seen"] is False


def test_claude_missing_receipt_releases_after_one_retry(claude_project):
    root, base = claude_project
    claude(root)
    assert claude(root, "Stop")["decision"] == "block"
    released = claude(root, "Stop", stop_hook_active=True)
    assert "decision" not in released and "incomplete" in released["systemMessage"]
    assert "decision" not in claude(root, "Stop", session="never-started")
    assert claude(root, session="")["systemMessage"]


def test_claude_prompt_id_is_the_turn_identity(claude_project):
    root, base = claude_project
    first = claude(root, prompt="same words", prompt_id="p1")
    assert claude(root, prompt="same words", prompt_id="p1") == first
    [p1] = read_state(base)["turns"]
    close_turn(base, p1, "no-op", "Read only", None)
    claude(root, prompt="same words", prompt_id="p2")
    p2 = list(read_state(base)["turns"])[-1]
    assert p2 != p1 and len(read_state(base)["turns"]) == 2
    # An exact prompt_id match wins over recency; the open p2 turn still gates.
    assert claude(root, "Stop", prompt_id="p1") == {}
    assert claude(root, "Stop", prompt_id="p2")["decision"] == "block"
    assert b"same words" not in (base / "maintenance.json").read_bytes()


def test_claude_without_prompt_id_each_prompt_is_new_and_stop_closes_the_latest(claude_project):
    root, base = claude_project
    claude(root, prompt_id=None)
    [first] = read_state(base)["turns"]
    close_turn(base, first, "no-op", "Read only", None)
    assert claude(root, "Stop", prompt_id=None) == {}
    claude(root, prompt_id=None)
    second = list(read_state(base)["turns"])[-1]
    assert second != first and claude(root, "Stop", prompt_id=None)["decision"] == "block"
    # An unmatched prompt_id (its entry hook never ran) also falls back to the latest turn.
    assert "incomplete" in claude(root, "Stop", prompt_id="unseen", stop_hook_active=True)["systemMessage"]
    claude(root, session="parallel", prompt_id=None)
    third = list(read_state(base)["turns"])[-1]
    close_turn(base, third, "no-op", "Separate session", None)
    assert claude(root, "Stop", session="parallel", prompt_id=None) == {}


def test_claude_plan_mode_turns_are_not_gated(claude_project):
    root, base = claude_project
    context = claude(root, permission_mode="plan")["hookSpecificOutput"]["additionalContext"]
    assert "Plan mode is read-only" in context
    assert claude(root, "Stop", permission_mode="plan") == {}
    [key] = read_state(base)["turns"]
    assert read_state(base)["turns"][key]["retry_count"] == 0
    # Leaving plan mode inside the same turn restores the normal closure check.
    assert claude(root, "Stop", permission_mode="acceptEdits")["decision"] == "block"


def test_windows_claude_command_uses_a_git_bash_executable_path(monkeypatch):
    root = PureWindowsPath(r"C:\Projects\semantic history")
    with monkeypatch.context() as patch:
        patch.setattr(maintenance_hooks.os, "name", "nt")
        patch.setattr(maintenance_hooks.sys, "executable", r"C:\Program Files\Python\python.exe")
        handler = {"type": "command", "command": maintenance_hooks._claude_command(root)}
        assert shlex.split(handler["command"]) == [
            "C:/Program Files/Python/python.exe", "-m", "intent_cli", "maintenance", "hook",
            "--host", "claude-code", "--root", str(root)]
        assert maintenance_hooks._our_handler(handler, posix=True)


def test_claude_entry_context_stays_below_the_host_cap(claude_project):
    root, base = claude_project
    for number in range(1, 18):
        intent(base, number, text="Long verified fact " * 200)
    output = claude(root)["hookSpecificOutput"]["additionalContext"]
    assert len(output) < 10000 and '"context_truncated": true' in output


def test_codex_and_claude_turns_stay_separate(project):
    root, base = project
    begin(root, base)
    assert configure(base, True, "claude-code")["hooks"]["configured"]
    # The flag is shared, but a Claude Code Stop never closes a Codex turn.
    assert "decision" not in claude(root, "Stop", session="s1")
    assert handle_event(event(root, "Stop"), root)["decision"] == "block"


@pytest.mark.skipif(os.name == "nt", reason="POSIX shell quoting check")
def test_installed_claude_command_runs_through_a_shell(claude_project):
    root, base = claude_project
    settings = json.loads((root / CLAUDE_SETTINGS).read_text())
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join((str(SOURCE / "src"), str(SOURCE)))

    def run(name, payload):
        [group] = settings["hooks"][name]
        process = subprocess.run(["/bin/sh", "-c", group["hooks"][0]["command"]], input=json.dumps(payload),
                                 env=environment, text=True, capture_output=True, timeout=10, cwd=root)
        assert process.returncode == 0, process.stderr
        return json.loads(process.stdout)

    entry = run("UserPromptSubmit", claude_event(root, prompt="Summarize the plan"))
    assert entry["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert run("Stop", claude_event(root, "Stop"))["decision"] == "block"
    assert len(read_state(base)["turns"]) == 1


def test_claude_code_plugin_serves_the_single_root_skill_without_hooks():
    manifest = json.loads((SOURCE / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    [plugin] = manifest["plugins"]
    # With no skills/ directory or skills key, the root SKILL.md loads as the plugin's one skill.
    assert plugin["source"] == "./" and "skills" not in plugin and not (SOURCE / "skills").exists()
    # Plugin hooks would run in every project; enabling stays an explicit project command.
    assert not {"hooks", "mcpServers"} & set(plugin) and not (SOURCE / "hooks").exists()
    skill = (SOURCE / "SKILL.md").read_text(encoding="utf-8")
    assert skill.split("---", 2)[1].splitlines()[1] == f"name: {plugin['name']}"
    for document in ("SKILL.md", "SKILL_CN.md"):
        text = (SOURCE / document).read_text(encoding="utf-8")
        for link in re.findall(r"\]\((references/[^)#]+)", text):
            assert (SOURCE / link).is_file(), link
        assert "references/claude-code-hooks.md" in text


def test_off_can_remove_the_hooks_too_even_after_intent_is_deleted(tmp_path):
    assert cli(tmp_path, "init", "--host", "codex")["ok"]
    assert cli(tmp_path, "maintenance", "on", "--host", "claude-code")["ok"]
    hooks = tmp_path / ".codex" / "hooks.json"
    settings = tmp_path / ".claude" / "settings.local.json"
    data = json.loads(hooks.read_text())
    data["hooks"]["Stop"].append({"hooks": [{"type": "command", "command": "echo mine"}]})
    hooks.write_text(json.dumps(data))
    assert cli(tmp_path, "maintenance", "off")["ok"]
    assert hooks.exists() and settings.exists() is False, "plain off keeps Codex's reviewed definitions"

    shutil.rmtree(tmp_path / ".intent")
    result = cli(tmp_path, "maintenance", "off", "--remove-hooks")
    assert result["ok"] and result["result"]["enabled"] is False
    remaining = json.loads(hooks.read_text())["hooks"]
    assert list(remaining) == ["Stop"] and "echo mine" in hooks.read_text() and "intent_cli" not in hooks.read_text()


def test_a_moved_project_hears_that_its_hooks_are_stale(tmp_path):
    root = tmp_path / "before"
    root.mkdir()
    assert cli(root, "init", "--host", "claude-code")["ok"]
    moved = tmp_path / "after"
    root.rename(moved)
    event = {"hook_event_name": "UserPromptSubmit", "session_id": "s", "prompt_id": "t", "prompt": "hi", "cwd": str(moved)}
    result = cli(moved, "maintenance", "hook", "--host", "claude-code", "--root", str(root), stdin=json.dumps(event))
    assert "itt maintenance on" in result["systemMessage"] and str(root) in result["systemMessage"]
    stop = {**event, "hook_event_name": "Stop"}
    assert cli(moved, "maintenance", "hook", "--host", "claude-code", "--root", str(root), stdin=json.dumps(stop)) == {}
    # A project nested in a hooked one is simply not this hook's.
    nested = moved / "nested"
    nested.mkdir()
    assert cli(nested, "init", "--host", "claude-code")["ok"]
    inner = {**event, "cwd": str(nested)}
    assert cli(nested, "maintenance", "hook", "--host", "claude-code", "--root", str(moved), stdin=json.dumps(inner)) == {}


def test_status_reads_without_asking_which_agent(tmp_path, monkeypatch):
    assert cli(tmp_path, "init", "--host", "codex")["ok"]
    assert cli(tmp_path, "maintenance", "status")["result"]["hooks"]["host"] == "codex"
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("status must never prompt"))
    from intent_cli.commands.maintenance import _reported_host
    assert _reported_host(None, tmp_path) == "codex"
