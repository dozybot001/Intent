"""Intent CLI — entry point and command handlers."""

import argparse
import json
import sys
from datetime import datetime, timezone

from intent_cli.output import success, error
from intent_cli.store import (
    git_root, ensure_init, init_workspace,
    next_id, read_object, write_object, list_objects, read_config,
)

VERSION = "0.6.0"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _require_init():
    """Return .intent/ base path, or exit with error."""
    base = ensure_init()
    if base is not None:
        return base
    if git_root() is None:
        error("GIT_STATE_INVALID", "Not inside a Git repository.",
              suggested_fix="cd into a git repo and run: itt init")
    error("NOT_INITIALIZED", ".intent/ directory not found.",
          suggested_fix="itt init")


# ---------------------------------------------------------------------------
# Global commands
# ---------------------------------------------------------------------------

def cmd_version(_args):
    success("version", {"version": VERSION})


def cmd_init(_args):
    path, err = init_workspace()
    if err == "GIT_STATE_INVALID":
        error("GIT_STATE_INVALID", "Not inside a Git repository.",
              suggested_fix="cd into a git repo and run: itt init")
    if err == "ALREADY_EXISTS":
        error("ALREADY_EXISTS", ".intent/ already exists.",
              suggested_fix="Remove .intent/ first if you want to reinitialize.")
    success("init", {"path": str(path)})


