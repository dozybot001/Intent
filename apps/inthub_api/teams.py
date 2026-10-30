"""Teams: a group of accounts that own projects together.

Changes are browser actions, like renaming a project. Access tokens only ever
use the membership, to read and push the team's projects.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from apps.inthub_api.access import TEAM_ROLES, team_role
from apps.inthub_api.common import APIError, new_id, now_utc
from apps.inthub_api.db import connect
from apps.inthub_api.projects import remove_project
from apps.inthub_api.queries import project_rows
from intent_cli.hub.versions import TEAM_SLUG

NAME_MAX = 80
TEAMS_PER_ACCOUNT = 50
PENDING_INVITES_MAX = 50
INVITE_TTL = timedelta(days=7)


def _clean_name(value):
    name = value.strip() if isinstance(value, str) else ""
    if (not 1 <= len(name) <= NAME_MAX or any(ord(char) < 32 or ord(char) == 127 for char in name)
            or name.encode("utf-8", "replace").decode("utf-8") != name):
        raise APIError("INVALID_INPUT", f"A team name must be 1–{NAME_MAX} characters.")
    return name


def _clean_slug(value):
    if not isinstance(value, str) or not TEAM_SLUG.match(value):
        raise APIError("INVALID_INPUT", "A team URL must use lowercase letters, digits and hyphens, up to 39 characters.")
    return value


def _clean_role(value):
    if value not in TEAM_ROLES:
        raise APIError("INVALID_INPUT", "A role must be admin, member or viewer.")
    return value


def _view(team):
    return {"id": team["id"], "slug": team["slug"], "name": team["name"], "created_at": team["created_at"]}


def _membership(conn, team_ref, account_id):
    """The team by ID or slug, with the viewer's role; a team you are not in does not exist."""
    team = conn.execute("SELECT * FROM teams WHERE id = ? OR slug = ?", (team_ref, team_ref)).fetchone()
    role = team_role(conn, team["id"], account_id) if team else None
    if role is None:
        raise APIError("TEAM_NOT_FOUND", "Team not found.", 404)
    return team, role


def _administered(conn, team_ref, account_id):
    team, role = _membership(conn, team_ref, account_id)
    if role != "admin":
        raise APIError("PERMISSION_DENIED", "Only team admins can do this.", 403)
    return team


def _serialized(conn, team_id):
    # Holds role changes in line, so two admins cannot each demote the other.
    if conn.backend == "sqlite":
        conn.execute("BEGIN IMMEDIATE")
    else:
        conn.execute("SELECT id FROM teams WHERE id = ? FOR UPDATE", (team_id,))


def _is_last_admin(conn, team_id, account_id):
    admins = conn.execute("SELECT account_id FROM team_members WHERE team_id = ? AND role = 'admin'", (team_id,)).fetchall()
    return [row["account_id"] for row in admins] == [account_id]


def _keep_an_admin(conn, team_id, account_id):
    if _is_last_admin(conn, team_id, account_id):
        raise APIError("LAST_ADMIN", "Make another member an admin first.", 409)


def _claim_slug(conn, slug, name, account_id, timestamp):
    team_id = new_id("team")
    inserted = conn.execute("""INSERT INTO teams (id, slug, name, created_by, created_at)
        VALUES (?, ?, ?, ?, ?) ON CONFLICT DO NOTHING""", (team_id, slug, name, account_id, timestamp))
    if inserted.rowcount != 1:
        raise APIError("NAME_TAKEN", f"The team URL {slug} is taken.", 409)
    return team_id


def create_team(db_path, name, slug, account_id):
    name, slug = _clean_name(name), _clean_slug(slug)
    timestamp = now_utc()
    with connect(db_path) as conn:
        created = conn.execute("SELECT count(*) AS n FROM teams WHERE created_by = ?", (account_id,)).fetchone()["n"]
        if created >= TEAMS_PER_ACCOUNT:
            raise APIError("TEAM_LIMIT", f"An account can create up to {TEAMS_PER_ACCOUNT} teams.", 409)
        team_id = _claim_slug(conn, slug, name, account_id, timestamp)
        conn.execute("INSERT INTO team_members (team_id, account_id, role, joined_at) VALUES (?, ?, 'admin', ?)",
                     (team_id, account_id, timestamp))
    return {"team": {"id": team_id, "slug": slug, "name": name, "created_at": timestamp}, "role": "admin"}


