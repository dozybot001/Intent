"""Core object command handlers for the Intent CLI."""

import json

from intent_cli import __version__
from intent_cli.commands.common import now_utc, require_init, validate_status_filter
from intent_cli.output import error, success
from intent_cli.store import (
    VALID_STATUSES,
    git_root,
    init_workspace,
    list_objects,
    next_id,
    read_config,
    read_object,
    validate_graph,
    write_object,
)


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
    success("init", {"path": str(path)})


def cmd_inspect(_args):
    base = require_init()
    config = read_config(base)

    active_intents = []
    suspend_intents = []
    for obj in list_objects(base, "intent"):
        entry = {
            "id": obj["id"],
            "title": obj["title"],
            "status": obj["status"],
            "decision_ids": obj.get("decision_ids", []),
            "latest_snap_id": obj["snap_ids"][-1] if obj.get("snap_ids") else None,
        }
        if obj["status"] == "active":
            active_intents.append(entry)
        elif obj["status"] == "suspend":
            suspend_intents.append(entry)

    active_decisions = []
    for obj in list_objects(base, "decision", status="active"):
        active_decisions.append({
            "id": obj["id"],
            "title": obj["title"],
            "status": obj["status"],
            "intent_ids": obj.get("intent_ids", []),
        })

    all_snaps = list_objects(base, "snap")
    all_snaps.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    recent_snaps = []
    for snap in all_snaps[:10]:
        recent_snaps.append({
            "id": snap["id"],
            "title": snap["title"],
            "intent_id": snap["intent_id"],
            "status": snap["status"],
            "summary": snap.get("summary", ""),
            "feedback": snap.get("feedback", ""),
        })

    warnings = []
    intent_ids_on_disk = {obj["id"] for obj in list_objects(base, "intent")}
    for snap in all_snaps:
        if snap.get("intent_id") and snap["intent_id"] not in intent_ids_on_disk:
            warnings.append(f"Orphan snap {snap['id']}: intent {snap['intent_id']} not found")

    print(json.dumps({
        "ok": True,
        "schema_version": config.get("schema_version", "1.0"),
        "active_intents": active_intents,
        "suspend_intents": suspend_intents,
        "active_decisions": active_decisions,
        "recent_snaps": recent_snaps,
        "warnings": warnings,
    }, indent=2, ensure_ascii=False))


def cmd_doctor(_args):
    base = require_init()
    success("doctor", validate_graph(base))


def cmd_intent_create(args):
    base = require_init()
    obj_id = next_id(base, "intent")

    active_decisions = list_objects(base, "decision", status="active")
    decision_ids = [decision["id"] for decision in active_decisions]

    warnings = []
    if not decision_ids:
        warnings.append("No active decisions to attach.")

    intent = {
        "id": obj_id,
        "object": "intent",
        "created_at": now_utc(),
        "title": args.title,
        "status": "active",
        "source_query": args.query,
        "rationale": args.rationale,
        "decision_ids": decision_ids,
        "snap_ids": [],
    }
    write_object(base, "intent", obj_id, intent)

    for decision in active_decisions:
        if obj_id not in decision.get("intent_ids", []):
            decision.setdefault("intent_ids", []).append(obj_id)
            write_object(base, "decision", decision["id"], decision)

    success("intent.create", intent, warnings)


def cmd_intent_list(args):
    base = require_init()
    validate_status_filter("intent", args.status)
    objects = list_objects(base, "intent", status=args.status)
    if args.decision:
        objects = [obj for obj in objects if args.decision in obj.get("decision_ids", [])]
    success("intent.list", objects)


