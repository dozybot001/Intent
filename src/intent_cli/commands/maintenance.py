"""Small project-local maintenance command surface."""

import json
import os
import sys
from pathlib import Path

from intent_cli import store
from intent_cli.commands.common import require_init
from intent_cli.hub.credentials import global_config_path
from intent_cli.maintenance import MaintenanceError, close_turn, read_state, write_state
from intent_cli.maintenance_hooks import host_status, install_host_hooks, remove_claude_hooks, remove_codex_hooks, run_hook
from intent_cli.output import AGENT_ENVIRONMENT, error, json_mode, success

HOST_FOLDERS = (("codex", ".codex"), ("claude-code", ".claude"))
# Project-local hook files hold machine-specific paths; keep them out of Git like .intent/.
HOOK_FILES = {"codex": ".codex/hooks.json", "claude-code": ".claude/settings.local.json"}
DECLINED_LIMIT = 1000


SETUP_ACTIONS = {
    "codex": "trust this project folder, then review its two hooks using /hooks in the CLI",
    "claude-code": "trust this folder in Claude Code, then confirm both Intent hooks in /hooks (restart the session if they are missing)",
}


def _configured_host(root):
    for host, _folder in HOST_FOLDERS:
        try:
            if host_status(root, host).get("configured"):
                return host
        except (MaintenanceError, store.StorageSecurityError, OSError):
            continue
    return None


def _ask_host():
    print("Which agent will record in this project?\n  1) Codex\n  2) Claude Code")
    try:
        answer = input("Choose 1 or 2 [1]: ").strip().lower()
    except EOFError:
        answer = ""
    return "claude-code" if answer in {"2", "claude", "claude-code"} else "codex"


def choose_host(explicit=None, root=None):
    """--host if given; else the project's configured host, the running agent,
    the only agent installed, or (for a person at a terminal) ask. Codex otherwise."""
    if explicit:
        return explicit
    if root is not None:
        configured = _configured_host(root)
        if configured:
            return configured
    if os.environ.get("CLAUDECODE"):
        return "claude-code"
    if any(os.environ.get(name) for name in AGENT_ENVIRONMENT):
        return "codex"
    installed = [host for host, folder in HOST_FOLDERS if (Path.home() / folder).is_dir()]
    if len(installed) == 1:
        return installed[0]
    if not json_mode() and sys.stdin.isatty():
        return _ask_host()
    return "codex"


def _reported_host(explicit, root):
    """Reading status never asks: the configured host, the running agent, or Codex."""
    return explicit or _configured_host(root) or ("claude-code" if os.environ.get("CLAUDECODE") else "codex")


def setup_warning(host, field="hooks.setup"):
    return f"Hooks are configured, not verified running. Follow {field}: {SETUP_ACTIONS[host]}; verify actual host execution."


def _expected_host(root):
    """The host whose hooks should run here; none for a script or an agent Intent has no hooks for."""
    if os.environ.get("CLAUDECODE"):
        return "claude-code"
    if any(os.environ.get(name) for name in AGENT_ENVIRONMENT):
        return "codex"
    return None if json_mode() else _configured_host(root) or "codex"


def recording_notice(base):
    """What to do when recording is on but its hooks have never run, so nothing is recorded by itself."""
    try:
        state = read_state(base)
        root = store.project_root(base).resolve()
        host = _expected_host(root)
        if host is None or not state["enabled"] or state["turns"]:
            return []
        configured = host_status(root, host).get("configured")
    except (MaintenanceError, store.StorageSecurityError, OSError):
        return []
    step = SETUP_ACTIONS[host] if configured else f"run itt maintenance on --host {host}"
    return [f"Recording is on, but its hooks have not run here yet, so nothing is recorded automatically. To fix it: {step}."]


def _declined_path():
    return global_config_path().parent / "declined-projects.json"


def _declined():
    """Projects whose owner said no, kept in user config so a no leaves nothing in the project."""
    try:
        roots = json.loads(_declined_path().read_text(encoding="utf-8"))["roots"]
    except (OSError, ValueError, KeyError, TypeError):
        return []
    return [root for root in roots if isinstance(root, str)] if isinstance(roots, list) else []


def _decline(root):
    roots = [value for value in _declined() if value != str(root)] + [str(root)]
    path = _declined_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        store._write_json_atomic(path, {"version": 1, "roots": roots[-DECLINED_LIMIT:]})
    except OSError as exc:
        raise MaintenanceError("MAINTENANCE_WRITE_FAILED", "Could not save this choice in the user config folder.") from exc


