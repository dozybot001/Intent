"""Read-model queries for the IntHub API."""

import json

from apps.inthub_api.common import APIError, make_remote_object_id, split_remote_object_id
from apps.inthub_api.db import connect


def _f(obj, key):
    """Read field, return empty string if missing."""
    return obj.get(key, "")


def _project_row(conn, project_id):
    project = conn.execute(
        "SELECT * FROM projects WHERE id = ?",
        (project_id,),
    ).fetchone()
    if project is None:
        raise APIError("OBJECT_NOT_FOUND", f"Project {project_id} not found.", status=404)
    return project


def _latest_payloads(conn, project_id):
    rows = conn.execute(
        """
        SELECT sb.payload_json
        FROM sync_batches AS sb
        JOIN (
            SELECT workspace_id, MAX(rowid) AS max_rowid
            FROM sync_batches
            WHERE project_id = ?
            GROUP BY workspace_id
        ) latest
        ON sb.rowid = latest.max_rowid
        ORDER BY sb.accepted_at DESC
        """,
        (project_id,),
    ).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


def _workspace_state(payload):
    return {
        "workspace_id": payload["workspace"]["workspace_id"],
        "last_synced_at": payload.get("generated_at"),
        "branch": payload.get("git", {}).get("branch"),
        "head_commit": payload.get("git", {}).get("head_commit"),
        "dirty": payload.get("git", {}).get("dirty"),
    }


def _latest_snap_for_intent(intent, snaps):
    snap_ids = intent.get("snap_ids", [])
    if not snap_ids:
        return None
    latest_id = snap_ids[-1]
    for snap in snaps:
        if snap["id"] == latest_id:
            return snap
    return None


def _latest_payload_for_workspace(conn, workspace_id):
    row = conn.execute(
        """
        SELECT payload_json
        FROM sync_batches
        WHERE workspace_id = ?
        ORDER BY rowid DESC
        LIMIT 1
        """,
        (workspace_id,),
    ).fetchone()
    if row is None:
        raise APIError(
            "OBJECT_NOT_FOUND",
            f"No sync batch found for workspace {workspace_id}.",
            status=404,
        )
    return json.loads(row["payload_json"])


def project_overview(db_path, project_id):
    with connect(db_path) as conn:
        project = _project_row(conn, project_id)
        payloads = _latest_payloads(conn, project_id)

    active_intents = []
    other_intents = []
    active_decisions = []
    deprecated_decisions = []
    recent_snaps = []
    workspaces = []

    for payload in payloads:
        workspace_id = payload["workspace"]["workspace_id"]
        snapshot = payload.get("snapshot", {})
        git = payload.get("git", {})
        workspaces.append(_workspace_state(payload))

        intents = snapshot.get("intents", [])
        snaps = snapshot.get("snaps", [])
        decisions = snapshot.get("decisions", [])
        snap_map = {s["id"]: s for s in snaps}

        for intent in intents:
            latest_snap_id = intent.get("snap_ids", [])[-1] if intent.get("snap_ids") else None
            latest_snap = snap_map.get(latest_snap_id) if latest_snap_id else None
            entry = {
                "remote_id": make_remote_object_id(workspace_id, intent["id"]),
                "workspace_id": workspace_id,
                "id": intent["id"],
                "what": _f(intent, "what"),
                "status": intent["status"],
                "decision_ids": intent.get("decision_ids", []),
                "latest_snap_id": latest_snap_id,
                "origin": intent.get("origin", ""),
                "why": _f(intent, "why"),
                "branch": git.get("branch"),
                "head_commit": git.get("head_commit"),
                "dirty": git.get("dirty"),
            }
            if intent.get("status") == "active":
                active_intents.append(entry)
            else:
                other_intents.append(entry)

        for decision in decisions:
            entry = {
                "remote_id": make_remote_object_id(workspace_id, decision["id"]),
                "workspace_id": workspace_id,
                "id": decision["id"],
                "what": _f(decision, "what"),
                "status": decision["status"],
                "why": _f(decision, "why"),
                "intent_ids": decision.get("intent_ids", []),
            }
            if decision.get("status") == "active":
                active_decisions.append(entry)
            elif decision.get("status") == "deprecated":
                deprecated_decisions.append(entry)

        for snap in snaps:
            recent_snaps.append({
                "remote_id": make_remote_object_id(workspace_id, snap["id"]),
                "workspace_id": workspace_id,
                "id": snap["id"],
                "what": _f(snap, "what"),
                "intent_id": snap.get("intent_id"),
                "why": _f(snap, "why"),
                "origin": snap.get("origin", ""),
                "created_at": snap.get("created_at"),
            })

    recent_snaps.sort(key=lambda snap: snap.get("created_at", ""), reverse=True)
    return {
        "project": {
            "id": project["id"],
            "name": project["name"],
            "repo": {
                "provider": project["provider"],
                "repo_id": project["repo_id"],
                "owner": project["owner"],
                "name": project["repo_name"],
            },
        },
        "workspaces": workspaces,
        "active_intents": active_intents,
        "other_intents": other_intents,
        "active_decisions": active_decisions,
        "deprecated_decisions": deprecated_decisions,
        "recent_snaps": recent_snaps,
    }


