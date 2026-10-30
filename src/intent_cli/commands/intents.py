"""Create Intents, change their status and relate them."""

from intent_cli import identity, relations as relation_rules
from intent_cli.commands.common import now_utc, require_init, workspace_mutation
from intent_cli.origin import detect_origin
from intent_cli.output import error, json_mode, success
from intent_cli.store import create_object, list_objects, next_id, read_object, update_object, validate_object_id


def _attribute(obj):
    """Record the author, omitted rather than empty so objects keep the older shape without one."""
    author = identity.author()
    if author:
        obj["author"] = author


def _number(obj_id):
    return int(obj_id.rsplit("-", 1)[1])


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
    if not decision_ids and json_mode():
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
    _attribute(intent)
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
