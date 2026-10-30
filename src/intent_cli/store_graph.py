"""Check that objects agree with each other once they are loaded."""

from intent_cli import relations as relation_rules
from intent_cli.store_schema import VALID_STATUSES


def validate_graph(graph):
    """Validate one in-memory graph without reading storage again."""
    intents = graph["intent"]
    snaps = graph["snap"]
    decisions = graph["decision"]
    issues = list(graph.get("load_issues", []))

    def add_issue(code, object_type, obj_id, message):
        issues.append({
            "code": code,
            "object": object_type,
            "id": obj_id,
            "message": message,
        })

    for object_type, objects in (
        ("intent", intents),
        ("snap", snaps),
        ("decision", decisions),
    ):
        for obj_id, obj in objects.items():
            if obj.get("object") != object_type:
                add_issue(
                    "OBJECT_TYPE_MISMATCH",
                    object_type,
                    obj_id,
                    f"Stored object type is '{obj.get('object')}', expected '{object_type}'.",
                )
            if object_type in VALID_STATUSES:
                status = obj.get("status")
                if status not in VALID_STATUSES[object_type]:
                    add_issue(
                        "INVALID_STATUS",
                        object_type,
                        obj_id,
                        f"Invalid status '{status}' for {object_type}.",
                    )

    for intent_id, intent in intents.items():
        for snap_id in intent.get("snap_ids", []):
            snap = snaps.get(snap_id)
            if snap is None:
                add_issue(
                    "MISSING_REFERENCE",
                    "intent",
                    intent_id,
                    f"References missing snap {snap_id} in snap_ids.",
                )
                continue
            if snap.get("intent_id") != intent_id:
                add_issue(
                    "BROKEN_LINK",
                    "intent",
                    intent_id,
                    f"Snap {snap_id} points to intent {snap.get('intent_id')}, not {intent_id}.",
                )
        for decision_id in intent.get("decision_ids", []):
            decision = decisions.get(decision_id)
            if decision is None:
                add_issue(
                    "MISSING_REFERENCE",
                    "intent",
                    intent_id,
                    f"References missing decision {decision_id} in decision_ids.",
                )
                continue
            if intent_id not in decision.get("intent_ids", []):
                add_issue(
                    "BROKEN_LINK",
                    "intent",
                    intent_id,
                    f"Decision {decision_id} does not link back to this intent.",
                )

    for snap_id, snap in snaps.items():
        intent_id = snap.get("intent_id")
        intent = intents.get(intent_id)
        if intent is None:
            add_issue(
                "MISSING_REFERENCE",
                "snap",
                snap_id,
                f"Points to missing intent {intent_id}.",
            )
            continue
        if snap_id not in intent.get("snap_ids", []):
            add_issue(
                "BROKEN_LINK",
                "snap",
                snap_id,
                f"Intent {intent_id} does not include this snap in snap_ids.",
            )

    for decision_id, decision in decisions.items():
        for intent_id in decision.get("intent_ids", []):
            intent = intents.get(intent_id)
            if intent is None:
                add_issue(
                    "MISSING_REFERENCE",
                    "decision",
                    decision_id,
                    f"References missing intent {intent_id} in intent_ids.",
                )
                continue
            if decision_id not in intent.get("decision_ids", []):
                add_issue(
                    "BROKEN_LINK",
                    "decision",
                    decision_id,
                    f"Intent {intent_id} does not link back to this decision.",
                )

    for intent_id, intent in intents.items():
        for entry in relation_rules.active_entries(intent):
            if entry["intent"] not in intents:
                add_issue(
                    "MISSING_REFERENCE",
                    "intent",
                    intent_id,
                    f"Relation {entry['type']} points to missing intent {entry['intent']}.",
                )
    for intent_id, message in relation_rules.graph_issues(intents):
        add_issue("INVALID_RELATION", "intent", intent_id, message)
    for decision_id, decision in decisions.items():
        source = decision.get("source_intent_id")
        if source is not None and source not in intents:
            add_issue(
                "MISSING_REFERENCE",
                "decision",
                decision_id,
                f"Source intent {source} is missing.",
            )

    return {
        "healthy": not issues,
        "issues": issues,
    }
