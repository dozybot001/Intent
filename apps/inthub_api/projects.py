"""Project management from the browser: rename, delete and export.

History itself is written only by CLI pushes; these change a project's name or remove it.
"""

from apps.inthub_api.common import APIError, now_utc
from apps.inthub_api.db import connect
from apps.inthub_api.history import _head, _project, _project_by_id, project_name

EXPORT_FORMAT_VERSION = 1


def _owned(conn, project_id, account_id):
    project = _project_by_id(conn, project_id, account_id)
    if project is None:
        raise APIError("OBJECT_NOT_FOUND", f"Project {project_id} not found.", 404)
    return project


def _view(project, name=None):
    return {"id": project["id"], "name": name or project["repo_id"], "created_at": project["created_at"]}


def rename_project(db_path, project_id, name, account_id=None):
    name = project_name(name)
    with connect(db_path) as conn:
        project = _owned(conn, project_id, account_id)
        if project["repo_id"] != name:
            if _project(conn, name, account_id) is not None:
                raise APIError("NAME_TAKEN", f"You already have a project named {name}.", 409)
            # CLIs look projects up by ID first, so existing clones follow the new name.
            conn.execute("UPDATE projects SET name = ?, repo_id = ?, repo_name = ? WHERE id = ?",
                         (name, name, name, project_id))
    return {"project": _view(project, name)}


def delete_project(db_path, project_id, confirm, account_id=None):
    with connect(db_path) as conn:
        project = _owned(conn, project_id, account_id)
        if confirm != project["repo_id"]:
            raise APIError("CONFIRMATION_MISMATCH", "Type the project name exactly to delete it.", 400)
        # Same tables as account deletion, for one project. Local .intent directories are untouched.
        for table in ("public_profile_projects", "semantic_heads", "semantic_versions", "sync_batches", "workspaces"):
            conn.execute(f"DELETE FROM {table} WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return {"deleted": True, "id": project_id}


def export_project(db_path, project_id, account_id=None):
    with connect(db_path) as conn:
        project = _owned(conn, project_id, account_id)
        head = _head(conn, project_id)
        parents = {row["revision"]: row for row in conn.execute(
            "SELECT revision, parent, created_at FROM semantic_versions WHERE project_id = ?", (project_id,)).fetchall()}
    # Pushes only fast-forward, so the revisions form one chain from the head.
    revisions, revision = [], head["revision"]
    while revision in parents:
        row = parents.pop(revision)
        revisions.append({"revision": row["revision"], "parent": row["parent"], "created_at": row["created_at"]})
        revision = row["parent"]
    return {
        "format": "inthub-export",
        "format_version": EXPORT_FORMAT_VERSION,
        "exported_at": now_utc(),
        "project": _view(project),
        "head": {"revision": head["revision"], "parent": head["parent"], "accepted_at": head["accepted_at"]},
        "snapshot": head["snapshot"] or {"intents": [], "snaps": [], "decisions": []},
        "revisions": revisions,
    }
