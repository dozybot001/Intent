"""Small project-local maintenance command surface."""

from intent_cli import store
from intent_cli.commands.common import require_init
from intent_cli.maintenance import MaintenanceError, close_turn, read_state, write_state
from intent_cli.maintenance_hooks import host_status, install_host_hooks, remove_claude_hooks, run_hook
from intent_cli.output import success


SETUP_ACTIONS = {
    "codex": "trust this project folder, then review its two hooks using /hooks in the CLI",
    "claude-code": "trust this folder in Claude Code, then confirm both Intent hooks in /hooks (restart the session if they are missing)",
}


def setup_warning(host, field="hooks.setup"):
    return f"Hooks are configured, not verified running. Follow {field}: {SETUP_ACTIONS[host]}; verify actual host execution."


def configure(base, enabled, host="codex"):
    # Validate/merge hooks before enabling. A failed configuration must not
    # silently claim it installed a gate. Existing semantic objects are untouched.
    root = base.parent.resolve()
    with store.workspace_write_lock(base, operation="maintenance.hooks"):
        if enabled:
            hooks = install_host_hooks(root, host)
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
    base = require_init()
    if args.sub in {"on", "off"}:
        result = configure(base, args.sub == "on", args.host)
        warnings = [setup_warning(args.host)] if args.sub == "on" else []
        success("maintenance." + args.sub, result, warnings)
    else:
        result = close_turn(base, args.turn, args.outcome, args.reason, args.objects)
        warnings = ["Intent recording failed: " + args.reason] if args.outcome == "failed" else []
        success("maintenance.close", result, warnings)
