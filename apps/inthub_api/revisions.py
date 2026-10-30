"""The project's history: one revision per accepted push, like git log and git show."""

import json

from apps.inthub_api.common import APIError
from apps.inthub_api.db import connect
from apps.inthub_api.queries import _project_row
from intent_cli.hub.changes import COLLECTIONS, semantic_changes, summarize

LIST_LIMIT = 200  # objects shown per list of one revision; the counts stay exact
_OBJECT_FIELDS = ("id", "what", "status", "intent_id", "author", "origin", "git")


def _snapshot(conn, project_id, revision):
    if revision is None:
        return None
    row = conn.execute("SELECT snapshot_json FROM semantic_versions WHERE project_id = ? AND revision = ?",
                       (project_id, revision)).fetchone()
    return json.loads(row["snapshot_json"])


def _view(conn, project_id, row):
    summary = row["changes_json"]
    if summary is None:
        # Revisions from before 7.4: worked out once, then kept like newer ones.
        summary = json.dumps(summarize(semantic_changes(
            _snapshot(conn, project_id, row["parent"]), _snapshot(conn, project_id, row["revision"]))))
        conn.execute("UPDATE semantic_versions SET changes_json = ? WHERE project_id = ? AND revision = ?",
                     (summary, project_id, row["revision"]))
    account = {"login": row["login"], "name": row["display_name"]} if row["login"] else None
    return {"revision": row["revision"], "parent": row["parent"], "created_at": row["created_at"],
            "pushed_by": account, "pusher": json.loads(row["pusher_json"]) if row["pusher_json"] else None,
            "summary": json.loads(summary)}


_SELECT = """SELECT v.revision, v.parent, v.created_at, v.pusher_json, v.changes_json, a.login, a.display_name
    FROM semantic_versions v LEFT JOIN accounts a ON a.id = v.pushed_by WHERE v.project_id = ?"""


def project_revisions(db_path, project_id, offset=0, limit=30, account_id=None):
    """One page of revisions, newest first."""
    with connect(db_path) as conn:
        _project_row(conn, project_id, account_id)
        total = conn.execute("SELECT count(*) AS n FROM semantic_versions WHERE project_id = ?", (project_id,)).fetchone()["n"]
        rows = conn.execute(f"{_SELECT} ORDER BY v.created_at DESC, v.revision LIMIT ? OFFSET ?",
                            (project_id, limit, offset)).fetchall()
        revisions = [_view(conn, project_id, row) for row in rows]
    return {"project_id": project_id, "revisions": revisions, "total": total,
            "offset": offset, "limit": limit, "has_more": offset + len(revisions) < total}


def _brief(obj, verified):
    view = {key: obj[key] for key in _OBJECT_FIELDS if key in obj}
    return {**view, "verified": True} if obj["id"] in verified else view


def revision_detail(db_path, project_id, revision, account_id=None):
    """What one revision changed. Long lists are cut to LIST_LIMIT; their totals stay exact."""
    with connect(db_path) as conn:
        _project_row(conn, project_id, account_id)
        row = conn.execute(f"{_SELECT} AND v.revision = ?", (project_id, revision)).fetchone()
        if row is None:
            raise APIError("OBJECT_NOT_FOUND", f"Revision {revision} not found.", 404)
        view = _view(conn, project_id, row)
        changes = semantic_changes(_snapshot(conn, project_id, row["parent"]), _snapshot(conn, project_id, revision))
        verified = {found["object_id"] for found in conn.execute(
            "SELECT object_id FROM verified_objects WHERE project_id = ?", (project_id,)).fetchall()}
    listed = {}
    for collection in COLLECTIONS:
        added, changed = changes[collection]["added"], changes[collection]["changed"]
        listed[collection] = {
            "added": [_brief(obj, verified) for obj in added[:LIST_LIMIT]],
            "changed": [{"object": _brief(item["object"], verified), "changes": item["changes"]} for item in changed[:LIST_LIMIT]],
            "truncated": len(added) > LIST_LIMIT or len(changed) > LIST_LIMIT,
        }
    return {"project_id": project_id, **view, "changes": listed}
