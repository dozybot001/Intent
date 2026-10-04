"""Account-private read views of the current shared project revision."""

from apps.inthub_api.common import APIError, make_remote_object_id, split_remote_object_id
from apps.inthub_api.db import connect
from apps.inthub_api.history import _head


def _project_row(conn, project_id, account_id=None):
    clause = "AND account_id = ?" if account_id else ""
    params = (project_id, account_id) if account_id else (project_id,)
    row = conn.execute(f"SELECT * FROM projects WHERE id = ? AND provider = 'intent' {clause}", params).fetchone()
    if row is None:
        raise APIError("OBJECT_NOT_FOUND", f"Project {project_id} not found.", 404)
    return row


def _load_project(db_path, project_id, account_id=None):
    with connect(db_path) as conn:
        project = dict(_project_row(conn, project_id, account_id))
        head = _head(conn, project_id)
    return project, head


def _project_view(project):
    return {key: project[key] for key in ("id", "name", "created_at")}


def _snapshot(head):
    return head["snapshot"] or {"intents": [], "snaps": [], "decisions": []}


def _entry(project_id, obj):
    return {**obj, "project_id": project_id, "remote_id": make_remote_object_id(project_id, obj["id"])}


def project_overview(db_path, project_id, account_id=None):
    project, head = _load_project(db_path, project_id, account_id)
    snapshot = _snapshot(head)
    intents = []
    for intent in snapshot["intents"]:
        snap_ids = intent["snap_ids"]
        intents.append({**_entry(project_id, intent), "latest_snap_id": snap_ids[-1] if snap_ids else None})
    decisions = [_entry(project_id, obj) for obj in snapshot["decisions"]]
    snaps = sorted((_entry(project_id, obj) for obj in snapshot["snaps"]),
                   key=lambda obj: obj["created_at"], reverse=True)
    return {
        "project": _project_view(project),
        "history": {"project_id": project_id, "revision": head["revision"],
                    "parent": head["parent"], "last_synced_at": head["accepted_at"]},
        "active_intents": [obj for obj in intents if obj["status"] == "active"],
        "other_intents": [obj for obj in intents if obj["status"] != "active"],
        "active_decisions": [obj for obj in decisions if obj["status"] == "active"],
        "deprecated_decisions": [obj for obj in decisions if obj["status"] == "deprecated"],
        "recent_snaps": snaps, "total_snaps": len(snaps),
    }


def list_projects(db_path, account_id=None):
    clause = "WHERE p.account_id = ?" if account_id else ""
    with connect(db_path) as conn:
        rows = conn.execute(f"""SELECT p.id, p.name, p.created_at, h.revision, v.created_at AS last_synced_at
            FROM projects p JOIN semantic_heads h ON h.project_id = p.id
            LEFT JOIN semantic_versions v ON v.project_id = h.project_id AND v.revision = h.revision
            {clause} ORDER BY COALESCE(v.created_at, p.created_at) DESC, p.created_at DESC""",
            (account_id,) if account_id else ()).fetchall()
    return {"projects": [dict(row) for row in rows]}


def project_handoff(db_path, project_id, account_id=None):
    project, head = _load_project(db_path, project_id, account_id)
    snapshot = _snapshot(head)
    snaps = {obj["id"]: obj for obj in snapshot["snaps"]}
    intents = []
    for intent in snapshot["intents"]:
        if intent["status"] not in {"active", "suspend"}:
            continue
        latest = snaps.get(intent["snap_ids"][-1]) if intent["snap_ids"] else None
        intents.append({**_entry(project_id, intent), "latest_snap": latest, "synced_at": head["accepted_at"]})
    return {
        "project": _project_view(project),
        "active_decisions": [_entry(project_id, obj) for obj in snapshot["decisions"] if obj["status"] == "active"],
        "intents": [obj for obj in intents if obj["status"] == "active"],
        "suspended_intents": [obj for obj in intents if obj["status"] == "suspend"],
    }


def _detail(db_path, remote_object_id, collection, account_id=None):
    try:
        project_id, local_id = split_remote_object_id(remote_object_id)
    except ValueError as exc:
        raise APIError("INVALID_INPUT", "Invalid remote object ID.") from exc
    _, head = _load_project(db_path, project_id, account_id)
    snapshot = _snapshot(head)
    obj = next((obj for obj in snapshot[collection] if obj["id"] == local_id), None)
    if obj is None:
        raise APIError("OBJECT_NOT_FOUND", f"Object {remote_object_id} not found.", 404)
    return {"remote_id": remote_object_id, "project_id": project_id, "id": local_id,
            "synced_at": head["accepted_at"]}, obj, snapshot


def get_intent_detail(db_path, remote_object_id, account_id=None):
    result, intent, snapshot = _detail(db_path, remote_object_id, "intents", account_id)
    snaps = {obj["id"]: obj for obj in snapshot["snaps"]}
    decisions = {obj["id"]: obj for obj in snapshot["decisions"]}
    return {**result, "intent": intent,
            "snaps": [snaps[obj_id] for obj_id in intent["snap_ids"]],
            "decisions": [decisions[obj_id] for obj_id in intent["decision_ids"]]}


def get_decision_detail(db_path, remote_object_id, account_id=None):
    result, decision, snapshot = _detail(db_path, remote_object_id, "decisions", account_id)
    intents = {obj["id"]: obj for obj in snapshot["intents"]}
    return {**result, "decision": decision, "intents": [intents[obj_id] for obj_id in decision["intent_ids"]]}


def get_snap_detail(db_path, remote_object_id, account_id=None):
    result, snap, snapshot = _detail(db_path, remote_object_id, "snaps", account_id)
    intent = next(obj for obj in snapshot["intents"] if obj["id"] == snap["intent_id"])
    return {**result, "snap": snap, "intent": intent}


def search_project(db_path, project_id, query, account_id=None):
    _, head = _load_project(db_path, project_id, account_id)
    q = (query or "").strip().lower()
    matches = []
    if q:
        for collection, objects in _snapshot(head).items():
            for obj in objects:
                if q in f"{obj['what']} {obj['why']}".lower():
                    matches.append({**_entry(project_id, obj), "object_type": collection[:-1]})
    return {"project_id": project_id, "query": query, "matches": matches}