def cmd_inspect(_args):
    base = _require_init()
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
    for s in all_snaps[:10]:
        recent_snaps.append({
            "id": s["id"],
            "title": s["title"],
            "intent_id": s["intent_id"],
            "status": s["status"],
            "summary": s.get("summary", ""),
            "feedback": s.get("feedback", ""),
        })

    warnings = []
    intent_ids_on_disk = {o["id"] for o in list_objects(base, "intent")}
    for s in all_snaps:
        if s.get("intent_id") and s["intent_id"] not in intent_ids_on_disk:
            warnings.append(f"Orphan snap {s['id']}: intent {s['intent_id']} not found")

    print(json.dumps({
        "ok": True,
        "schema_version": config.get("schema_version", "0.6"),
        "active_intents": active_intents,
        "suspend_intents": suspend_intents,
        "active_decisions": active_decisions,
        "recent_snaps": recent_snaps,
        "warnings": warnings,
    }, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Intent commands
# ---------------------------------------------------------------------------

def cmd_intent_create(args):
    base = _require_init()
    obj_id = next_id(base, "intent")

    active_decisions = list_objects(base, "decision", status="active")
    decision_ids = [d["id"] for d in active_decisions]

    warnings = []
    if not decision_ids:
        warnings.append("No active decisions to attach.")

    intent = {
        "id": obj_id,
        "object": "intent",
        "created_at": _now(),
        "title": args.title,
        "status": "active",
        "source_query": args.query,
        "rationale": args.rationale,
        "decision_ids": decision_ids,
        "snap_ids": [],
    }
    write_object(base, "intent", obj_id, intent)

    for d in active_decisions:
        if obj_id not in d.get("intent_ids", []):
            d.setdefault("intent_ids", []).append(obj_id)
            write_object(base, "decision", d["id"], d)

    success("intent.create", intent, warnings)


def cmd_intent_list(args):
    base = _require_init()
    success("intent.list", list_objects(base, "intent", status=args.status))


def cmd_intent_show(args):
    base = _require_init()
    obj = read_object(base, "intent", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Intent {args.id} not found.")
    success("intent.show", obj)


def cmd_intent_activate(args):
    base = _require_init()
    obj = read_object(base, "intent", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Intent {args.id} not found.")
    if obj["status"] != "suspend":
        error("STATE_CONFLICT",
              f"Cannot activate intent with status '{obj['status']}'. Only 'suspend' intents can be activated.",
              suggested_fix=f"itt intent show {args.id}")

    obj["status"] = "active"

    active_decisions = list_objects(base, "decision", status="active")
    for d in active_decisions:
        if d["id"] not in obj["decision_ids"]:
            obj["decision_ids"].append(d["id"])
        if args.id not in d.get("intent_ids", []):
            d.setdefault("intent_ids", []).append(args.id)
            write_object(base, "decision", d["id"], d)

    write_object(base, "intent", args.id, obj)
    success("intent.activate", obj)


def cmd_intent_suspend(args):
    base = _require_init()
    obj = read_object(base, "intent", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Intent {args.id} not found.")
    if obj["status"] != "active":
        error("STATE_CONFLICT",
              f"Cannot suspend intent with status '{obj['status']}'. Only 'active' intents can be suspended.",
              suggested_fix=f"itt intent show {args.id}")

    obj["status"] = "suspend"
    write_object(base, "intent", args.id, obj)
    success("intent.suspend", obj)


def cmd_intent_done(args):
    base = _require_init()
    obj = read_object(base, "intent", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Intent {args.id} not found.")
    if obj["status"] != "active":
        error("STATE_CONFLICT",
              f"Cannot mark intent as done with status '{obj['status']}'. Only 'active' intents can be marked done.",
              suggested_fix=f"itt intent show {args.id}")

    obj["status"] = "done"
    write_object(base, "intent", args.id, obj)
    success("intent.done", obj)


# ---------------------------------------------------------------------------
# Snap commands
# ---------------------------------------------------------------------------

def cmd_snap_create(args):
    base = _require_init()
    intent_id = args.intent

    intent = read_object(base, "intent", intent_id)
    if intent is None:
        error("OBJECT_NOT_FOUND", f"Intent {intent_id} not found.")
    if intent["status"] != "active":
        error("STATE_CONFLICT",
              f"Cannot add snap to intent with status '{intent['status']}'. Only 'active' intents accept new snaps.",
              suggested_fix=f"itt intent activate {intent_id}")

    obj_id = next_id(base, "snap")
    snap = {
        "id": obj_id,
        "object": "snap",
        "created_at": _now(),
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
    base = _require_init()
    objects = list_objects(base, "snap", status=args.status)
    if args.intent:
        objects = [s for s in objects if s.get("intent_id") == args.intent]
    success("snap.list", objects)


def cmd_snap_show(args):
    base = _require_init()
    obj = read_object(base, "snap", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Snap {args.id} not found.")
    success("snap.show", obj)


def cmd_snap_feedback(args):
    base = _require_init()
    obj = read_object(base, "snap", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Snap {args.id} not found.")
    obj["feedback"] = args.feedback
    write_object(base, "snap", args.id, obj)
    success("snap.feedback", obj)


def cmd_snap_revert(args):
    base = _require_init()
    obj = read_object(base, "snap", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Snap {args.id} not found.")
    if obj["status"] != "active":
        error("STATE_CONFLICT",
              f"Cannot revert snap with status '{obj['status']}'. Only 'active' snaps can be reverted.",
              suggested_fix=f"itt snap show {args.id}")

    obj["status"] = "reverted"
    write_object(base, "snap", args.id, obj)
    success("snap.revert", obj)


# ---------------------------------------------------------------------------
# Decision commands
# ---------------------------------------------------------------------------

def cmd_decision_create(args):
    base = _require_init()
    obj_id = next_id(base, "decision")

    active_intents = list_objects(base, "intent", status="active")
    intent_ids = [i["id"] for i in active_intents]

    warnings = []
    if not intent_ids:
        warnings.append("No active intents to attach.")

    decision = {
        "id": obj_id,
        "object": "decision",
        "created_at": _now(),
        "title": args.title,
        "status": "active",
        "rationale": args.rationale,
        "intent_ids": intent_ids,
    }
    write_object(base, "decision", obj_id, decision)

    for i in active_intents:
        if obj_id not in i.get("decision_ids", []):
            i.setdefault("decision_ids", []).append(obj_id)
            write_object(base, "intent", i["id"], i)

    success("decision.create", decision, warnings)


def cmd_decision_list(args):
    base = _require_init()
    success("decision.list", list_objects(base, "decision", status=args.status))


def cmd_decision_show(args):
    base = _require_init()
    obj = read_object(base, "decision", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Decision {args.id} not found.")
    success("decision.show", obj)


def cmd_decision_deprecate(args):
    base = _require_init()
    obj = read_object(base, "decision", args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"Decision {args.id} not found.")
    if obj["status"] != "active":
        error("STATE_CONFLICT",
              f"Cannot deprecate decision with status '{obj['status']}'. Only 'active' decisions can be deprecated.",
              suggested_fix=f"itt decision show {args.id}")

    obj["status"] = "deprecated"
    write_object(base, "decision", args.id, obj)
    success("decision.deprecate", obj)


def cmd_decision_attach(args):
    base = _require_init()
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


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(prog="itt", description="Intent CLI")
    sub = parser.add_subparsers(dest="command")

    # version / init / inspect
    sub.add_parser("version")
    sub.add_parser("init")
    sub.add_parser("inspect")

    # --- intent ---
    p_intent = sub.add_parser("intent")
    s_intent = p_intent.add_subparsers(dest="sub")

    p = s_intent.add_parser("create")
    p.add_argument("title")
    p.add_argument("--query", default="")
    p.add_argument("--rationale", default="")

    p = s_intent.add_parser("list")
    p.add_argument("--status", default=None)

    p = s_intent.add_parser("show")
    p.add_argument("id")

    p = s_intent.add_parser("activate")
    p.add_argument("id")

    p = s_intent.add_parser("suspend")
    p.add_argument("id")

    p = s_intent.add_parser("done")
    p.add_argument("id")

    # --- snap ---
    p_snap = sub.add_parser("snap")
    s_snap = p_snap.add_subparsers(dest="sub")

    p = s_snap.add_parser("create")
    p.add_argument("title")
    p.add_argument("--intent", required=True)
    p.add_argument("--query", default="")
    p.add_argument("--rationale", default="")
    p.add_argument("--summary", default="")
    p.add_argument("--feedback", default="")

    p = s_snap.add_parser("list")
    p.add_argument("--intent", default=None)
    p.add_argument("--status", default=None)

    p = s_snap.add_parser("show")
    p.add_argument("id")

    p = s_snap.add_parser("feedback")
    p.add_argument("id")
    p.add_argument("feedback")

    p = s_snap.add_parser("revert")
    p.add_argument("id")

    # --- decision ---
    p_decision = sub.add_parser("decision")
    s_decision = p_decision.add_subparsers(dest="sub")

    p = s_decision.add_parser("create")
    p.add_argument("title")
    p.add_argument("--rationale", default="")

    p = s_decision.add_parser("list")
    p.add_argument("--status", default=None)

    p = s_decision.add_parser("show")
    p.add_argument("id")

    p = s_decision.add_parser("deprecate")
    p.add_argument("id")

    p = s_decision.add_parser("attach")
    p.add_argument("id")
    p.add_argument("--intent", required=True)

    # --- dispatch ---
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    dispatch_global = {
        "version": cmd_version,
        "init": cmd_init,
        "inspect": cmd_inspect,
    }
    if args.command in dispatch_global:
        dispatch_global[args.command](args)
        return

    if not getattr(args, "sub", None):
        {"intent": p_intent, "snap": p_snap, "decision": p_decision}[args.command].print_help()
        sys.exit(1)

    dispatch = {
        ("intent", "create"):    cmd_intent_create,
        ("intent", "list"):      cmd_intent_list,
        ("intent", "show"):      cmd_intent_show,
        ("intent", "activate"):  cmd_intent_activate,
        ("intent", "suspend"):   cmd_intent_suspend,
        ("intent", "done"):      cmd_intent_done,
        ("snap", "create"):      cmd_snap_create,
        ("snap", "list"):        cmd_snap_list,
        ("snap", "show"):        cmd_snap_show,
        ("snap", "feedback"):    cmd_snap_feedback,
        ("snap", "revert"):      cmd_snap_revert,
        ("decision", "create"):  cmd_decision_create,
        ("decision", "list"):    cmd_decision_list,
        ("decision", "show"):    cmd_decision_show,
        ("decision", "deprecate"): cmd_decision_deprecate,
        ("decision", "attach"):  cmd_decision_attach,
    }
    dispatch[(args.command, args.sub)](args)
