"""Read views of the current shared project revision, for whoever may see the project."""

import json

from apps.inthub_api.access import VISITOR, permission, role_level
from apps.inthub_api.common import APIError, make_remote_object_id, split_remote_object_id
from apps.inthub_api.db import connect
from apps.inthub_api.history import _head


def _project_row(conn, project_id, account_id=None):
    row = conn.execute("SELECT * FROM projects WHERE id = ? AND provider = 'intent'", (project_id,)).fetchone()
    level = permission(conn, row, account_id) if row else None
    if level is None:
        # The same answer for a private project and a missing one.
        if account_id == VISITOR:
            raise APIError("AUTH_REQUIRED", "Sign in to continue.", 401)
        raise APIError("OBJECT_NOT_FOUND", f"Project {project_id} not found.", 404)
    return {**dict(row), "permission": level}


def without_email(obj):
    """Author emails come from Git config and can be private, so visitors never get them."""
    author = obj.get("author")
    return {**obj, "author": {key: value for key, value in author.items() if key != "email"}} if author else obj


def _owner(conn, project):
    if project["team_id"]:
        team = conn.execute("SELECT id, slug, name FROM teams WHERE id = ?", (project["team_id"],)).fetchone()
        return {"type": "team", **dict(team)}
    account = conn.execute("SELECT display_name FROM accounts WHERE id = ?", (project["account_id"],)).fetchone() if project["account_id"] else None
    return {"type": "account", "name": account["display_name"] if account else None}


def _load_project(db_path, project_id, account_id=None):
    with connect(db_path) as conn:
        project = _project_row(conn, project_id, account_id)
        project["owner"] = _owner(conn, project)
        head = _head(conn, project_id)
        verified = {row["object_id"] for row in conn.execute(
            "SELECT object_id FROM verified_objects WHERE project_id = ?", (project_id,)).fetchall()}
    # Every read view starts here, so each gets the flag; the stored snapshot does not change.
    for objects in _snapshot(head).values():
        for obj in objects:
            if obj["id"] in verified:
                obj["verified"] = True
    if project["permission"] == "public" and head["snapshot"]:
        head["snapshot"] = {collection: [without_email(obj) for obj in objects] for collection, objects in head["snapshot"].items()}
    return project, head


def _full_name(slug, name):
    return f"{slug}/{name}" if slug else name


def _project_view(project):
    owner = project["owner"]
    return {**{key: project[key] for key in ("id", "name", "created_at", "repository_url", "visibility", "permission")},
            "full_name": _full_name(owner.get("slug"), project["name"]), "owner": owner}


def _snapshot(head):
    return head["snapshot"] or {"intents": [], "snaps": [], "decisions": []}


def _entry(project_id, obj):
    return {**obj, "project_id": project_id, "remote_id": make_remote_object_id(project_id, obj["id"])}


OVERVIEW_SNAPS = 20  # the rest of the timeline is paged through project_snaps
SNAP_PAGE_MAX = 200
SEARCH_LIMIT = 50


def _author_key(obj):
    author = obj.get("author") or {}
    return author.get("email") or author.get("name")


def _authors(snaps):
    """Everyone with a Snap in this project, most active first, for the timeline filter."""
    authors = {}
    for snap in snaps:
        key = _author_key(snap)
        if key:
            entry = authors.setdefault(key, {"key": key, "name": snap["author"].get("name") or key, "snaps": 0})
            entry["snaps"] += 1
    return sorted(authors.values(), key=lambda entry: -entry["snaps"])


def _newest_first(project_id, snaps):
    return sorted((_entry(project_id, obj) for obj in snaps), key=lambda obj: obj["created_at"], reverse=True)


def project_overview(db_path, project_id, account_id=None):
    project, head = _load_project(db_path, project_id, account_id)
    snapshot = _snapshot(head)
    intents = []
    for intent in snapshot["intents"]:
        snap_ids = intent["snap_ids"]
        intents.append({**_entry(project_id, intent), "latest_snap_id": snap_ids[-1] if snap_ids else None})
    decisions = [_entry(project_id, obj) for obj in snapshot["decisions"]]
    snaps = _newest_first(project_id, snapshot["snaps"])
    return {
        "project": _project_view(project),
        "history": {"project_id": project_id, "revision": head["revision"],
                    "parent": head["parent"], "last_synced_at": head["accepted_at"]},
        "active_intents": [obj for obj in intents if obj["status"] == "active"],
        "other_intents": [obj for obj in intents if obj["status"] != "active"],
        "active_decisions": [obj for obj in decisions if obj["status"] == "active"],
        "deprecated_decisions": [obj for obj in decisions if obj["status"] == "deprecated"],
        "recent_snaps": snaps[:OVERVIEW_SNAPS], "total_snaps": len(snaps), "authors": _authors(snaps),
    }


