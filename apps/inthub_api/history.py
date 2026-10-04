"""One account-private shared history per named project; atomic fast-forward push."""

import hashlib
import json

from apps.inthub_api.common import APIError, new_id, now_utc
from apps.inthub_api.db import connect
from intent_cli.hub.snapshots import SnapshotError, require_fast_forward, snapshot_sha256, validate_snapshot
from intent_cli.hub.versions import revision_id, validate_project_name


def project_name(value):
    try:
        return validate_project_name(value)
    except ValueError as exc:
        raise APIError("INVALID_INPUT", str(exc)) from exc


def _project(conn, name, account_id):
    clause = "account_id = ?" if account_id else "account_id IS NULL"
    params = (name, account_id) if account_id else (name,)
    return conn.execute(f"SELECT * FROM projects WHERE provider = 'intent' AND repo_id = ? AND {clause}", params).fetchone()


def link_history(db_path, name, account_id=None):
    name = project_name(name)
    with connect(db_path) as conn:
        # Anonymous local mode also needs a deterministic identity (NULL unique
        # constraints do not enforce uniqueness on either supported database).
        pid = new_id("proj") if account_id else "proj_local_" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:24]
        conn.execute("""INSERT INTO projects
            (id, account_id, name, provider, repo_id, owner, repo_name, created_at)
            VALUES (?, ?, ?, 'intent', ?, ?, ?, ?) ON CONFLICT DO NOTHING""",
            (pid, account_id, name, name, account_id or "local", name, now_utc()))
        project = _project(conn, name, account_id)
        conn.execute("INSERT INTO semantic_heads (project_id, revision) VALUES (?, NULL) ON CONFLICT DO NOTHING", (project["id"],))
        return {"format_version": 2, "project_id": project["id"], "project_name": name}


def _head(conn, pid):
    row = conn.execute("""SELECT v.* FROM semantic_heads h JOIN semantic_versions v
        ON v.project_id = h.project_id AND v.revision = h.revision WHERE h.project_id = ?""", (pid,)).fetchone()
    if row is None:
        return {"revision": None, "parent": None, "snapshot": None, "snapshot_sha256": None, "accepted_at": None}
    snapshot = json.loads(row["snapshot_json"])
    return {"revision": row["revision"], "parent": row["parent"], "snapshot": snapshot,
            "snapshot_sha256": snapshot_sha256(snapshot), "accepted_at": row["created_at"]}


def read_history(db_path, name, account_id=None):
    name = project_name(name)
    with connect(db_path) as conn:
        project = _project(conn, name, account_id)
        head = _head(conn, project["id"]) if project else {
            "revision": None, "parent": None, "snapshot": None,
            "snapshot_sha256": None, "accepted_at": None}
        return {"format_version": 2, "project_id": project["id"] if project else None,
                "project_name": name, **head}


def push_history(db_path, payload, account_id=None):
    name = project_name(payload.get("project_name"))
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
        project = _project(conn, name, account_id)
        if project is None:
            raise APIError("NOT_LINKED", "Configure the remote project before pushing.", 404)
        pid = project["id"]
        if payload.get("project_id") != pid:
            raise APIError("REMOTE_CHANGED", "Remote project identity changed; check status before relinking.", 409)
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
        accepted = now_utc()
        conn.execute("""INSERT INTO semantic_versions
            (project_id, revision, parent, snapshot_json, created_at) VALUES (?, ?, ?, ?, ?)""",
            (pid, expected_revision, head["revision"], json.dumps(snapshot, ensure_ascii=False), accepted))
        conn.execute("UPDATE semantic_heads SET revision = ? WHERE project_id = ?", (expected_revision, pid))
        return {"format_version": 2, "project_id": pid, "project_name": name,
                "revision": expected_revision, "parent": head["revision"],
                "snapshot_sha256": digest, "accepted_at": accepted, "changed": True}
