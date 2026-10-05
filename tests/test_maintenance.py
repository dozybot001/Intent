"""Project isolation, quiet closure, recovery, replay and bounded hook work."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from intent_cli import store
from intent_cli import maintenance_hooks
from intent_cli.commands.maintenance import configure
from intent_cli.maintenance import MaintenanceError, MAX_TURNS, close_turn, read_state, set_enabled
from intent_cli.maintenance_hooks import MAX_CONTEXT_BYTES, handle_event, hook_status, install_hooks


SOURCE = Path(__file__).resolve().parents[1]


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


def event(root, name="UserPromptSubmit", turn="t1", session="s1", **extra):
    return {"cwd": str(root), "hook_event_name": name, "session_id": session, "turn_id": turn, **extra}


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