def project_snaps(db_path, project_id, offset=0, limit=50, intent_id=None, author=None, account_id=None):
    """One page of the timeline, newest first, optionally for one Intent or one author."""
    _, head = _load_project(db_path, project_id, account_id)
    snaps = _snapshot(head)["snaps"]
    if intent_id is not None:
        snaps = [obj for obj in snaps if obj["intent_id"] == intent_id]
    if author is not None:
        snaps = [obj for obj in snaps if _author_key(obj) == author]
    ordered = _newest_first(project_id, snaps)
    page = ordered[offset:offset + limit]
    return {"project_id": project_id, "snaps": page, "total": len(ordered),
            "offset": offset, "limit": limit, "has_more": offset + len(page) < len(ordered)}


def project_rows(conn, account_id=None, *, team_id=None, snapshots=False):
    """Projects the viewer works on, most recently synced first; one team's when team_id is given."""
    where = "p.team_id = ?" if team_id else "(p.account_id = ? OR m.account_id IS NOT NULL)" if account_id else "1 = 1"
    params = (account_id, *((team_id,) if team_id else (account_id,) if account_id else ()))
    rows = conn.execute(f"""SELECT p.id, p.name, p.created_at, p.visibility, p.team_id, t.slug AS team_slug, t.name AS team_name,
            m.role AS team_role, h.revision, v.created_at AS last_synced_at{", v.snapshot_json" if snapshots else ""}
        FROM projects p JOIN semantic_heads h ON h.project_id = p.id
        LEFT JOIN semantic_versions v ON v.project_id = h.project_id AND v.revision = h.revision
        LEFT JOIN teams t ON t.id = p.team_id
        LEFT JOIN team_members m ON m.team_id = p.team_id AND m.account_id = ?
        WHERE {where} ORDER BY COALESCE(v.created_at, p.created_at) DESC, p.created_at DESC""", params).fetchall()
    return [{"id": row["id"], "name": row["name"], "full_name": _full_name(row["team_slug"], row["name"]),
             "created_at": row["created_at"], "revision": row["revision"], "last_synced_at": row["last_synced_at"],
             "visibility": row["visibility"], "permission": role_level(row["team_role"]) if row["team_role"] else "admin",
             "team": {"id": row["team_id"], "slug": row["team_slug"], "name": row["team_name"]} if row["team_id"] else None,
             **({"snapshot_json": row["snapshot_json"]} if snapshots else {})} for row in rows]


def list_projects(db_path, account_id=None):
    with connect(db_path) as conn:
        return {"projects": project_rows(conn, account_id)}


_CLEAR_BLOCKERS = {"none", "n/a", "not blocked", "no blocker", "无", "没有", "无阻塞", "暂无"}


def _blocked(snap):
    blocker = str((snap or {}).get("checkpoint", {}).get("blocker") or "").strip().lower().rstrip(".!。！")
    return bool(blocker) and blocker not in _CLEAR_BLOCKERS


def project_home(db_path, account_id=None):
    """Every project the viewer works on, and how many of its active Intents are blocked."""
    with connect(db_path) as conn:
        projects = project_rows(conn, account_id, snapshots=True)
    for project in projects:
        snapshot = json.loads(project.pop("snapshot_json") or '{"intents": [], "snaps": []}')
        snaps = {snap["id"]: snap for snap in snapshot["snaps"]}
        active = [intent for intent in snapshot["intents"] if intent["status"] == "active"]
        project.update(active_intents=len(active), total_snaps=len(snaps),
                       blocked_intents=sum(1 for intent in active if intent["snap_ids"] and _blocked(snaps.get(intent["snap_ids"][-1]))))
    return {"projects": projects}


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
                # Only Snaps carry the validated checkpoint contract.
                checkpoint = obj.get("checkpoint", {}) if collection == "snaps" else {}
                if q in " ".join((obj["what"], obj["why"], *checkpoint.values())).lower():
                    matches.append({**_entry(project_id, obj), "object_type": collection[:-1]})
    return {"project_id": project_id, "query": query, "matches": matches[:SEARCH_LIMIT],
            "total": len(matches), "truncated": len(matches) > SEARCH_LIMIT}