def _offers_recording(root):
    """Whether an agent should ask once. A home folder or a drive root is not a project."""
    return root not in (Path.home().resolve(), Path(root.anchor)) and str(root) not in _declined()


def configure(base, enabled, host="codex"):
    # Validate/merge hooks before enabling. A failed configuration must not
    # silently claim it installed a gate. Existing semantic objects are untouched.
    root = store.project_root(base).resolve()
    with store.workspace_write_lock(base, operation="maintenance.hooks"):
        if enabled:
            hooks = install_host_hooks(root, host)
            if store.git_root() is not None:
                store.ensure_local_git_exclude(root, (HOOK_FILES[host],))
        else:
            # Off leaves no Intent entries in Claude Code settings; Codex keeps
            # its reviewed definitions, which are inert while disabled.
            try:
                remove_claude_hooks(root)
            except (MaintenanceError, store.StorageSecurityError, OSError):
                pass
            # Revocation must work even if the host configuration is damaged.
            try:
                hooks = host_status(root, host)
            except (MaintenanceError, store.StorageSecurityError, OSError):
                hooks = {"host": host, "configured": None, "enforcement": "disabled", "configuration_unavailable": True}
        state = read_state(base)
        if state["enabled"] != enabled:
            state["generation"] += 1
        state["enabled"] = enabled
        write_state(base, state)
    return {"root": str(root), "enabled": state["enabled"], "mode": "continuous", "hooks": hooks}


def cmd_maintenance(args):
    if args.sub == "hook":
        run_hook(args.root, args.host)
        return
    if args.sub == "status":
        base = store.intent_dir()
        args.host = _reported_host(args.host, store.project_root(base).resolve())
        if not base.exists():
            root = store.project_root(base).resolve()
            success("maintenance.status", {"root": str(root), "initialized": False, "enabled": False, "offer": _offers_recording(root)})
            return
        with store.workspace_write_lock(base, operation="maintenance.status"):
            state = read_state(base)
        warnings = []
        try:
            hooks = host_status(store.project_root(base).resolve(), args.host)
        except (MaintenanceError, store.StorageSecurityError, OSError):
            hooks = {"host": args.host, "configured": None, "enforcement": "not_attested", "configuration_unavailable": True}
            warnings.append("Project hook configuration is unavailable; the local flag does not guarantee host enforcement.")
        turns = [entry for entry in state["turns"].values() if entry.get("host", "codex") == args.host]
        success("maintenance.status", {"root": str(store.project_root(base).resolve()), "initialized": True,
                "enabled": state["enabled"], "mode": "continuous", "hooks": hooks,
                "observations": {
                    "entry_seen": bool(turns),
                    "stop_checked_receipt": any(entry.get("stop_checked", False) for entry in turns),
                    "note": "Local adapter observations, not attestation of this current desktop session or semantic quality.",
                }}, warnings)
        return
    if args.sub == "decline":
        base = store.intent_dir()
        if base.exists():
            error("ALREADY_EXISTS", "Intent is already set up in this project.",
                  suggested_fix="Run `itt maintenance off` to stop recording here.")
        root = store.project_root(base).resolve()
        _decline(root)
        success("maintenance.decline", {"root": str(root), "offer": False})
        return
    if args.sub == "off" and getattr(args, "remove_hooks", False):
        # Also for a project whose .intent/ is already gone: what is left of it is these files.
        root = store.project_root(store.intent_dir()).resolve()
        remove_claude_hooks(root)
        remove_codex_hooks(root)
        if not store.intent_dir().exists():
            success("maintenance.off", {"root": str(root), "enabled": False, "mode": "continuous", "hooks": None})
            return
    base = require_init()
    if args.sub in {"on", "off"}:
        host = choose_host(args.host, store.project_root(base).resolve())
        result = configure(base, args.sub == "on", host)
        # People get readable next steps from the renderer; agents keep the warning.
        warnings = [setup_warning(host)] if args.sub == "on" and json_mode() else []
        success("maintenance." + args.sub, result, warnings)
    else:
        result = close_turn(base, args.turn, args.outcome, args.reason, args.objects)
        warnings = ["Intent recording failed: " + args.reason] if args.outcome == "failed" else []
        success("maintenance.close", result, warnings)
