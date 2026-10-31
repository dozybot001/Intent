"""One shared history per named project, owned by an account or a team; atomic fast-forward push."""

import hashlib
import json

from apps.inthub_api.access import MEMBER_LEVELS, permission, project_handle, team_role
from apps.inthub_api.common import APIError, new_id, now_utc
from apps.inthub_api.db import connect
from apps.inthub_api.limits import require_project_slot, require_storage
from intent_cli.hub.changes import COLLECTIONS, semantic_changes, summarize
from intent_cli.hub.snapshots import SnapshotError, require_fast_forward, snapshot_sha256, validate_snapshot
from intent_cli.hub.versions import revision_id, validate_project_name, validate_project_ref
from intent_cli.identity import FIELD_MAX_CHARS, REPOSITORY


def project_name(value):
    try:
        return validate_project_name(value)
    except ValueError as exc:
        raise APIError("INVALID_INPUT", str(exc)) from exc


def project_ref(value):
    try:
        return validate_project_ref(value)
    except ValueError as exc:
        raise APIError("INVALID_INPUT", str(exc)) from exc


def _project(conn, name, account_id):
    clause = "account_id = ?" if account_id else "account_id IS NULL"
    params = (name, account_id) if account_id else (name,)
    return conn.execute(f"SELECT * FROM projects WHERE provider = 'intent' AND repo_id = ? AND team_id IS NULL AND {clause}", params).fetchone()


def _team_project(conn, team_id, name):
    return conn.execute("SELECT * FROM projects WHERE provider = 'intent' AND repo_id = ? AND team_id = ?",
                        (name, team_id)).fetchone()


def _project_by_id(conn, project_id, account_id):
    """A project the viewer belongs to. Reading a public one does not count: pulls carry author emails."""
    project = conn.execute("SELECT * FROM projects WHERE provider = 'intent' AND id = ?", (project_id,)).fetchone()
    if project is None or (account_id is None and project["account_id"]):
        return None
    return project if permission(conn, project, account_id) in MEMBER_LEVELS else None


def _team(conn, slug):
    return conn.execute("SELECT id FROM teams WHERE slug = ?", (slug,)).fetchone()


def _named(conn, ref, account_id):
    """The project a CLI names, when the viewer belongs to it."""
    slug, _, name = ref.rpartition("/")
    if not slug:
        return _project(conn, name, account_id)
    team = _team(conn, slug) if account_id else None
    if team is None or team_role(conn, team["id"], account_id) is None:
        return None
    return _team_project(conn, team["id"], name)


def _local_project_id(conn, name):
    # Anonymous local mode also needs a deterministic identity (NULL unique
    # constraints do not enforce uniqueness on either supported database).
    # A renamed project keeps the ID derived from its old name, so step past it.
    for attempt in range(100):
        seed = name if attempt == 0 else f"{name}\n{attempt}"
        pid = "proj_local_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24]
        row = conn.execute("SELECT repo_id FROM projects WHERE id = ?", (pid,)).fetchone()
        if row is None or row["repo_id"] == name:
            return pid
    raise APIError("CONFLICT", "Could not allocate a local project identity.", 409)


def _link_team_project(conn, slug, name, account_id):
    team = _team(conn, slug) if account_id else None
    role = team_role(conn, team["id"], account_id) if team else None
    if role is None:
        raise APIError("TEAM_NOT_FOUND", f"Team {slug} not found, or you are not a member.", 404)
    if _team_project(conn, team["id"], name) is None:
        if role == "viewer":
            raise APIError("PERMISSION_DENIED", "Read-only members cannot add projects.", 403)
        require_project_slot(conn, None, team["id"])
        conn.execute("""INSERT INTO projects
            (id, team_id, name, provider, repo_id, owner, repo_name, created_at)
            VALUES (?, ?, ?, 'intent', ?, ?, ?, ?) ON CONFLICT DO NOTHING""",
            (new_id("proj"), team["id"], name, name, team["id"], name, now_utc()))
    return _team_project(conn, team["id"], name)


def link_history(db_path, ref, account_id=None):
    ref = project_ref(ref)
    slug, _, name = ref.rpartition("/")
    with connect(db_path) as conn:
        if slug:
            project = _link_team_project(conn, slug, name, account_id)
        else:
            pid = new_id("proj") if account_id else _local_project_id(conn, name)
            if _project(conn, name, account_id) is None:
                require_project_slot(conn, account_id)
            conn.execute("""INSERT INTO projects
                (id, account_id, name, provider, repo_id, owner, repo_name, created_at)
                VALUES (?, ?, ?, 'intent', ?, ?, ?, ?) ON CONFLICT DO NOTHING""",
                (pid, account_id, name, name, account_id or "local", name, now_utc()))
            project = _project(conn, name, account_id)
        conn.execute("INSERT INTO semantic_heads (project_id, revision) VALUES (?, NULL) ON CONFLICT DO NOTHING", (project["id"],))
        return {"format_version": 2, "project_id": project["id"], "project_name": ref}


def _head(conn, pid):
    row = conn.execute("""SELECT v.* FROM semantic_heads h JOIN semantic_versions v
        ON v.project_id = h.project_id AND v.revision = h.revision WHERE h.project_id = ?""", (pid,)).fetchone()
    if row is None:
        return {"revision": None, "parent": None, "snapshot": None, "snapshot_sha256": None, "accepted_at": None, "tip": None}
    snapshot = json.loads(row["snapshot_json"])
    return {"revision": row["revision"], "parent": row["parent"], "snapshot": snapshot,
            "snapshot_sha256": snapshot_sha256(snapshot), "accepted_at": row["created_at"], "tip": row["tip"]}