def list_teams(db_path, account_id):
    with connect(db_path) as conn:
        rows = conn.execute("""SELECT t.id, t.slug, t.name, t.created_at, m.role,
                (SELECT count(*) FROM team_members o WHERE o.team_id = t.id) AS members,
                (SELECT count(*) FROM projects p WHERE p.team_id = t.id) AS projects
            FROM team_members m JOIN teams t ON t.id = m.team_id
            WHERE m.account_id = ? ORDER BY t.name""", (account_id,)).fetchall()
    return {"teams": [{**_view(row), "role": row["role"], "members": row["members"], "projects": row["projects"]} for row in rows]}


def team_detail(db_path, team_ref, account_id):
    with connect(db_path) as conn:
        team, role = _membership(conn, team_ref, account_id)
        members = conn.execute("""SELECT a.id, a.login, a.display_name, a.email, m.role, m.joined_at
            FROM team_members m JOIN accounts a ON a.id = m.account_id
            WHERE m.team_id = ? ORDER BY m.joined_at, a.id""", (team["id"],)).fetchall()
        invites = conn.execute("""SELECT i.id, i.role, i.created_at, i.expires_at, a.display_name AS invited_by
            FROM team_invites i LEFT JOIN accounts a ON a.id = i.created_by
            WHERE i.team_id = ? AND i.expires_at > ? ORDER BY i.created_at DESC""", (team["id"], now_utc())).fetchall() if role == "admin" else []
        projects = project_rows(conn, account_id, team_id=team["id"])
    admin = role == "admin"
    return {
        "team": _view(team), "role": role,
        # Only admins see addresses, to tell apart people with the same name before granting a role.
        "members": [{"id": row["id"], "name": row["display_name"] or row["login"], "role": row["role"], "joined_at": row["joined_at"],
                     "you": row["id"] == account_id, **({"email": row["email"]} if admin else {})} for row in members],
        "invites": [dict(row) for row in invites],
        "projects": projects,
    }


def update_team(db_path, team_ref, name, slug, account_id):
    name, slug = _clean_name(name), _clean_slug(slug)
    with connect(db_path) as conn:
        team = _administered(conn, team_ref, account_id)
        taken = conn.execute("SELECT id FROM teams WHERE slug = ? AND id <> ?", (slug, team["id"])).fetchone()
        if taken:
            raise APIError("NAME_TAKEN", f"The team URL {slug} is taken.", 409)
        # Clones find projects by ID, so they follow a new team URL like a rename.
        conn.execute("UPDATE teams SET name = ?, slug = ? WHERE id = ?", (name, slug, team["id"]))
    return {"team": {**_view(team), "name": name, "slug": slug}}


def _drop_team(conn, team_id):
    for row in conn.execute("SELECT id FROM projects WHERE team_id = ?", (team_id,)).fetchall():
        remove_project(conn, row["id"])
    conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))


def delete_team(db_path, team_ref, confirm, account_id):
    with connect(db_path) as conn:
        team = _administered(conn, team_ref, account_id)
        if confirm != team["slug"]:
            raise APIError("CONFIRMATION_MISMATCH", "Type the team URL exactly to delete it.", 400)
        _drop_team(conn, team["id"])
    return {"deleted": True, "id": team["id"]}


def hand_over_teams(conn, account_id):
    """Before an account is deleted: each of its teams keeps an admin, and an empty one goes with it."""
    teams = conn.execute("SELECT team_id FROM team_members WHERE account_id = ? AND role = 'admin'", (account_id,)).fetchall()
    for row in teams:
        team_id = row["team_id"]
        if not _is_last_admin(conn, team_id, account_id):
            continue
        heir = conn.execute("""SELECT account_id FROM team_members WHERE team_id = ? AND account_id <> ?
            ORDER BY CASE role WHEN 'member' THEN 0 ELSE 1 END, joined_at, account_id LIMIT 1""", (team_id, account_id)).fetchone()
        if heir:
            conn.execute("UPDATE team_members SET role = 'admin' WHERE team_id = ? AND account_id = ?", (team_id, heir["account_id"]))
        else:
            _drop_team(conn, team_id)


def set_member_role(db_path, team_ref, member_id, role, account_id):
    role = _clean_role(role)
    with connect(db_path) as conn:
        team = _administered(conn, team_ref, account_id)
        _serialized(conn, team["id"])
        current = team_role(conn, team["id"], member_id)
        if current is None:
            raise APIError("OBJECT_NOT_FOUND", "That person is not in this team.", 404)
        if current == "admin" and role != "admin":
            _keep_an_admin(conn, team["id"], member_id)
        conn.execute("UPDATE team_members SET role = ? WHERE team_id = ? AND account_id = ?", (role, team["id"], member_id))
    return {"id": member_id, "role": role}