def cmd_intent_show(args):
    base = require_init()
    obj = read_object(base, "intent", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Intent {args.id} not found.")
    success("intent.show", obj)


def cmd_intent_activate(args):
    base = require_init()
    obj = read_object(base, "intent", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Intent {args.id} not found.")
    if obj["status"] != "suspend":
        error(
            "STATE_CONFLICT",
            f"Cannot activate intent with status '{obj['status']}'. Only 'suspend' intents can be activated.",
            suggested_fix=f"itt intent show {args.id}",
        )

    obj["status"] = "active"

    active_decisions = list_objects(base, "decision", status="active")
    for decision in active_decisions:
        if decision["id"] not in obj["decision_ids"]:
            obj["decision_ids"].append(decision["id"])
        if args.id not in decision.get("intent_ids", []):
            decision.setdefault("intent_ids", []).append(args.id)
            write_object(base, "decision", decision["id"], decision)

    write_object(base, "intent", args.id, obj)
    success("intent.activate", obj)


def cmd_intent_suspend(args):
    base = require_init()
    obj = read_object(base, "intent", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Intent {args.id} not found.")
    if obj["status"] != "active":
        error(
            "STATE_CONFLICT",
            f"Cannot suspend intent with status '{obj['status']}'. Only 'active' intents can be suspended.",
            suggested_fix=f"itt intent show {args.id}",
        )

    obj["status"] = "suspend"
    write_object(base, "intent", args.id, obj)
    success("intent.suspend", obj)


def cmd_intent_done(args):
    base = require_init()
    obj = read_object(base, "intent", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Intent {args.id} not found.")
    if obj["status"] != "active":
        error(
            "STATE_CONFLICT",
            f"Cannot mark intent as done with status '{obj['status']}'. Only 'active' intents can be marked done.",
            suggested_fix=f"itt intent show {args.id}",
        )

    obj["status"] = "done"
    write_object(base, "intent", args.id, obj)
    success("intent.done", obj)


def cmd_snap_create(args):
    base = require_init()
    intent_id = args.intent

    intent = read_object(base, "intent", intent_id)
    if intent is None:
        error("OBJECT_NOT_FOUND", f"Intent {intent_id} not found.")
    if intent["status"] != "active":
        error(
            "STATE_CONFLICT",
            f"Cannot add snap to intent with status '{intent['status']}'. Only 'active' intents accept new snaps.",
            suggested_fix=f"itt intent activate {intent_id}",
        )

    obj_id = next_id(base, "snap")
    snap = {
        "id": obj_id,
        "object": "snap",
        "created_at": now_utc(),
        "title": args.title,
        "status": "active",
        "intent_id": intent_id,
        "query": args.query,
        "rationale": args.rationale,
        "summary": args.summary,
        "feedback": args.feedback,
    }
    write_object(base, "snap", obj_id, snap)

    intent.setdefault("snap_ids", []).append(obj_id)
    write_object(base, "intent", intent_id, intent)

    success("snap.create", snap)


def cmd_snap_list(args):
    base = require_init()
    validate_status_filter("snap", args.status)
    objects = list_objects(base, "snap", status=args.status)
    if args.intent:
        objects = [snap for snap in objects if snap.get("intent_id") == args.intent]
    success("snap.list", objects)


def cmd_snap_show(args):
    base = require_init()
    obj = read_object(base, "snap", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Snap {args.id} not found.")
    success("snap.show", obj)


def cmd_snap_feedback(args):
    base = require_init()
    obj = read_object(base, "snap", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Snap {args.id} not found.")
    obj["feedback"] = args.feedback
    write_object(base, "snap", args.id, obj)
    success("snap.feedback", obj)


def cmd_snap_revert(args):
    base = require_init()
    obj = read_object(base, "snap", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Snap {args.id} not found.")
    if obj["status"] != "active":
        error(
            "STATE_CONFLICT",
            f"Cannot revert snap with status '{obj['status']}'. Only 'active' snaps can be reverted.",
            suggested_fix=f"itt snap show {args.id}",
        )

    obj["status"] = "reverted"
    write_object(base, "snap", args.id, obj)
    success("snap.revert", obj)


def cmd_decision_create(args):
    base = require_init()
    obj_id = next_id(base, "decision")

    active_intents = list_objects(base, "intent", status="active")
    intent_ids = [intent["id"] for intent in active_intents]

    warnings = []
    if not intent_ids:
        warnings.append("No active intents to attach.")

    decision = {
        "id": obj_id,
        "object": "decision",
        "created_at": now_utc(),
        "title": args.title,
        "status": "active",
        "rationale": args.rationale,
        "intent_ids": intent_ids,
    }
    write_object(base, "decision", obj_id, decision)

    for intent in active_intents:
        if obj_id not in intent.get("decision_ids", []):
            intent.setdefault("decision_ids", []).append(obj_id)
            write_object(base, "intent", intent["id"], intent)

    success("decision.create", decision, warnings)


def cmd_decision_list(args):
    base = require_init()
    validate_status_filter("decision", args.status)
    objects = list_objects(base, "decision", status=args.status)
    if args.intent:
        objects = [obj for obj in objects if args.intent in obj.get("intent_ids", [])]
    success("decision.list", objects)


def cmd_decision_show(args):
    base = require_init()
    obj = read_object(base, "decision", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Decision {args.id} not found.")
    success("decision.show", obj)


def cmd_decision_deprecate(args):
    base = require_init()
    obj = read_object(base, "decision", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Decision {args.id} not found.")
    if obj["status"] != "active":
        error(
            "STATE_CONFLICT",
            f"Cannot deprecate decision with status '{obj['status']}'. Only 'active' decisions can be deprecated.",
            suggested_fix=f"itt decision show {args.id}",
        )

    obj["status"] = "deprecated"
    write_object(base, "decision", args.id, obj)
    success("decision.deprecate", obj)


def cmd_decision_attach(args):
    base = require_init()
    decision = read_object(base, "decision", args.id)
    if decision is None:
        error("OBJECT_NOT_FOUND", f"Decision {args.id} not found.")

    intent_id = args.intent
    intent = read_object(base, "intent", intent_id)
    if intent is None:
        error("OBJECT_NOT_FOUND", f"Intent {intent_id} not found.")

    if intent_id not in decision.get("intent_ids", []):
        decision.setdefault("intent_ids", []).append(intent_id)
        write_object(base, "decision", args.id, decision)

    if args.id not in intent.get("decision_ids", []):
        intent.setdefault("decision_ids", []).append(args.id)
        write_object(base, "intent", intent_id, intent)

    success("decision.attach", decision)
