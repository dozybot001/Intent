"""Bounded Codex entry/closure adapters, scoped to exactly one semantic root."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from intent_cli import store
from intent_cli.maintenance import (
    MaintenanceError, begin_turn, find_turn, read_state, receipt_valid, verified_graph, write_state,
)


MAX_EVENT_BYTES = 256 * 1024
MAX_CONTEXT_BYTES = 12000
EVENTS = ("UserPromptSubmit", "Stop")


def _hooks_path(root, create=False):
    directory = root / ".codex"
    if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        raise store.UnsafeStoragePathError(directory, "Project hook directory must not be redirected")
    if create:
        directory.mkdir(exist_ok=True)
    path = directory / "hooks.json"
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise store.UnsafeStoragePathError(path, "Project hooks must be a regular file")
    return path


def _hooks_data(root):
    path = _hooks_path(root)
    if not path.exists():
        return {"hooks": {}}
    try:
        if path.stat().st_size > MAX_EVENT_BYTES:
            raise ValueError("oversized hooks")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("hooks", {}), dict):
            raise ValueError("invalid hooks")
        for groups in data.get("hooks", {}).values():
            if (not isinstance(groups, list) or any(not isinstance(group, dict)
                    or not isinstance(group.get("hooks"), list)
                    or any(not isinstance(handler, dict) for handler in group["hooks"]) for group in groups)):
                raise ValueError("invalid hook group")
        data.setdefault("hooks", {})
        return data
    except (ValueError, OSError, UnicodeError, RecursionError) as exc:
        raise MaintenanceError("HOOK_CONFIG_INVALID", "Existing hooks are invalid; nothing was replaced.") from exc


def _command_words(handler):
    if handler.get("type") != "command" or not isinstance(handler.get("command"), str):
        return []
    try:
        words = shlex.split(handler["command"], posix=os.name != "nt")
    except ValueError:
        return []
    if os.name == "nt":
        words = [word[1:-1] if word.startswith('"') and word.endswith('"') else word for word in words]
    return words


def _our_handler(handler):
    words = _command_words(handler)
    return ["-m", "intent_cli", "maintenance", "hook"] == words[1:5]


def hook_status(root):
    data = _hooks_data(root)
    def scoped(handler):
        if not _our_handler(handler):
            return False
        words = _command_words(handler)
        return words[5:] == ["--root", str(root)]

    configured = all(any(scoped(handler) for group in data["hooks"].get(event, [])
                         for handler in group["hooks"]) for event in EVENTS)
    return {"configured": configured, "trust": "host_review_required" if configured else "not_configured",
            "enforcement": "not_attested", "path": str(_hooks_path(root))}


def install_hooks(root):
    """Preserve unrelated hooks; never edit host trust or user-global config."""
    data = _hooks_data(root)
    words = [sys.executable, "-m", "intent_cli", "maintenance", "hook", "--root", str(root)]
    command = subprocess.list2cmdline(words) if os.name == "nt" else shlex.join(words)
    handler = {"type": "command", "command": command, "timeout": 5}
    for event in EVENTS:
        groups = data["hooks"].setdefault(event, [])
        # An update replaces only this integration, avoiding duplicate sources
        # within the project. Other plugin/user hooks remain untouched.
        retained = []
        for group in groups:
            old = group["hooks"]
            keep = [item for item in old if not _our_handler(item)]
            if keep:
                retained.append({**group, "hooks": keep})
            elif not any(_our_handler(item) for item in old):
                retained.append(group)
        retained.append({"hooks": [handler]})
        data["hooks"][event] = retained
    path = _hooks_path(root, create=True)
    new_file = not path.exists()
    if not path.exists() or json.loads(path.read_text(encoding="utf-8")) != data:
        try:
            store._write_json_atomic(path, data)
        except OSError as exc:
            raise MaintenanceError("HOOK_CONFIG_WRITE_FAILED", "Could not install project hooks; review local file permissions.") from exc
    if new_file:
        store.ensure_local_git_exclude(root, (".codex/hooks.json",))
    return hook_status(root)


def _context(base, key, entry, graph):
    prefix = (
        f"Intent continuous local maintenance is enabled only for {base.parent.resolve()}. "
        "Use the intent-cli Skill. This entry is the current turn's inspect; do not repeat it if sufficient. "
        "Preserve verified milestones, split independent goals, and write no garbage Snap for a quiet turn. "
        "Before finishing, run: itt maintenance close recorded|no-op|failed "
        f"--turn {key} [--reason REASON] [--objects ID ...]. "
        "recorded verifies changed objects; no-op/failed need a short reason. "
        "Respect read-only/skip instructions; they allow no-op, not semantic writes. "
        "Do not push/pull/login automatically. Receipt metadata is not semantic history. "
    )
    if entry["entry_error"]:
        return prefix + "History was unavailable at entry. Diagnose safely; report failed if it remains unverified."
    records = {"active_intents": [], "suspended": [], "active_decisions": [], "context_truncated": False}
    for kind, objects in (("decision", graph["decision"]), ("intent", graph["intent"])):
        for obj in objects.values():
            if obj.get("status") not in {"active", "suspend"}:
                continue
            item = {name: obj.get(name, "") for name in ("id", "what", "why", "status")}
            if len(item["what"]) > 800 or len(item["why"]) > 800:
                records["context_truncated"] = True
            item["what"], item["why"] = item["what"][:800], item["why"][:800]
            if kind == "intent":
                ids = obj["snap_ids"]
                snap = graph["snap"].get(ids[-1]) if ids else None
                if snap and any(len(snap.get(name, "")) > 1400 for name in ("what", "why")):
                    records["context_truncated"] = True
                item["latest_snap"] = {name: snap.get(name, "")[:1400] for name in ("id", "what", "why")} if snap else None
                item["snap_count"] = len(ids)
            collection = "active_decisions" if kind == "decision" else "active_intents" if obj["status"] == "active" else "suspended"
            records[collection].append(item)
            rendered = prefix + json.dumps(records, ensure_ascii=True)
            if len(rendered.encode("utf-8")) > MAX_CONTEXT_BYTES - 300:
                records[collection].pop()
                records["context_truncated"] = True
    if records["context_truncated"]:
        records["notice"] = "Context was bounded. Inspect the selected Intent and applicable Decisions before relying on omitted facts."
    return prefix + json.dumps(records, ensure_ascii=True)


def handle_event(event, expected_root=None):
    if not isinstance(event, dict) or event.get("hook_event_name") not in EVENTS:
        return {}
    if not all(isinstance(event.get(field), str) and 0 < len(event[field]) <= 1024
               for field in ("cwd", "session_id", "turn_id")):
        return {"systemMessage": "Intent maintenance hook lacks a valid turn identity; no history was written."}
    cwd = Path(event["cwd"]).resolve()
    if not cwd.is_dir():
        return {}
    os.chdir(cwd)
    base = store.intent_dir()
    if not base.exists():
        return {}
    root = base.parent.resolve()
    if expected_root is not None and root != Path(expected_root).resolve():
        return {}
    # Disabled projects are a read-only no-op, including after mid-turn revoke.
    if not read_state(base)["enabled"]:
        return {}
    with store.workspace_write_lock(base, timeout=0.5, operation="maintenance.hook"):
        state = read_state(base)
        if not state["enabled"]:
            return {}
        if event["hook_event_name"] == "UserPromptSubmit":
            key, entry = begin_turn(base, state, event["session_id"], event["turn_id"], event.get("prompt"), _context)
            return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": entry["context"]}}
        key, entry = find_turn(state, root, event["session_id"], event["turn_id"])
        if entry is None:
            return {"systemMessage": "Intent closure was not checked: this turn has no trusted entry context."}
        if receipt_valid(base, entry):
            if entry["receipt"]["outcome"] == "failed":
                return {"systemMessage": "Intent recording failed: " + entry["receipt"]["reason"][:600]}
            return {}
        if entry["retry_count"] or event.get("stop_hook_active") is True:
            return {"systemMessage": "Intent closure remains incomplete after one retry; main work is released, no successful recording is claimed."}
        reason = (f"Intent closure retry {key}. Complete only this project's missing local receipt using "
                  f"itt maintenance close recorded|no-op|failed --turn {key}. "
                  "For no-op/failed add a short --reason. Do not redo the task, create quota-filling Snaps, or sync. "
                  "Use the current intent-cli Skill and verified object IDs. Report a real failure if closure cannot be verified.")
        entry["retry_count"], entry["continuation_reason"] = 1, reason
        write_state(base, state)
        return {"decision": "block", "reason": reason}


def run_hook(expected_root=None):
    try:
        raw = sys.stdin.buffer.read(MAX_EVENT_BYTES + 1)
        if len(raw) > MAX_EVENT_BYTES:
            raise ValueError("event too large")
        result = handle_event(json.loads(raw), expected_root)
    except (ValueError, OSError, store.StorageSecurityError, store.WorkspaceBusyError, RecursionError):
        result = {"systemMessage": "Intent maintenance hook could not verify local state; main work continues without a closure guarantee."}
    print(json.dumps(result, ensure_ascii=True))
