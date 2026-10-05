"""Small project-local maintenance command surface."""

from intent_cli import store
from intent_cli.commands.common import require_init
from intent_cli.maintenance import MaintenanceError, close_turn, read_state, write_state
from intent_cli.maintenance_hooks import hook_status, install_hooks, run_hook
from intent_cli.output import success


def configure(base, enabled):
    # Validate/merge hooks before enabling. A failed configuration must not
    # silently claim it installed a gate. Existing semantic objects are untouched.
    with store.workspace_write_lock(base, operation="maintenance.hooks"):
        if enabled:
            hooks = install_hooks(base.parent.resolve())
        else:
            # Revocation must work even if the host configuration is damaged.
            try:
                hooks = hook_status(base.parent.resolve())
            except (MaintenanceError, store.StorageSecurityError, OSError):
                hooks = {"configured": None, "enforcement": "disabled", "configuration_unavailable": True}
        state = read_state(base)
        if state["enabled"] != enabled:
            state["generation"] += 1
        state["enabled"] = enabled
        write_state(base, state)
    return {"root": str(base.parent.resolve()), "enabled": state["enabled"], "mode": "continuous", "hooks": hooks}


def cmd_maintenance(args):
    if args.sub == "hook":
        run_hook(args.root)
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
            hooks = hook_status(base.parent.resolve())
        except (MaintenanceError, store.StorageSecurityError, OSError):
            hooks = {"configured": None, "enforcement": "not_attested", "configuration_unavailable": True}
            warnings.append("Project hook configuration is unavailable; the local flag does not guarantee host enforcement.")
        success("maintenance.status", {"root": str(base.parent.resolve()), "initialized": True,
                "enabled": state["enabled"], "mode": "continuous", "hooks": hooks,
                "observations": {
                    "entry_seen": bool(state["turns"]),
                    "stop_checked_receipt": any(entry.get("stop_checked", False)
                                                for entry in state["turns"].values()),
                    "note": "Local adapter observations, not attestation of this current desktop session or semantic quality.",
                }}, warnings)
        return
    base = require_init()
    if args.sub in {"on", "off"}:
        result = configure(base, args.sub == "on")
        warnings = ["Hooks are configured, not verified running. Follow hooks.setup: trust this project folder, then review its two hooks using /hooks in the CLI; verify actual host execution."] if args.sub == "on" else []
        success("maintenance." + args.sub, result, warnings)
    else:
        result = close_turn(base, args.turn, args.outcome, args.reason, args.objects)
        warnings = ["Intent recording failed: " + args.reason] if args.outcome == "failed" else []
        success("maintenance.close", result, warnings)
