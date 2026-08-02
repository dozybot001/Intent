"""Core object command handlers for the Intent CLI."""

import json

from intent_cli import __version__
from intent_cli.commands.common import now_utc, require_init, workspace_mutation
from intent_cli.output import error, success
from intent_cli.origin import detect_origin
from intent_cli.store import (
    VALID_STATUSES,
    ensure_local_git_exclude,
    git_root,
    init_workspace,
    list_objects,
    next_id,
    read_object,
    validate_object_id,
    validate_graph,
    write_object,
)


# ---- Commands ----

def cmd_version(_args):
    success("version", {"version": __version__})


def cmd_init(_args):
    path, err = init_workspace()
    if err == "GIT_STATE_INVALID":
        error(
            "GIT_STATE_INVALID",
            "Not inside a Git repository.",
            suggested_fix="cd into a git repo and run: itt init",
        )
    if err == "ALREADY_EXISTS":
        error(
            "ALREADY_EXISTS",
            ".intent/ already exists.",
            suggested_fix="Remove .intent/ first if you want to reinitialize.",
        )
    warnings = []
    if not ensure_local_git_exclude(path.parent):
        warnings.append(
            "Could not add .intent/ to Git's local exclude file; exclude it manually before recording private semantics."
        )
    success("init", {"path": str(path)}, warnings)


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

    all_snaps = list_objects(base, "snap")
    snap_by_id = {snap["id"]: snap for snap in all_snaps}

    intents = list_objects(base, "intent")
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
            "latest_snap": latest_snap,
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
    for obj in list_objects(base, "decision", status="active"):
        active_decisions.append({
            "id": obj["id"],
            "what": obj["what"],
            "why": obj.get("why", ""),
        })

    warnings = validate_graph(base)["issues"]

    print(json.dumps({
        "ok": True,
        "active_intents": active_intents,
        "active_decisions": active_decisions,
        "suspended": suspended,
        "warnings": warnings,
    }, indent=2, ensure_ascii=False))


def cmd_doctor(_args):
    base = require_init()
    success("doctor", validate_graph(base))


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
        key=lambda c: c["id"],
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


@workspace_mutation
def cmd_intent_create(args):
    base = require_init()
    obj_id = next_id(base, "intent")

    active_decisions = list_objects(base, "decision", status="active")
    decision_ids = [decision["id"] for decision in active_decisions]

    if args.origin is not None:
        origin = (args.origin or "").strip()
    else:
        origin = detect_origin()

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
    write_object(base, "intent", obj_id, intent)

    for decision in active_decisions:
        if obj_id not in decision.get("intent_ids", []):
            decision.setdefault("intent_ids", []).append(obj_id)
            write_object(base, "decision", decision["id"], decision)

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
            write_object(base, "decision", decision["id"], decision)

    write_object(base, "intent", intent_id, obj)
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
    write_object(base, "intent", intent_id, obj)
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

    obj["status"] = "done"
    write_object(base, "intent", intent_id, obj)
    warnings = []
    if inferred:
        warnings.append(f"Inferred intent {intent_id} (only active intent).")
    success("intent.done", _intent_result_for_json(obj), warnings)


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

    obj["status"] = "cancelled"
    reason = getattr(args, "reason", "") or ""
    if reason:
        obj["reason"] = reason
    write_object(base, "intent", intent_id, obj)
    warnings = []
    if inferred:
        warnings.append(f"Inferred intent {intent_id} (only open intent).")
    success("intent.cancel", _intent_result_for_json(obj), warnings)


@workspace_mutation
def cmd_snap_create(args):
    base = require_init()
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
    write_object(base, "snap", obj_id, snap)

    intent.setdefault("snap_ids", []).append(obj_id)
    write_object(base, "intent", intent_id, intent)

    warnings = []
    if inferred:
        warnings.append(f"Inferred intent {intent_id} (only active intent).")
    success("snap.create", snap, warnings)


@workspace_mutation
def cmd_decision_create(args):
    base = require_init()
    obj_id = next_id(base, "decision")

    active_intents = list_objects(base, "intent", status="active")
    intent_ids = [intent["id"] for intent in active_intents]

    if args.origin is not None:
        origin = (args.origin or "").strip()
    else:
        origin = detect_origin()

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
    write_object(base, "decision", obj_id, decision)

    for intent in active_intents:
        if obj_id not in intent.get("decision_ids", []):
            intent.setdefault("decision_ids", []).append(obj_id)
            write_object(base, "intent", intent["id"], intent)

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
    write_object(base, "decision", args.id, obj)
    success("decision.deprecate", obj)
