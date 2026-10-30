"""Project management from the browser: rename, visibility, transfer, delete and export.

History itself is written only by CLI pushes; these change how a project is named and
who can see it, or remove it.
"""

from apps.inthub_api.access import permission, project_handle, team_role
from apps.inthub_api.common import APIError, now_utc
from apps.inthub_api.db import connect
from apps.inthub_api.history import _head, _project, _project_by_id, _team_project, project_name

EXPORT_FORMAT_VERSION = 1
VISIBILITIES = ("private", "public")


def _member(conn, project_id, account_id):
    project = _project_by_id(conn, project_id, account_id)
    if project is None:
        raise APIError("OBJECT_NOT_FOUND", f"Project {project_id} not found.", 404)
    return project


def _managed(conn, project_id, account_id):
    project = _member(conn, project_id, account_id)
    if permission(conn, project, account_id) != "admin":
        raise APIError("PERMISSION_DENIED", "Only a project's admins can do this.", 403)
    return project


def _view(conn, project, **changed):
    project = {**dict(project), **changed}
    return {"id": project["id"], "name": project["repo_id"], "full_name": project_handle(conn, project),
            "created_at": project["created_at"], "visibility": project["visibility"]}


def _name_taken(conn, name, account_id, team_id):
    return (_team_project(conn, team_id, name) if team_id else _project(conn, name, account_id)) is not None


def rename_project(db_path, project_id, name, account_id=None):
    name = project_name(name)
    with connect(db_path) as conn:
        project = _managed(conn, project_id, account_id)
        if project["repo_id"] != name:
            if _name_taken(conn, name, project["account_id"], project["team_id"]):
                raise APIError("NAME_TAKEN", f"A project named {name} already exists there.", 409)
            # CLIs look projects up by ID first, so existing clones follow the new name.
            conn.execute("UPDATE projects SET name = ?, repo_id = ?, repo_name = ? WHERE id = ?",
                         (name, name, name, project_id))
        return {"project": _view(conn, project, repo_id=name)}


def set_visibility(db_path, project_id, visibility, confirm, account_id):
    if visibility not in VISIBILITIES:
        raise APIError("INVALID_INPUT", "Visibility must be private or public.")
    with connect(db_path) as conn:
        project = _managed(conn, project_id, account_id)
        # Going public cannot be taken back once someone has read it, so it is never a stray click.
        if visibility == "public" and project["visibility"] != "public" and confirm != project["repo_id"]:
            raise APIError("CONFIRMATION_MISMATCH", "Type the project name exactly to make it public.", 400)
        conn.execute("UPDATE projects SET visibility = ? WHERE id = ?", (visibility, project_id))
        return {"project": _view(conn, project, visibility=visibility)}


def transfer_project(db_path, project_id, team_id, confirm, account_id):
    """Move a project to a team the caller administers, or to the caller. Its ID stays, so clones follow."""
    with connect(db_path) as conn:
        project = _managed(conn, project_id, account_id)
        if confirm != project["repo_id"]:
            raise APIError("CONFIRMATION_MISMATCH", "Type the project name exactly to transfer it.", 400)
        if team_id and (not isinstance(team_id, str) or team_role(conn, team_id, account_id) != "admin"):
            raise APIError("TEAM_NOT_FOUND", "Choose a team you administer.", 404)
        owner = None if team_id else account_id
        if (owner, team_id or None) != (project["account_id"], project["team_id"]):
            if _name_taken(conn, project["repo_id"], owner, team_id):
                raise APIError("NAME_TAKEN", f"A project named {project['repo_id']} already exists there.", 409)
            conn.execute("UPDATE projects SET account_id = ?, team_id = ?, owner = ? WHERE id = ?",
                         (owner, team_id or None, team_id or owner, project_id))
        return {"project": _view(conn, project, account_id=owner, team_id=team_id or None)}


def remove_project(conn, project_id):
    # Same tables as account deletion, for one project. Local .intent directories are untouched.
    for table in ("public_profile_projects", "semantic_heads", "semantic_versions", "sync_batches", "workspaces"):
        conn.execute(f"DELETE FROM {table} WHERE project_id = ?", (project_id,))
    conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))


def delete_project(db_path, project_id, confirm, account_id=None):
    with connect(db_path) as conn:
        project = _managed(conn, project_id, account_id)
        if confirm != project["repo_id"]:
            raise APIError("CONFIRMATION_MISMATCH", "Type the project name exactly to delete it.", 400)
        remove_project(conn, project_id)
    return {"deleted": True, "id": project_id}


def export_project(db_path, project_id, account_id=None):
    with connect(db_path) as conn:
        project = _member(conn, project_id, account_id)
        head = _head(conn, project_id)
        parents = {row["revision"]: row for row in conn.execute(
            "SELECT revision, parent, created_at FROM semantic_versions WHERE project_id = ?", (project_id,)).fetchall()}
        view = _view(conn, project)
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
        "project": view,
        "head": {"revision": head["revision"], "parent": head["parent"], "accepted_at": head["accepted_at"]},
        "snapshot": head["snapshot"] or {"intents": [], "snaps": [], "decisions": []},
        "revisions": revisions,
    }