def remove_member(db_path, team_ref, member_id, account_id):
    """Anyone can leave; removing someone else takes an admin."""
    with connect(db_path) as conn:
        team, role = _membership(conn, team_ref, account_id)
        if member_id != account_id and role != "admin":
            raise APIError("PERMISSION_DENIED", "Only team admins can do this.", 403)
        _serialized(conn, team["id"])
        if team_role(conn, team["id"], member_id) is None:
            raise APIError("OBJECT_NOT_FOUND", "That person is not in this team.", 404)
        _keep_an_admin(conn, team["id"], member_id)
        conn.execute("DELETE FROM team_members WHERE team_id = ? AND account_id = ?", (team["id"], member_id))
    return {"removed": True, "id": member_id}


def _hash(token):
    return hashlib.sha256(token.encode("utf-8", "replace")).hexdigest()


def create_invite(db_path, team_ref, role, account_id):
    role = _clean_role(role)
    token = "ith_inv_" + secrets.token_urlsafe(32)
    invite_id, created = new_id("inv"), now_utc()
    expires = (datetime.now(timezone.utc) + INVITE_TTL).isoformat()
    with connect(db_path) as conn:
        team = _administered(conn, team_ref, account_id)
        conn.execute("DELETE FROM team_invites WHERE team_id = ? AND expires_at <= ?", (team["id"], created))
        pending = conn.execute("SELECT count(*) AS n FROM team_invites WHERE team_id = ?", (team["id"],)).fetchone()["n"]
        if pending >= PENDING_INVITES_MAX:
            raise APIError("INVITE_LIMIT", "Revoke a pending invite first.", 409)
        conn.execute("""INSERT INTO team_invites (id, team_id, token_hash, role, created_by, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", (invite_id, team["id"], _hash(token), role, account_id, created, expires))
    # The link exists only in this response; the hub keeps its hash.
    return {"invite": {"id": invite_id, "role": role, "created_at": created, "expires_at": expires},
            "path": f"/invite?token={token}"}


def revoke_invite(db_path, team_ref, invite_id, account_id):
    with connect(db_path) as conn:
        team = _administered(conn, team_ref, account_id)
        conn.execute("DELETE FROM team_invites WHERE id = ? AND team_id = ?", (invite_id, team["id"]))
    return {"revoked": True, "id": invite_id}


def _pending_invite(conn, token):
    invite = conn.execute("""SELECT i.id, i.role, i.expires_at, t.id AS team_id, t.slug, t.name, t.created_at, a.display_name AS invited_by
        FROM team_invites i JOIN teams t ON t.id = i.team_id LEFT JOIN accounts a ON a.id = i.created_by
        WHERE i.token_hash = ? AND i.expires_at > ?""", (_hash(token) if isinstance(token, str) else "", now_utc())).fetchone()
    if invite is None:
        raise APIError("INVITE_INVALID", "This invite link is no longer valid.", 410)
    return invite


def _invited_team(invite):
    return {"id": invite["team_id"], "slug": invite["slug"], "name": invite["name"], "created_at": invite["created_at"]}


def preview_invite(db_path, token, account_id):
    with connect(db_path) as conn:
        invite = _pending_invite(conn, token)
        member = team_role(conn, invite["team_id"], account_id) is not None
    return {"team": _invited_team(invite), "role": invite["role"], "invited_by": invite["invited_by"],
            "expires_at": invite["expires_at"], "already_member": member}


def accept_invite(db_path, token, account_id):
    """One use: the invite is claimed by deleting it. Members leave it for whoever it was meant for."""
    with connect(db_path) as conn:
        invite = _pending_invite(conn, token)
        team = _invited_team(invite)
        if team_role(conn, invite["team_id"], account_id):
            return {"team": team, "joined": False}
        if conn.execute("DELETE FROM team_invites WHERE id = ?", (invite["id"],)).rowcount != 1:
            raise APIError("INVITE_INVALID", "This invite link is no longer valid.", 410)
        conn.execute("INSERT INTO team_members (team_id, account_id, role, joined_at) VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING",
                     (invite["team_id"], account_id, invite["role"], now_utc()))
    return {"team": team, "role": invite["role"], "joined": True}
