"""Who can do what with a project, in one place.

A viewer is an account ID, VISITOR when nobody is signed in on a hosted hub, or
None on a local hub, which has no accounts. Levels run admin, write, read for
people who belong to the project; "public" is anyone else reading a public one.
"""

VISITOR = "visitor"
TEAM_ROLES = ("admin", "member", "viewer")
_ROLE_LEVELS = {"admin": "admin", "member": "write", "viewer": "read"}
MEMBER_LEVELS = frozenset(_ROLE_LEVELS.values())


def team_role(conn, team_id, account_id):
    row = conn.execute("SELECT role FROM team_members WHERE team_id = ? AND account_id = ?",
                       (team_id, account_id)).fetchone()
    return row["role"] if row else None


def role_level(role):
    return _ROLE_LEVELS[role]


def permission(conn, project, viewer):
    """The viewer's level on this project, or None when they cannot see it."""
    if viewer is None:
        return "admin"
    if viewer != VISITOR:
        if project["team_id"]:
            role = team_role(conn, project["team_id"], viewer)
            if role:
                return role_level(role)
        elif project["account_id"] == viewer:
            return "admin"
    return "public" if project["visibility"] == "public" else None


def project_handle(conn, project):
    """The name a CLI uses: NAME for a personal project, TEAM/NAME for a team's."""
    if not project["team_id"]:
        return project["repo_id"]
    team = conn.execute("SELECT slug FROM teams WHERE id = ?", (project["team_id"],)).fetchone()
    return f"{team['slug']}/{project['repo_id']}"
