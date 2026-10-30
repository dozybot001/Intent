"""Core object command handlers for the Intent CLI."""

from intent_cli import __version__
from intent_cli import relations as relation_rules
from intent_cli.commands.common import require_init
from intent_cli.output import emit_json, error, json_mode, success
from intent_cli import identity
from intent_cli.store import (
    ensure_local_git_exclude,
    git_root,
    init_workspace,
    load_graph_once,
    validate_object_id,
    validate_graph,
    workspace_write_lock,
    StorageSecurityError,
)
from intent_cli.commands.intents import _number


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
    print(render_success("inspect", payload))


def cmd_log(args):
    """List Snaps newest first, like `git log`."""
    base = require_init()
    if args.intent is not None:
        validate_object_id("intent", args.intent)
    if args.max_count < 1:
        error("INVALID_INPUT", "-n must be a positive integer.")
    with workspace_write_lock(base, operation="log"):
        graph = load_graph_once(base)
    intents = graph["intent"]
    if args.intent is not None and args.intent not in intents:
        error("OBJECT_NOT_FOUND", f"Intent {args.intent} not found.")
    snaps = [snap for snap in graph["snap"].values() if args.intent in (None, snap.get("intent_id"))]
    snaps.sort(key=lambda snap: (snap.get("created_at", ""), _number(snap["id"])), reverse=True)
    shown = snaps if args.all else snaps[:args.max_count]
    entries = []
    for snap in shown:
        intent = intents.get(snap.get("intent_id"))
        entries.append({**snap, "intent": {key: intent.get(key) for key in ("id", "what", "status")} if intent else None})
    success("log", {"snaps": entries, "total": len(snaps), "has_more": len(shown) < len(snaps)})


def cmd_show(args):
    """Show one Intent, Snap or Decision with its relations, like `git show`."""
    kind = args.id.split("-", 1)[0] if "-" in args.id else ""
    if kind not in {"intent", "snap", "decision"}:
        error("INVALID_INPUT", f"{args.id!r} is not an object ID.", suggested_fix="Use an ID such as intent-001, snap-001 or decision-001.")
    validate_object_id(kind, args.id)
    base = require_init()
    with workspace_write_lock(base, operation="show"):
        graph = load_graph_once(base)
    obj = graph[kind].get(args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"{args.id} not found.")
    summary = lambda item, *keys: {key: item.get(key) for key in ("id", *keys)}
    result = {"object": obj}
    if kind == "intent":
        result["snaps"] = [summary(graph["snap"][sid], "created_at", "what") for sid in obj.get("snap_ids", []) if sid in graph["snap"]]
        result["decisions"] = [summary(graph["decision"][did], "what", "status") for did in obj.get("decision_ids", []) if did in graph["decision"]]
        result["relations"] = relation_rules.view(graph["intent"], obj["id"])
    elif kind == "snap":
        intent = graph["intent"].get(obj.get("intent_id"))
        result["intent"] = summary(intent, "what", "status") if intent else None
    else:
        result["intents"] = [summary(graph["intent"][iid], "what", "status") for iid in obj.get("intent_ids", []) if iid in graph["intent"]]
        source = graph["intent"].get(obj.get("source_intent_id"))
        result["source_intent"] = summary(source, "what", "status") if source else None
    success("show", result)


def cmd_doctor(_args):
    base = require_init()
    with workspace_write_lock(base, operation="doctor"):
        graph = load_graph_once(base, tolerant=True)
    success("doctor", validate_graph(graph), [] if identity.author() else [identity.MISSING])


