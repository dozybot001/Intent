"""Core object command handlers for the Intent CLI."""

from intent_cli import __version__
from intent_cli import relations as relation_rules
from intent_cli.commands.common import now_utc, require_init, workspace_mutation
from intent_cli.output import emit_json, error, json_mode, success
from intent_cli.origin import detect_origin
from intent_cli.store import (
    CHECKPOINT_FIELDS,
    CHECKPOINT_FIELD_MAX_CHARS,
    VALID_STATUSES,
    create_object,
    ensure_local_git_exclude,
    git_root,
    init_workspace,
    list_objects,
    load_graph_once,
    next_id,
    read_object,
    update_object,
    validate_object_id,
    validate_graph,
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
    from intent_cli.commands.maintenance import configure, setup_warning
    from intent_cli.maintenance import MaintenanceError, set_enabled

    try:
        maintenance = configure(path, True, args.host)
        warnings.append(setup_warning(args.host, "maintenance.hooks.setup"))
    except (MaintenanceError, StorageSecurityError, OSError) as exc:
        set_enabled(path, True)
        maintenance = {"enabled": True, "hooks": {"host": args.host, "configured": False, "enforcement": "not_attested"}}
        warnings.append(f"Local maintenance is enabled but hooks were not installed: {type(exc).__name__}.")
    success("init", {"path": str(path), "maintenance": maintenance}, warnings)


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


def _number(obj_id):
    return int(obj_id.rsplit("-", 1)[1])


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
    success("doctor", validate_graph(graph))


def _intent_result_for_json(intent):
    result = dict(intent)
    result.pop("decision_ids", None)
    return result


def _resolve_inferred_intent_id(
    base,
    explicit_id,
    *,
    status,
    none_code,
    none_message,
    multi_code,
    multi_message,
    suggested_fix,
):
    if explicit_id:
        return explicit_id, False

    candidates = sorted(
        (
            {"id": obj["id"], "what": obj["what"]}
            for obj in list_objects(base, "intent", status=status)
        ),
        key=lambda c: _number(c["id"]),
    )
    if not candidates:
        error(none_code, none_message, suggested_fix=suggested_fix)
    if len(candidates) > 1:
        error(
            multi_code,
            multi_message,
            details={"candidates": candidates},
            suggested_fix=suggested_fix,
        )
    return candidates[0]["id"], True


def _require_text(value, name="WHAT"):
    if not str(value or "").strip():
        error("INVALID_INPUT", f"{name} must not be empty.")


def _relation_entry(kind, target_id):
    return {"type": kind, "intent": target_id, "created_at": now_utc()}


def _require_relation(intents, subject_id, kind, target_id):
    """Exit before any write if SUBJECT KIND TARGET would break a relation rule."""
    validate_object_id("intent", target_id)
    if subject_id not in intents:
        error("OBJECT_NOT_FOUND", f"Intent {subject_id} not found.")
    problem = relation_rules.violation(intents, subject_id, kind, target_id)
    if problem:
        code, message = problem
        error(code, message, suggested_fix=f"Inspect current relations with: itt show {subject_id}")


def _relation_flags(args):
    """(type, target) pairs given on the command line, in relation-type order."""
    pairs = []
    for kind in relation_rules.RELATION_TYPES:
        values = getattr(args, kind, None)
        for value in [values] if isinstance(values, str) else values or []:
            pairs.append((kind, value))
    return pairs


def _record_successor(base, intent_id, into):
    """For --into: record, before the status change, that INTO succeeds this intent.

    Ending one of two conflicting intents in favour of the other resolves the
    conflict, so that conflict record is withdrawn and replaced by succession.
    """
    if not into:
        return None
    validate_object_id("intent", into)
    intents = {obj["id"]: obj for obj in list_objects(base, "intent")}
    changed = set()
    for owner_id, other_id in ((intent_id, into), (into, intent_id)):
        for entry in relation_rules.active_entries(intents.get(owner_id, {})):
            if entry["intent"] == other_id and entry["type"] == "conflicts_with":
                entry["removed_at"] = now_utc()
                changed.add(owner_id)
    _require_relation(intents, into, "succeeds", intent_id)
    intents[into].setdefault("relations", []).append(_relation_entry("succeeds", intent_id))
    for owner_id in changed | {into}:
        update_object(base, "intent", owner_id, intents[owner_id])
    return into


@workspace_mutation
def cmd_intent_create(args):
    _require_text(args.what)
    base = require_init()
    obj_id = next_id(base, "intent")

    active_decisions = list_objects(base, "decision", status="active")
    decision_ids = [decision["id"] for decision in active_decisions]

    if args.origin is not None:
        origin = (args.origin or "").strip()
    else:
        origin = detect_origin()

    relations = []
    pairs = _relation_flags(args)
    if pairs:
        # Only relations need the other intents; plain creation stays a single write.
        intents = {obj["id"]: obj for obj in list_objects(base, "intent")}
        intents[obj_id] = {"id": obj_id, "status": "active", "relations": relations}
        for kind, target_id in pairs:
            _require_relation(intents, obj_id, kind, target_id)
            relations.append(_relation_entry(kind, target_id))

    warnings = []
    if not decision_ids:
        warnings.append("No active decisions to attach.")

    intent = {
        "id": obj_id,
        "object": "intent",
        "created_at": now_utc(),
        "what": args.what,
        "status": "active",
        "why": args.why,
        "origin": origin,
        "decision_ids": decision_ids,
        "snap_ids": [],
    }
    if relations:
        intent["relations"] = relations
    create_object(base, "intent", obj_id, intent)

    for decision in active_decisions:
        if obj_id not in decision.get("intent_ids", []):
            decision.setdefault("intent_ids", []).append(obj_id)
            update_object(base, "decision", decision["id"], decision)

    success("intent.create", _intent_result_for_json(intent), warnings)

@workspace_mutation
def cmd_intent_activate(args):
    base = require_init()
    intent_id, inferred = _resolve_inferred_intent_id(
        base,
        args.id,
        status="suspend",
        none_code="NO_SUSPENDED_INTENT",
        none_message="No suspended intent to activate.",
        multi_code="MULTIPLE_SUSPENDED_INTENTS",
        multi_message="Multiple suspended intents; specify which one with ID.",
        suggested_fix="itt intent activate <id> or use: itt inspect",
    )

    obj = read_object(base, "intent", intent_id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Intent {intent_id} not found.")
    if obj["status"] != "suspend":
        error(
            "STATE_CONFLICT",
            f"Cannot activate intent with status '{obj['status']}'. Only 'suspend' intents can be activated.",
            suggested_fix="Use: itt inspect",
        )

    obj["status"] = "active"

    active_decisions = list_objects(base, "decision", status="active")
    for decision in active_decisions:
        if decision["id"] not in obj["decision_ids"]:
            obj["decision_ids"].append(decision["id"])
        if intent_id not in decision.get("intent_ids", []):
            decision.setdefault("intent_ids", []).append(intent_id)
            update_object(base, "decision", decision["id"], decision)

    update_object(base, "intent", intent_id, obj)
    warnings = []
    if inferred:
        warnings.append(f"Inferred intent {intent_id} (only suspended intent).")
    success("intent.activate", _intent_result_for_json(obj), warnings)


@workspace_mutation
def cmd_intent_suspend(args):
    base = require_init()
    intent_id, inferred = _resolve_inferred_intent_id(
        base,
        args.id,
        status="active",
        none_code="NO_ACTIVE_INTENT",
        none_message="No active intent to suspend.",
        multi_code="MULTIPLE_ACTIVE_INTENTS",
        multi_message="Multiple active intents; specify which one with ID.",
        suggested_fix="itt intent suspend <id> or use: itt inspect",
    )

    obj = read_object(base, "intent", intent_id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Intent {intent_id} not found.")
    if obj["status"] != "active":
        error(
            "STATE_CONFLICT",
            f"Cannot suspend intent with status '{obj['status']}'. Only 'active' intents can be suspended.",
            suggested_fix="Use: itt inspect",
        )

    obj["status"] = "suspend"
    update_object(base, "intent", intent_id, obj)
    warnings = []
    if inferred:
        warnings.append(f"Inferred intent {intent_id} (only active intent).")
    success("intent.suspend", _intent_result_for_json(obj), warnings)


@workspace_mutation
def cmd_intent_done(args):
    base = require_init()
    intent_id, inferred = _resolve_inferred_intent_id(
        base,
        args.id,
        status="active",
        none_code="NO_ACTIVE_INTENT",
        none_message="No active intent to mark done.",
        multi_code="MULTIPLE_ACTIVE_INTENTS",
        multi_message="Multiple active intents; specify which one with ID.",
        suggested_fix="itt intent done <id> or use: itt inspect",
    )

    obj = read_object(base, "intent", intent_id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Intent {intent_id} not found.")
    if obj["status"] != "active":
        error(
            "STATE_CONFLICT",
            f"Cannot mark intent as done with status '{obj['status']}'. Only 'active' intents can be marked done.",
            suggested_fix="Use: itt inspect",
        )

    successor = _record_successor(base, intent_id, getattr(args, "into", None))
    if successor:
        obj = read_object(base, "intent", intent_id)  # --into may have withdrawn a conflict stored here
    obj["status"] = "done"
    update_object(base, "intent", intent_id, obj)
    warnings = []
    if inferred:
        warnings.append(f"Inferred intent {intent_id} (only active intent).")
    result = _intent_result_for_json(obj)
    if successor:
        result["successor"] = successor
    success("intent.done", result, warnings)


@workspace_mutation
def cmd_intent_cancel(args):
    base = require_init()
    if args.id:
        intent_id = args.id
        inferred = False
    else:
        candidates = sorted(
            (
                {"id": obj["id"], "what": obj["what"]}
                for obj in list_objects(base, "intent")
                if obj.get("status") in {"active", "suspend"}
            ),
            key=lambda candidate: candidate["id"],
        )
        if not candidates:
            error(
                "NO_OPEN_INTENT",
                "No active or suspended intent to cancel.",
                suggested_fix="Use: itt inspect",
            )
        if len(candidates) > 1:
            error(
                "MULTIPLE_OPEN_INTENTS",
                "Multiple active or suspended intents; specify which one with ID.",
                details={"candidates": candidates},
                suggested_fix="itt intent cancel <id> --reason TEXT",
            )
        intent_id = candidates[0]["id"]
        inferred = True

    obj = read_object(base, "intent", intent_id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Intent {intent_id} not found.")
    if obj["status"] not in {"active", "suspend"}:
        error(
            "STATE_CONFLICT",
            f"Cannot cancel intent with status '{obj['status']}'. Only 'active' or 'suspend' intents can be cancelled.",
            suggested_fix="Use: itt inspect",
        )

    successor = _record_successor(base, intent_id, getattr(args, "into", None))
    if successor:
        obj = read_object(base, "intent", intent_id)  # --into may have withdrawn a conflict stored here
    obj["status"] = "cancelled"
    reason = getattr(args, "reason", "") or ""
    if reason:
        obj["reason"] = reason
    update_object(base, "intent", intent_id, obj)
    warnings = []
    if inferred:
        warnings.append(f"Inferred intent {intent_id} (only open intent).")
    result = _intent_result_for_json(obj)
    if successor:
        result["successor"] = successor
    success("intent.cancel", result, warnings)


@workspace_mutation
def cmd_intent_relate(args):
    base = require_init()
    validate_object_id("intent", args.id)
    kind, target_id = next(pair for pair in _relation_flags(args))
    intents = {obj["id"]: obj for obj in list_objects(base, "intent")}
    _require_relation(intents, args.id, kind, target_id)
    subject = intents[args.id]
    entry = _relation_entry(kind, target_id)
    subject.setdefault("relations", []).append(entry)
    update_object(base, "intent", args.id, subject)
    success("intent.relate", {
        "id": args.id,
        "relation": {**entry, "state": relation_rules.state(kind, subject, intents[target_id])},
    })


@workspace_mutation
def cmd_intent_unrelate(args):
    base = require_init()
    for value in (args.id, args.other):
        validate_object_id("intent", value)
    intents = {obj["id"]: obj for obj in list_objects(base, "intent")}
    for value in (args.id, args.other):
        if value not in intents:
            error("OBJECT_NOT_FOUND", f"Intent {value} not found.")
    # The relation is stored on whichever intent declared it.
    for owner_id, other_id in ((args.id, args.other), (args.other, args.id)):
        owner = intents[owner_id]
        entry = next((item for item in relation_rules.active_entries(owner) if item["intent"] == other_id), None)
        if entry is not None:
            entry["removed_at"] = now_utc()
            update_object(base, "intent", owner_id, owner)
            success("intent.unrelate", {"id": owner_id, "relation": entry})
            return
    error(
        "OBJECT_NOT_FOUND",
        f"No active relation between {args.id} and {args.other}.",
        suggested_fix=f"Inspect current relations with: itt show {args.id}",
    )


def _checkpoint_from_args(args):
    """Return the optional structured checkpoint, or exit before any write."""
    checkpoint = {}
    for name in CHECKPOINT_FIELDS:
        value = getattr(args, name, None)
        if value is None:
            continue
        value = value.strip()
        if not value:
            error(
                "INVALID_INPUT",
                f"--{name} must not be blank.",
                details={"field": name},
                suggested_fix="Omit the flag when that cell is unknown; use --blocker none when nothing blocks.",
            )
        if len(value) > CHECKPOINT_FIELD_MAX_CHARS:
            error(
                "INVALID_INPUT",
                f"--{name} exceeds {CHECKPOINT_FIELD_MAX_CHARS} characters.",
                details={"field": name, "length": len(value), "limit": CHECKPOINT_FIELD_MAX_CHARS},
                suggested_fix="Keep the checkpoint cell concise and move supporting detail into --why.",
            )
        checkpoint[name] = value
    return checkpoint


@workspace_mutation
def cmd_snap_create(args):
    _require_text(args.what)
    base = require_init()
    checkpoint = _checkpoint_from_args(args)
    if args.intent:
        intent_id = args.intent
        inferred = False
    else:
        active = list_objects(base, "intent", status="active")
        if not active:
            error(
                "NO_ACTIVE_INTENT",
                "No active intent to attach the snap to.",
                suggested_fix='Create or activate an intent first, e.g. itt intent create "WHAT" or itt intent activate <id>',
            )
        if len(active) > 1:
            candidates = sorted(
                ({"id": o["id"], "what": o["what"]} for o in active),
                key=lambda c: c["id"],
            )
            error(
                "MULTIPLE_ACTIVE_INTENTS",
                "Multiple active intents; specify which one with --intent ID.",
                details={"candidates": candidates},
                suggested_fix="itt snap create WHAT --intent <id> --why ...",
            )
        intent_id = active[0]["id"]
        inferred = True

    intent = read_object(base, "intent", intent_id)
    if intent is None:
        error("OBJECT_NOT_FOUND", f"Intent {intent_id} not found.")
    if intent["status"] != "active":
        error(
            "STATE_CONFLICT",
            f"Cannot add snap to intent with status '{intent['status']}'. Only 'active' intents accept new snaps.",
            suggested_fix=f"itt intent activate {intent_id}",
        )

    if args.origin is not None:
        origin = (args.origin or "").strip()
    else:
        origin = detect_origin()

    obj_id = next_id(base, "snap")
    snap = {
        "id": obj_id,
        "object": "snap",
        "created_at": now_utc(),
        "what": args.what,
        "why": args.why,
        "intent_id": intent_id,
        "origin": origin,
    }
    # Omitted rather than empty, so Snaps without a checkpoint keep the legacy shape.
    if checkpoint:
        snap["checkpoint"] = checkpoint
    create_object(base, "snap", obj_id, snap)

    intent.setdefault("snap_ids", []).append(obj_id)
    update_object(base, "intent", intent_id, intent)

    warnings = []
    if inferred:
        warnings.append(f"Inferred intent {intent_id} (only active intent).")
    success("snap.create", snap, warnings)


@workspace_mutation
def cmd_decision_create(args):
    _require_text(args.what)
    base = require_init()
    obj_id = next_id(base, "decision")

    active_intents = list_objects(base, "intent", status="active")
    intent_ids = [intent["id"] for intent in active_intents]

    if args.origin is not None:
        origin = (args.origin or "").strip()
    else:
        origin = detect_origin()

    source = getattr(args, "source", None)
    if source:
        validate_object_id("intent", source)
        if read_object(base, "intent", source) is None:
            error("OBJECT_NOT_FOUND", f"Intent {source} not found.", suggested_fix="Omit --from for a project-level decision.")

    warnings = []
    if not intent_ids:
        warnings.append("No active intents to attach.")

    decision = {
        "id": obj_id,
        "object": "decision",
        "created_at": now_utc(),
        "what": args.what,
        "status": "active",
        "why": args.why,
        "origin": origin,
        "intent_ids": intent_ids,
    }
    if source:
        decision["source_intent_id"] = source
    create_object(base, "decision", obj_id, decision)

    for intent in active_intents:
        if obj_id not in intent.get("decision_ids", []):
            intent.setdefault("decision_ids", []).append(obj_id)
            update_object(base, "intent", intent["id"], intent)

    success("decision.create", decision, warnings)


@workspace_mutation
def cmd_decision_deprecate(args):
    base = require_init()
    obj = read_object(base, "decision", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Decision {args.id} not found.")
    if obj["status"] != "active":
        error(
            "STATE_CONFLICT",
            f"Cannot deprecate decision with status '{obj['status']}'. Only 'active' decisions can be deprecated.",
            suggested_fix="Use: itt inspect",
        )

    obj["status"] = "deprecated"
    reason = getattr(args, "reason", "") or ""
    if reason:
        obj["reason"] = reason
    update_object(base, "decision", args.id, obj)
    success("decision.deprecate", obj)