def list_projects(db_path):
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                p.*,
                COUNT(DISTINCT w.id) AS workspace_count,
                MAX(sb.accepted_at) AS last_synced_at
            FROM projects AS p
            LEFT JOIN workspaces AS w
                ON w.project_id = p.id
            LEFT JOIN sync_batches AS sb
                ON sb.project_id = p.id
            GROUP BY p.id
            ORDER BY COALESCE(MAX(sb.accepted_at), p.created_at) DESC, p.created_at DESC
            """
        ).fetchall()

    return {
        "projects": [
            {
                "id": row["id"],
                "name": row["name"],
                "repo": {
                    "provider": row["provider"],
                    "repo_id": row["repo_id"],
                    "owner": row["owner"],
                    "name": row["repo_name"],
                },
                "workspace_count": row["workspace_count"],
                "last_synced_at": row["last_synced_at"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
    }


def project_handoff(db_path, project_id):
    with connect(db_path) as conn:
        project = _project_row(conn, project_id)
        payloads = _latest_payloads(conn, project_id)

    intents_view = []
    active_decisions = []

    for payload in payloads:
        workspace_id = payload["workspace"]["workspace_id"]
        snapshot = payload.get("snapshot", {})
        git = payload.get("git", {})
        intents = snapshot.get("intents", [])
        snaps = snapshot.get("snaps", [])
        decisions = snapshot.get("decisions", [])

        for decision in decisions:
            if decision.get("status") == "active":
                active_decisions.append({
                    "remote_id": make_remote_object_id(workspace_id, decision["id"]),
                    "workspace_id": workspace_id,
                    "id": decision["id"],
                    "what": _f(decision, "what"),
                    "status": decision["status"],
                })

        for intent in intents:
            if intent.get("status") != "active":
                continue
            latest_snap = _latest_snap_for_intent(intent, snaps)
            intents_view.append({
                "remote_id": make_remote_object_id(workspace_id, intent["id"]),
                "workspace_id": workspace_id,
                "id": intent["id"],
                "what": _f(intent, "what"),
                "status": intent["status"],
                "why": _f(intent, "why"),
                "decision_ids": intent.get("decision_ids", []),
                "latest_snap": latest_snap,
                "git": {
                    "branch": git.get("branch"),
                    "head_commit": git.get("head_commit"),
                    "dirty": git.get("dirty"),
                },
                "synced_at": payload.get("generated_at"),
            })

    return {
        "project": {
            "id": project["id"],
            "name": project["name"],
        },
        "active_decisions": active_decisions,
        "intents": intents_view,
    }


def get_intent_detail(db_path, remote_object_id):
    workspace_id, local_object_id = split_remote_object_id(remote_object_id)
    with connect(db_path) as conn:
        payload = _latest_payload_for_workspace(conn, workspace_id)

    snapshot = payload.get("snapshot", {})
    intents = snapshot.get("intents", [])
    snaps = snapshot.get("snaps", [])
    for intent in intents:
        if intent["id"] != local_object_id:
            continue
        related_snaps = [snap for snap in snaps if snap.get("intent_id") == local_object_id]
        return {
            "remote_id": remote_object_id,
            "workspace_id": workspace_id,
            "id": local_object_id,
            "intent": intent,
            "snaps": related_snaps,
            "git": payload.get("git", {}),
            "synced_at": payload.get("generated_at"),
        }
    raise APIError("OBJECT_NOT_FOUND", f"Intent {remote_object_id} not found.", status=404)


def get_decision_detail(db_path, remote_object_id):
    workspace_id, local_object_id = split_remote_object_id(remote_object_id)
    with connect(db_path) as conn:
        payload = _latest_payload_for_workspace(conn, workspace_id)

    snapshot = payload.get("snapshot", {})
    decisions = snapshot.get("decisions", [])
    intents = snapshot.get("intents", [])
    for decision in decisions:
        if decision["id"] != local_object_id:
            continue
        related_intents = [intent for intent in intents if intent["id"] in decision.get("intent_ids", [])]
        return {
            "remote_id": remote_object_id,
            "workspace_id": workspace_id,
            "id": local_object_id,
            "decision": decision,
            "intents": related_intents,
            "synced_at": payload.get("generated_at"),
        }
    raise APIError("OBJECT_NOT_FOUND", f"Decision {remote_object_id} not found.", status=404)


def get_snap_detail(db_path, remote_object_id):
    workspace_id, local_object_id = split_remote_object_id(remote_object_id)
    with connect(db_path) as conn:
        payload = _latest_payload_for_workspace(conn, workspace_id)

    snapshot = payload.get("snapshot", {})
    snaps = snapshot.get("snaps", [])
    intents = snapshot.get("intents", [])
    for snap in snaps:
        if snap["id"] != local_object_id:
            continue
        parent_intent = None
        intent_id = snap.get("intent_id")
        if intent_id:
            for intent in intents:
                if intent["id"] == intent_id:
                    parent_intent = intent
                    break
        return {
            "remote_id": remote_object_id,
            "workspace_id": workspace_id,
            "id": local_object_id,
            "snap": snap,
            "intent": parent_intent,
            "git": payload.get("git", {}),
            "synced_at": payload.get("generated_at"),
        }
    raise APIError("OBJECT_NOT_FOUND", f"Snap {remote_object_id} not found.", status=404)


def search_project(db_path, project_id, query):
    with connect(db_path) as conn:
        _project_row(conn, project_id)
        payloads = _latest_payloads(conn, project_id)

    q = (query or "").strip().lower()
    matches = []
    if not q:
        return {"project_id": project_id, "query": query, "matches": matches}

    for payload in payloads:
        workspace_id = payload["workspace"]["workspace_id"]
        snapshot = payload.get("snapshot", {})
        for object_type in ("intents", "snaps", "decisions"):
            for obj in snapshot.get(object_type, []):
                fields = [
                    obj.get("what", ""),
                    obj.get("why", ""),
                ]
                haystack = " ".join(fields).lower()
                if q not in haystack:
                    continue
                matches.append({
                    "object_type": object_type[:-1],
                    "remote_id": make_remote_object_id(workspace_id, obj["id"]),
                    "workspace_id": workspace_id,
                    "id": obj["id"],
                    "what": obj.get("what", ""),
                    "status": obj.get("status", ""),
                })

    return {"project_id": project_id, "query": query, "matches": matches}