def read_history(db_path, ref, account_id=None, project_id=None):
    ref = project_ref(ref)
    with connect(db_path) as conn:
        # A clone that knows its project ID follows a rename or transfer made on IntHub.
        project = (_project_by_id(conn, project_id, account_id) if project_id else None) or _named(conn, ref, account_id)
        head = _head(conn, project["id"]) if project else {
            "revision": None, "parent": None, "snapshot": None,
            "snapshot_sha256": None, "accepted_at": None, "tip": None}
        return {"format_version": 2, "project_id": project["id"] if project else None,
                "project_name": project_handle(conn, project) if project else ref, **head}


def _declared_pusher(value):
    """The identity the CLI declares, like a Git committer; the token proves the account."""
    if not isinstance(value, dict):
        return None
    pusher = {key: value[key][:FIELD_MAX_CHARS] for key in ("name", "email")
              if isinstance(value.get(key), str) and value[key].strip()}
    return json.dumps(pusher, ensure_ascii=False) if pusher else None


def _record_verified(conn, project_id, revision, changes, account_id):
    """An object is verified when the account that pushed it has the author's verified email."""
    row = conn.execute("SELECT email FROM accounts WHERE id = ?", (account_id,)).fetchone() if account_id else None
    email = (row["email"] or "").casefold() if row else ""
    if not email:
        return
    verified = [obj["id"] for collection in COLLECTIONS for obj in changes[collection]["added"]
                if str((obj.get("author") or {}).get("email", "")).casefold() == email]
    for start in range(0, len(verified), 500):
        batch = verified[start:start + 500]
        conn.execute(f"""INSERT INTO verified_objects (project_id, object_id, revision)
            VALUES {", ".join(["(?, ?, ?)"] * len(batch))} ON CONFLICT DO NOTHING""",
            tuple(value for object_id in batch for value in (project_id, object_id, revision)))


def _writable(conn, payload, account_id):
    """The project a push names, when the pusher may write to it."""
    project = _project_by_id(conn, payload.get("project_id"), account_id) if payload.get("project_id") else None
    if project is None:
        ref = payload.get("project_name")
        if isinstance(ref, str) and _named(conn, project_ref(ref), account_id) is not None:
            raise APIError("REMOTE_CHANGED", "Remote project identity changed; check status before relinking.", 409)
        raise APIError("NOT_LINKED", "Configure the remote project before pushing.", 404)
    if permission(conn, project, account_id) == "read":
        raise APIError("PERMISSION_DENIED", "Read-only members cannot push to this project.", 403)
    return project


def _accept(conn, project, head, snapshot, revision, payload, account_id, tip=None):
    """Record what main now holds. tip names its revision in the graph when it came over protocol 3."""
    pid = project["id"]
    accepted = now_utc()
    changes = semantic_changes(head["snapshot"], snapshot)
    stored = json.dumps(snapshot, ensure_ascii=False)
    size = len(stored.encode("utf-8"))
    require_storage(conn, project, size)
    conn.execute("""INSERT INTO semantic_versions
        (project_id, revision, parent, snapshot_json, created_at, pushed_by, pusher_json, changes_json, tip)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (pid, revision, head["revision"], stored, accepted,
         account_id, _declared_pusher(payload.get("pusher")), json.dumps(summarize(changes)), tip))
    conn.execute("UPDATE projects SET stored_bytes = stored_bytes + ? WHERE id = ?", (size, pid))
    conn.execute("UPDATE semantic_heads SET revision = ? WHERE project_id = ?", (revision, pid))
    _record_verified(conn, pid, revision, changes, account_id)
    repository = payload.get("repository")
    if isinstance(repository, str) and REPOSITORY.fullmatch(repository):
        conn.execute("UPDATE projects SET repository_url = ? WHERE id = ?", (repository, pid))
    return accepted


def push_history(db_path, payload, account_id=None):
    ref = project_ref(payload.get("project_name"))
    snapshot = payload.get("snapshot")
    try:
        validate_snapshot(snapshot)
        expected_revision = revision_id(payload.get("parent"), snapshot)
    except (SnapshotError, ValueError) as exc:
        raise APIError("INVALID_SNAPSHOT", str(exc)) from exc
    if payload.get("revision") != expected_revision:
        raise APIError("INVALID_REVISION", "Revision does not match parent and snapshot.")
    with connect(db_path) as conn:
        if conn.backend == "sqlite":
            conn.execute("BEGIN IMMEDIATE")
        project = _writable(conn, payload, account_id)
        pid, name = project["id"], project_handle(conn, project)
        if conn.backend == "postgresql":
            conn.execute("SELECT project_id FROM semantic_heads WHERE project_id = ? FOR UPDATE", (pid,))
        head = _head(conn, pid)
        digest = snapshot_sha256(snapshot)
        if head["snapshot_sha256"] == digest:
            return {"format_version": 2, "project_id": pid, "project_name": name,
                    **{key: value for key, value in head.items() if key != "snapshot"}, "changed": False}
        if payload.get("parent") != head["revision"]:
            raise APIError("NON_FAST_FORWARD", "Remote history changed. Pull before pushing; divergent histories are preserved.", 409,
                           {"remote_revision": head["revision"], "local_parent": payload.get("parent")})
        if head["snapshot"] is not None:
            try:
                require_fast_forward(head["snapshot"], snapshot)
            except SnapshotError as exc:
                raise APIError("HISTORY_CONFLICT", str(exc), 409) from exc
        accepted = _accept(conn, project, head, snapshot, expected_revision, payload, account_id)
        return {"format_version": 2, "project_id": pid, "project_name": name,
                "revision": expected_revision, "parent": head["revision"],
                "snapshot_sha256": digest, "accepted_at": accepted, "changed": True}
