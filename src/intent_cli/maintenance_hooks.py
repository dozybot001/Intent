"""Bounded Codex and Claude Code entry/closure adapters, scoped to exactly one semantic root."""

import contextlib
import functools
import json
import os
from pathlib import Path, PureWindowsPath
import secrets
import shlex
import subprocess
import sys

from intent_cli import repo, repo_checkout, store
from intent_cli import relations as relation_rules
from intent_cli.maintenance import (
    MaintenanceError, begin_turn, find_turn, latest_turn, read_state, receipt_valid, verified_graph, write_state,
)


MAX_EVENT_BYTES = 256 * 1024
MAX_CONTEXT_BYTES = 12000
# Claude Code caps injected hook text at 10,000 characters; stay below it so
# clipping is explicit instead of a host cut through the records.
CLAUDE_MAX_CONTEXT_BYTES = 9500
PLAN_MODE_NOTE = " Plan mode is read-only: skip the receipt unless this turn leaves plan mode before finishing."
EVENTS = ("UserPromptSubmit", "Stop")
HOSTS = ("codex", "claude-code")
# Personal project settings: the handlers carry machine-specific paths, so they
# do not belong in the shared, usually committed .claude/settings.json.
CLAUDE_SETTINGS = (".claude", "settings.local.json")


def _config_path(root, folder, name, create=False):
    directory = root / folder
    if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        raise store.UnsafeStoragePathError(directory, "Project hook directory must not be redirected")
    if create:
        directory.mkdir(exist_ok=True)
    path = directory / name
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise store.UnsafeStoragePathError(path, "Project hooks must be a regular file")
    return path


def _hooks_path(root, create=False):
    return _config_path(root, ".codex", "hooks.json", create)


def _claude_path(root, create=False):
    return _config_path(root, *CLAUDE_SETTINGS, create=create)


def _hooks_data(path):
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


def _command_words(handler, posix=None):
    if handler.get("type") != "command" or not isinstance(handler.get("command"), str):
        return []
    native = os.name == "nt" and not posix
    try:
        words = shlex.split(handler["command"], posix=not native)
    except ValueError:
        return []
    if native:
        words = [word[1:-1] if word.startswith('"') and word.endswith('"') else word for word in words]
    return words


def _our_handler(handler, posix=None):
    words = _command_words(handler, posix)
    return ["-m", "intent_cli", "maintenance", "hook"] == words[1:5]


def _configured(data, scope, posix=None):
    return all(any(_our_handler(handler, posix) and _command_words(handler, posix)[5:] == scope
                   for group in data["hooks"].get(event, []) for handler in group["hooks"]) for event in EVENTS)


def _without_ours(groups, posix=None):
    retained = []
    for group in groups:
        old = group["hooks"]
        keep = [item for item in old if not _our_handler(item, posix)]
        if keep:
            retained.append({**group, "hooks": keep})
        elif not any(_our_handler(item, posix) for item in old):
            retained.append(group)
    return retained


def hook_status(root):
    data = _hooks_data(_hooks_path(root))
    configured = _configured(data, ["--root", str(root)])
    return {"host": "codex", "configured": configured,
            "trust": "host_state_not_inspected" if configured else "not_configured",
            "enforcement": "not_attested", "path": str(_hooks_path(root)),
            "setup": {
                "review_argv": ["codex", "--cd", str(root)],
                "steps": [
                    "Open Codex in this exact root and review the folder trust prompt; untrusted project hooks are not loaded.",
                    "In the CLI, open /hooks and review/trust the two handlers from this project's hooks.json.",
                    "Reload the desktop project/session, then verify a real UserPromptSubmit context and Stop closure.",
                ],
                "scope": "project",
                "note": "Desktop settings may not list the current project's hooks. CLI trust does not prove desktop execution; do not install duplicate global hooks or bypass trust.",
            }}


def claude_hook_status(root):
    path = _claude_path(root)
    data = _hooks_data(path)
    configured = _configured(data, ["--host", "claude-code", "--root", str(root)], posix=True)
    status = {"host": "claude-code", "configured": configured,
              "trust": "host_state_not_inspected" if configured else "not_configured",
              "enforcement": "not_attested", "path": str(path),
              "setup": {
                  "review_cwd": str(root),
                  "review_argv": ["claude"],
                  "steps": [
                      "Start Claude Code from this exact root and accept its workspace trust dialog; an interactive session runs no settings-file hooks before that.",
                      "Run /hooks (read-only) to confirm the UserPromptSubmit and Stop handlers from .claude/settings.local.json; edits are normally picked up automatically, otherwise restart the session.",
                      "Verify a real context injection and Stop closure (claude --debug logs each hook run); configuration alone is not execution.",
                  ],
                  "scope": "project",
                  "note": "Do not copy these handlers into user-global settings or a plugin, and do not bypass trust or hook policies. On Windows, hooks need Claude Code's default Git Bash shell.",
              }}
    if data.get("disableAllHooks") is True:
        status["blocked_by"] = "disableAllHooks"
    return status


