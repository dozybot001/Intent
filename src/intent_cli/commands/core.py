"""Core object command handlers for the Intent CLI."""

from intent_cli import __version__
from intent_cli import relations as relation_rules
from intent_cli.commands.common import expand_ids, require_init
from intent_cli.output import emit_json, error, json_mode, print_text, success
from intent_cli import identity, repo
from intent_cli.store import (
    ensure_local_git_exclude,
    git_root,
    init_workspace,
    load_graph_once,
    validate_graph,
    validate_object_id,
    workspace_write_lock,
    StorageSecurityError,
)


# ---- Commands ----

def cmd_version(_args):
    success("version", {"version": __version__})


def cmd_init(args):
    path, err = init_workspace()
    if err == "ALREADY_EXISTS":
        error(
            "ALREADY_EXISTS",
            "Intent is already initialized here.",
            suggested_fix="Run `itt inspect` to see its state, or `itt maintenance on` to enable continuous maintenance.",
        )
    warnings = []
    if git_root() is not None and not ensure_local_git_exclude(path.parent):
        warnings.append(
            "Could not add .intent/ to Git's local exclude file; exclude it manually before recording private semantics."
        )
    from intent_cli.commands.maintenance import choose_host, configure, setup_warning
    from intent_cli.maintenance import MaintenanceError, set_enabled

    host = choose_host(args.host)
    try:
        maintenance = configure(path, True, host)
        if json_mode():  # people get readable next steps from the renderer instead
            warnings.append(setup_warning(host, "maintenance.hooks.setup"))
    except (MaintenanceError, StorageSecurityError, OSError) as exc:
        set_enabled(path, True)
        maintenance = {"enabled": True, "hooks": {"host": host, "configured": False, "enforcement": "not_attested"}}
        warnings.append(f"Local maintenance is enabled but hooks were not installed: {type(exc).__name__}.")
    author = identity.author()
    if not author:
        warnings.append(identity.MISSING)
    success("init", {"path": str(path), "author": author, "maintenance": maintenance}, warnings)


def cmd_inspect(args):
    base = require_init()

    if args.history is not None:
        if args.intent is None:
            error(
                "INVALID_INPUT",
                "--history requires --intent ID.",
                suggested_fix="itt inspect --intent <id> --history <positive-number>",
            )
        if args.history < 1:
            error(
                "INVALID_INPUT",
                "--history must be a positive integer.",
                suggested_fix="Use a value of 1 or greater.",
            )
    expand_ids(base, args)
    if args.intent is not None:
        validate_object_id("intent", args.intent)

    with workspace_write_lock(base, operation="inspect"):
        graph = load_graph_once(base)

    snap_by_id = graph["snap"]
    intents = list(graph["intent"].values())
    if args.intent is not None:
        selected = next((obj for obj in intents if obj["id"] == args.intent), None)
        if selected is None:
            error("OBJECT_NOT_FOUND", f"Intent {args.intent} not found.")
        if selected.get("status") not in {"active", "suspend"}:
            error(
                "INVALID_INPUT",
                f"Intent {args.intent} is not open and cannot be resumed with inspect.",
                details={"status": selected.get("status")},
                suggested_fix="Use IntHub to browse completed or cancelled intent history.",
            )
        intents = [selected]

    history_limit = args.history if args.history is not None else 1

    active_intents = []
    suspended = []
    for obj in intents:
        snap_ids = obj.get("snap_ids") or []
        latest_snap_id = snap_ids[-1] if snap_ids else None
        latest_snap = snap_by_id.get(latest_snap_id) if latest_snap_id else None
        entry = {
            "id": obj["id"],
            "what": obj["what"],
            "why": obj.get("why", ""),
            "snap_count": len(snap_ids),
            "has_more": len(snap_ids) > history_limit,
            "checkpoint": latest_snap.get("checkpoint") if latest_snap else None,
            "latest_snap": latest_snap,
            "relations": relation_rules.view(graph["intent"], obj["id"]),
        }
        if args.history is not None:
            entry["recent_snaps"] = [
                snap_by_id.get(snap_id)
                for snap_id in snap_ids[-history_limit:]
            ]
        if obj["status"] == "active":
            active_intents.append(entry)
        elif obj["status"] == "suspend":
            entry["latest_snap_id"] = latest_snap_id
            suspended.append(entry)

    active_decisions = []
    for obj in graph["decision"].values():
        if obj.get("status") != "active":
            continue
        active_decisions.append({
            "id": obj["id"],
            "what": obj["what"],
            "why": obj.get("why", ""),
        })

    warnings = validate_graph(graph)["issues"]

    payload = {
        "ok": True,
        "active_intents": active_intents,
        "active_decisions": active_decisions,
        "suspended": suspended,
        "warnings": warnings,
    }
    if json_mode():
        # inspect keeps its original top-level JSON shape for agents and hooks.
        emit_json(payload)
        return
    from intent_cli.render import render_success
    print_text(render_success("inspect", payload))


def cmd_doctor(_args):
    base = require_init()
    warnings = [] if identity.author() else [identity.MISSING]
    with workspace_write_lock(base, operation="doctor"):
        report = validate_graph(load_graph_once(base, tolerant=True))
        if not repo.is_repository(base):
            warnings.append("This project still uses the Intent 7 format. Run itt migrate.")
        else:
            issues = repo.verify(base)
            report = {**report, "healthy": report["healthy"] and not issues, "issues": [*report["issues"], *issues]}
            if not issues and repo.uncommitted(base):
                warnings.append("The working copy differs from HEAD. The next write records it as a revision.")
    success("doctor", report, warnings)


