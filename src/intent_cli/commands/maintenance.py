"""Small project-local maintenance command surface."""

import os
import sys
from pathlib import Path

from intent_cli import store
from intent_cli.commands.common import require_init
from intent_cli.maintenance import MaintenanceError, close_turn, read_state, write_state
from intent_cli.maintenance_hooks import host_status, install_host_hooks, remove_claude_hooks, remove_codex_hooks, run_hook
from intent_cli.output import AGENT_ENVIRONMENT, json_mode, success

HOST_FOLDERS = (("codex", ".codex"), ("claude-code", ".claude"))
# Project-local hook files hold machine-specific paths; keep them out of Git like .intent/.
HOOK_FILES = {"codex": ".codex/hooks.json", "claude-code": ".claude/settings.local.json"}


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


def configure(base, enabled, host="codex"):
    # Validate/merge hooks before enabling. A failed configuration must not
    # silently claim it installed a gate. Existing semantic objects are untouched.
    root = base.parent.resolve()
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
        args.host = _reported_host(args.host, base.parent.resolve())
        if not base.exists():
            success("maintenance.status", {"root": str(base.parent.resolve()), "initialized": False, "enabled": False})
            return
        with store.workspace_write_lock(base, operation="maintenance.status"):
            state = read_state(base)
        warnings = []
        try:
            hooks = host_status(base.parent.resolve(), args.host)
        except (MaintenanceError, store.StorageSecurityError, OSError):
            hooks = {"host": args.host, "configured": None, "enforcement": "not_attested", "configuration_unavailable": True}
            warnings.append("Project hook configuration is unavailable; the local flag does not guarantee host enforcement.")
        turns = [entry for entry in state["turns"].values() if entry.get("host", "codex") == args.host]
        success("maintenance.status", {"root": str(base.parent.resolve()), "initialized": True,
                "enabled": state["enabled"], "mode": "continuous", "hooks": hooks,
                "observations": {
                    "entry_seen": bool(turns),
                    "stop_checked_receipt": any(entry.get("stop_checked", False) for entry in turns),
                    "note": "Local adapter observations, not attestation of this current desktop session or semantic quality.",
                }}, warnings)
        return
    if args.sub == "off" and getattr(args, "remove_hooks", False):
        # Also for a project whose .intent/ is already gone: what is left of it is these files.
        root = store.intent_dir().parent.resolve()
        remove_claude_hooks(root)
        remove_codex_hooks(root)
        if not store.intent_dir().exists():
            success("maintenance.off", {"root": str(root), "enabled": False, "mode": "continuous", "hooks": None})
            return
    base = require_init()
    if args.sub in {"on", "off"}:
        host = choose_host(args.host, base.parent.resolve())
        result = configure(base, args.sub == "on", host)
        # People get readable next steps from the renderer; agents keep the warning.
        warnings = [setup_warning(host)] if args.sub == "on" and json_mode() else []
        success("maintenance." + args.sub, result, warnings)
    else:
        result = close_turn(base, args.turn, args.outcome, args.reason, args.objects)
        warnings = ["Intent recording failed: " + args.reason] if args.outcome == "failed" else []
        success("maintenance.close", result, warnings)