def host_status(root, host):
    return claude_hook_status(root) if host == "claude-code" else hook_status(root)


def _install(root, locate, command, pattern, posix=None):
    data = _hooks_data(locate(root))
    handler = {"type": "command", "command": command, "timeout": 5}
    for event in EVENTS:
        # An update replaces only this integration, avoiding duplicate sources
        # within the project. Other plugin/user hooks remain untouched.
        data["hooks"][event] = _without_ours(data["hooks"].get(event, []), posix) + [{"hooks": [handler]}]
    path = locate(root, create=True)
    new_file = not path.exists()
    if new_file or json.loads(path.read_text(encoding="utf-8")) != data:
        try:
            store._write_json_atomic(path, data)
        except OSError as exc:
            raise MaintenanceError("HOOK_CONFIG_WRITE_FAILED", "Could not install project hooks; review local file permissions.") from exc
    if new_file:
        store.ensure_local_git_exclude(root, (pattern,))


def install_hooks(root):
    """Preserve unrelated hooks; never edit host trust or user-global config."""
    words = [sys.executable, "-m", "intent_cli", "maintenance", "hook", "--root", str(root)]
    command = subprocess.list2cmdline(words) if os.name == "nt" else shlex.join(words)
    _install(root, _hooks_path, command, ".codex/hooks.json")
    return hook_status(root)


def _claude_command(root):
    # Shell form runs through sh, or Git Bash on Windows, which execs only a
    # slash-separated path. Exec-form `args` lacks a documented minimum version.
    executable = PureWindowsPath(sys.executable).as_posix() if os.name == "nt" else sys.executable
    return shlex.join([executable, "-m", "intent_cli", "maintenance", "hook", "--host", "claude-code", "--root", str(root)])


def install_claude_hooks(root):
    """Merge into this project's local Claude Code settings only; other keys and hooks survive."""
    _install(root, _claude_path, _claude_command(root), "/".join(CLAUDE_SETTINGS), posix=True)
    return claude_hook_status(root)


def install_host_hooks(root, host):
    return install_claude_hooks(root) if host == "claude-code" else install_hooks(root)


def remove_claude_hooks(root):
    _remove_hooks(_claude_path(root), posix=True)


def remove_codex_hooks(root):
    _remove_hooks(_hooks_path(root), posix=os.name != "nt")


def _remove_hooks(path, posix):
    """Remove only Intent's handlers; drop the settings file only if nothing else remains."""
    if not path.exists():
        return
    data = _hooks_data(path)
    changed = False
    for event, groups in list(data["hooks"].items()):
        kept = _without_ours(groups, posix=posix)
        if kept != groups:
            changed = True
            if kept:
                data["hooks"][event] = kept
            else:
                del data["hooks"][event]
    if not changed:
        return
    if not data["hooks"]:
        del data["hooks"]
    try:
        if data:
            store._write_json_atomic(path, data)
        else:
            path.unlink()
            with contextlib.suppress(OSError):
                path.parent.rmdir()
    except OSError as exc:
        raise MaintenanceError("HOOK_CONFIG_WRITE_FAILED", "Could not remove project hooks; review local file permissions.") from exc


def _place(base):
    """The branch when it is not main, and any open merge: an agent cannot write until that one is settled."""
    if not repo.is_repository(base):
        return {}
    try:
        branch, state = repo.current_branch(base), repo_checkout.read_merge_state(base)
    except store.StorageSecurityError:
        return {}
    merging = {"merging": {"branch": state["branch"], "conflicts": len(state["conflicts"]),
                           "next": "itt resolve ID --ours|--theirs, then itt merge --continue, or itt merge --abort"}} if state else {}
    return {**({"branch": branch} if branch != repo.DEFAULT_BRANCH else {}), **merging}


