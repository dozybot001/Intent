"""Record Snaps and Decisions."""

from intent_cli import identity
from intent_cli.commands.common import now_utc, require_init, workspace_mutation
from intent_cli.origin import detect_origin
from intent_cli.output import error, json_mode, success
from intent_cli.store import CHECKPOINT_FIELDS, CHECKPOINT_FIELD_MAX_CHARS, create_object, list_objects, next_id, read_object, update_object, validate_object_id
from intent_cli.commands.intents import _attribute, _require_text


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
    _attribute(snap)
    commit = identity.commit()
    if commit:
        snap["git"] = commit
    create_object(base, "snap", obj_id, snap)

    intent.setdefault("snap_ids", []).append(obj_id)
    update_object(base, "intent", intent_id, intent)

    warnings = []
    if inferred and json_mode():
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
    if not intent_ids and json_mode():
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
    _attribute(decision)
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
