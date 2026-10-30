"""What one owner, an account or a team, may keep on a hosted hub.

Each push stores a whole snapshot, so storage is what an owner could run away
with. A local hub has no owners and no limits.
"""

from apps.inthub_api.common import APIError
from apps.inthub_api.db import connect

PROJECTS_PER_OWNER = 100
STORAGE_PER_OWNER = 1024 ** 3


def owner_usage(conn, account_id, team_id=None):
    clause, owner = ("team_id = ?", team_id) if team_id else ("account_id = ? AND team_id IS NULL", account_id)
    row = conn.execute(
        f"SELECT COUNT(*) AS projects, COALESCE(SUM(stored_bytes), 0) AS bytes FROM projects WHERE provider = 'intent' AND {clause}",
        (owner,),
    ).fetchone()
    return {"projects": int(row["projects"]), "projects_limit": PROJECTS_PER_OWNER,
            "storage_bytes": int(row["bytes"]), "storage_limit": STORAGE_PER_OWNER}


def require_project_slot(conn, account_id, team_id=None):
    if (account_id or team_id) and owner_usage(conn, account_id, team_id)["projects"] >= PROJECTS_PER_OWNER:
        raise APIError("QUOTA_EXCEEDED", f"An account or team can keep up to {PROJECTS_PER_OWNER} projects. Delete one first.", 403)


def require_storage(conn, project, adding):
    if not (project["account_id"] or project["team_id"]):
        return
    used = owner_usage(conn, project["account_id"], project["team_id"])["storage_bytes"]
    if used + adding > STORAGE_PER_OWNER:
        raise APIError("QUOTA_EXCEEDED", "This account or team has used its 1 GB of history storage. Delete a project to free space.", 403)


def account_usage(db_target, account_id):
    """The viewer's own allowance, then each team they belong to."""
    with connect(db_target) as conn:
        teams = conn.execute(
            """SELECT t.id, t.name FROM teams t JOIN team_members m ON m.team_id = t.id
            WHERE m.account_id = ? ORDER BY t.name""", (account_id,)).fetchall()
        return {"owners": [
            {"type": "account", "name": None, **owner_usage(conn, account_id)},
            *({"type": "team", "name": team["name"], **owner_usage(conn, None, team["id"])} for team in teams),
        ]}
