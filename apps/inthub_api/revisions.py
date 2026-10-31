"""The project's history: main and what was merged into it, like git log and git show."""

from apps.inthub_api.common import APIError
from apps.inthub_api.db import connect
from apps.inthub_api.queries import _project_row, without_email
from apps.inthub_api.repository import main_history, snapshot_at, tip_of_push
from intent_cli.hub.changes import COLLECTIONS, semantic_changes, summarize
from intent_cli.identity import FIELD_MAX_CHARS
from intent_cli.store_schema import SUBDIRS

LIST_LIMIT = 200  # objects shown per list of one revision; the counts stay exact
_OBJECT_FIELDS = ("id", "what", "status", "intent_id", "author", "origin", "git")


def _counts(revision):
    """Counts for the list, from what the revision recorded.

    Adding a Snap also changes its Intent's links, which is not news, so a change
    counts only when the revision added nothing. The detail view works out the rest.
    """
    counts = {f"{collection}_{kind}": 0 for collection in COLLECTIONS for kind in ("added", "changed")}
    changes = revision.get("changes")
    for change in changes if isinstance(changes, list) else []:
        obj_id, action = (change.get("id"), change.get("action")) if isinstance(change, dict) else (None, None)
        collection = SUBDIRS.get(obj_id.split("-", 1)[0]) if isinstance(obj_id, str) else None
        if collection and action in ("added", "changed"):
            counts[f"{collection}_{action}"] += 1
    if any(counts[f"{collection}_added"] for collection in COLLECTIONS):
        counts.update({f"{collection}_changed": 0 for collection in COLLECTIONS})
    return counts


def _pushers(conn, project_id):
    """The signed-in account behind each push, by the revision it left main on."""
    rows = conn.execute("""SELECT v.tip, a.login, a.display_name FROM semantic_versions v
        JOIN accounts a ON a.id = v.pushed_by WHERE v.project_id = ? AND v.tip IS NOT NULL""", (project_id,)).fetchall()
    return {row["tip"]: row for row in rows}


def _text(value):
    """A field a client wrote into its revision, which can hold anything."""
    return value[:FIELD_MAX_CHARS] if isinstance(value, str) else None


def _view(digest, revision, pushers, public=False):
    author = revision.get("author") if isinstance(revision.get("author"), dict) else {}
    pusher = {key: _text(author[key]) for key in ("name", "email") if _text(author.get(key))} or None
    row = pushers.get(digest)
    account = {"login": row["login"], "name": row["display_name"]} if row and row["login"] else None
    if public:
        # A visitor sees names only: a login can be an opaque Tenon subject.
        account = {"name": row["display_name"]} if row and row["display_name"] else None
        pusher = {key: value for key, value in pusher.items() if key != "email"} if pusher else None
    parents = revision["parents"]
    return {"revision": digest, "parent": parents[0] if parents else None, "parents": parents, "merge": len(parents) > 1,
            "created_at": _text(revision.get("time")), "pushed_by": account, "pusher": pusher,
            "title": _text(revision.get("summary")), "summary": _counts(revision)}


def project_revisions(db_path, project_id, offset=0, limit=30, account_id=None):
    """One page of main's revisions, newest first."""
    with connect(db_path) as conn:
        public = _project_row(conn, project_id, account_id)["permission"] == "public"
        history, _revisions = main_history(conn, project_id)
        pushers = _pushers(conn, project_id)
    page = history[offset:offset + limit]
    return {"project_id": project_id, "revisions": [_view(digest, revision, pushers, public) for digest, revision in page],
            "total": len(history), "offset": offset, "limit": limit, "has_more": offset + len(page) < len(history)}


def _brief(obj, verified, public):
    view = {key: obj[key] for key in _OBJECT_FIELDS if key in obj}
    if public:
        view = without_email(view)
    return {**view, "verified": True} if obj["id"] in verified else view


def revision_detail(db_path, project_id, revision, account_id=None):
    """What one revision changed from its first parent. Long lists are cut to LIST_LIMIT; their totals stay exact."""
    with connect(db_path) as conn:
        public = _project_row(conn, project_id, account_id)["permission"] == "public"
        history, revisions = main_history(conn, project_id)
        # Links made before the graph existed name the push's old revision ID.
        wanted = tip_of_push(conn, project_id, revision) or revision
        found = next((item for item in history if item[0] == wanted), None)
        if found is None:
            raise APIError("OBJECT_NOT_FOUND", f"Revision {revision} not found.", 404)
        digest, data = found
        parent = data["parents"][0] if data["parents"] else None
        changes = semantic_changes(snapshot_at(conn, project_id, revisions, parent), snapshot_at(conn, project_id, revisions, digest))
        verified = {row["object_id"] for row in conn.execute(
            "SELECT object_id FROM verified_objects WHERE project_id = ?", (project_id,)).fetchall()}
        pushers = _pushers(conn, project_id)
    listed = {}
    for collection in COLLECTIONS:
        added, changed = changes[collection]["added"], changes[collection]["changed"]
        listed[collection] = {
            "added": [_brief(obj, verified, public) for obj in added[:LIST_LIMIT]],
            "changed": [{"object": _brief(item["object"], verified, public), "changes": item["changes"]} for item in changed[:LIST_LIMIT]],
            "truncated": len(added) > LIST_LIMIT or len(changed) > LIST_LIMIT,
        }
    return {"project_id": project_id, **_view(digest, data, pushers, public), "summary": summarize(changes), "changes": listed}