def _context(base, key, entry, graph, limit=MAX_CONTEXT_BYTES):
    prefix = (
        f"Intent continuous local maintenance is enabled only for {store.project_root(base).resolve()}. "
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
    records = {**_place(base), "active_intents": [], "suspended": [], "active_decisions": [], "context_truncated": False}
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
                snap = graph["snap"].get(store.latest_snap_id(ids, graph["snap"])) if ids else None
                if snap and any(len(snap.get(name, "")) > 1400 for name in ("what", "why")):
                    records["context_truncated"] = True
                item["latest_snap"] = {name: snap.get(name, "")[:1400] for name in ("id", "what", "why")} if snap else None
                checkpoint = snap.get("checkpoint") if snap else None
                if checkpoint:
                    if any(len(value) > 800 for value in checkpoint.values()):
                        records["context_truncated"] = True
                    item["latest_snap"]["checkpoint"] = {key: value[:800] for key, value in checkpoint.items()}
                item["snap_count"] = len(ids)
                links = relation_rules.view(graph["intent"], obj["id"])
                if links:
                    item["relations"] = [{"type": row["type"], "direction": row["direction"],
                                          "intent": row["intent"]["id"], "state": row["state"]} for row in links[:8]]
            collection = "active_decisions" if kind == "decision" else "active_intents" if obj["status"] == "active" else "suspended"
            records[collection].append(item)
            rendered = prefix + json.dumps(records, ensure_ascii=True)
            if len(rendered.encode("utf-8")) > limit - 300:
                records[collection].pop()
                records["context_truncated"] = True
    if records["context_truncated"]:
        records["notice"] = "Context was bounded. Inspect the selected Intent and applicable Decisions before relying on omitted facts."
    return prefix + json.dumps(records, ensure_ascii=True)


def handle_event(event, expected_root=None, host="codex"):
    if not isinstance(event, dict) or event.get("hook_event_name") not in EVENTS:
        return {}
    identity = ("cwd", "session_id", "turn_id") if host == "codex" else ("cwd", "session_id")
    if not all(isinstance(event.get(field), str) and 0 < len(event[field]) <= 1024
               for field in identity):
        return {"systemMessage": "Intent maintenance hook lacks a valid turn identity; no history was written."}
    # Claude Code has no turn ID. Its prompt_id correlates a prompt with every
    # later event until the next prompt; without one, entry issues an ID and
    # Stop falls back to the session's latest turn.
    turn = event["turn_id"] if host == "codex" else event.get("prompt_id")
    if not (isinstance(turn, str) and 0 < len(turn) <= 1024):
        turn = None
    # Plan mode cannot run the closure command, so its turns are not gated.
    plan = host == "claude-code" and event.get("permission_mode") == "plan"
    cwd = Path(event["cwd"]).resolve()
    if not cwd.is_dir():
        return {}
    os.chdir(cwd)
    base = store.intent_dir()
    if not base.exists():
        return {}
    root = store.project_root(base).resolve()
    if expected_root is not None and root != Path(expected_root).resolve():
        # A nested project is not this hook's; a project that moved still needs to hear about it.
        if event["hook_event_name"] == "UserPromptSubmit" and not Path(expected_root).exists():
            return {"systemMessage": f"Intent hooks still point at {expected_root}. Run `itt maintenance on` here to update them."}
        return {}
    # Disabled projects are a read-only no-op, including after mid-turn revoke.
    if not read_state(base)["enabled"]:
        return {}
    with store.workspace_write_lock(base, timeout=0.5, operation="maintenance.hook"):
        state = read_state(base)
        if not state["enabled"]:
            return {}
        if event["hook_event_name"] == "UserPromptSubmit":
            if host == "codex":
                key, entry = begin_turn(base, state, event["session_id"], turn, event.get("prompt"), _context)
            else:
                context = functools.partial(_context, limit=CLAUDE_MAX_CONTEXT_BYTES)
                key, entry = begin_turn(base, state, event["session_id"], turn or secrets.token_hex(16),
                                        event.get("prompt"), context, host)
            note = PLAN_MODE_NOTE if plan else ""
            return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": entry["context"] + note}}
        key, entry = find_turn(state, root, event["session_id"], turn) if turn else (None, None)
        if entry is None and host != "codex":
            key, entry = latest_turn(state, root, event["session_id"], host)
        if entry is None:
            return {"systemMessage": "Intent closure was not checked: this turn has no trusted entry context."}
        if receipt_valid(base, entry):
            # Persist a minimal observation so setup can distinguish a receipt
            # submitted by the Agent from a receipt actually checked by Stop.
            if not entry.get("stop_checked", False):
                entry["stop_checked"] = True
                write_state(base, state)
            if entry["receipt"]["outcome"] == "failed":
                return {"systemMessage": "Intent recording failed: " + entry["receipt"]["reason"][:600]}
            return {}
        if plan:
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


def run_hook(expected_root=None, host="codex"):
    try:
        raw = sys.stdin.buffer.read(MAX_EVENT_BYTES + 1)
        if len(raw) > MAX_EVENT_BYTES:
            raise ValueError("event too large")
        result = handle_event(json.loads(raw), expected_root, host)
    except (ValueError, OSError, store.StorageSecurityError, store.WorkspaceBusyError, RecursionError):
        result = {"systemMessage": "Intent maintenance hook could not verify local state; main work continues without a closure guarantee."}
    print(json.dumps(result, ensure_ascii=True))
