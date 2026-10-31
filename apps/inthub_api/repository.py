"""A project's revision graph, stored the way a Git remote stores it: content-addressed blobs and branch refs.

The web views and protocol 2 read main as snapshots, so main stays mirrored into
semantic_versions. A row with no tip came in over protocol 2 and becomes a revision
the next time the graph is used, which also converts a project on its first use.
"""

import base64
import binascii
import hashlib
import json

from apps.inthub_api.access import project_handle
from apps.inthub_api.common import APIError, now_utc
from apps.inthub_api.db import connect
from apps.inthub_api.history import _accept, _head, _named, _project_by_id, _writable, project_ref
from apps.inthub_api.limits import require_storage
from intent_cli import repo
from intent_cli.hub.pack import plan, reachable
from intent_cli.hub.snapshots import SnapshotError, require_fast_forward, snapshot_sha256, validate_snapshot
from intent_cli.hub.versions import revision_id
from intent_cli.store_schema import SUBDIRS

KINDS = {"revision", "tree", "object"}
PAGE_BYTES = 6 * 1024 * 1024
REFS_PER_PROJECT = 200
_QUERY_BATCH = 500


def _store(conn, pid, kind, digest, body, binary=False):
    conn.execute("""INSERT INTO repo_blobs (project_id, kind, digest, body, is_binary) VALUES (?, ?, ?, ?, ?)
        ON CONFLICT DO NOTHING""", (pid, kind, digest, body, int(binary)))


def _put(conn, pid, kind, body, seen=None):
    """Store text under its digest. seen spares a long conversion from repeating what it has written."""
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if seen is None or (kind, digest) not in seen:
        _store(conn, pid, kind, digest, body)
    if seen is not None:
        seen.add((kind, digest))
    return digest


def _put_json(conn, pid, kind, data, seen=None):
    return _put(conn, pid, kind, repo._canonical(data).decode("utf-8"), seen)


def _rows(conn, pid, kind, digests):
    digests, found = list(digests), {}
    for start in range(0, len(digests), _QUERY_BATCH):
        batch = digests[start:start + _QUERY_BATCH]
        rows = conn.execute(f"""SELECT digest, body, is_binary FROM repo_blobs WHERE project_id = ? AND kind = ?
            AND digest IN ({", ".join("?" * len(batch))})""", (pid, kind, *batch)).fetchall()
        found.update((row["digest"], row) for row in rows)
    return found


def _bodies(conn, pid, kind, digests):
    return {digest: row["body"] for digest, row in _rows(conn, pid, kind, digests).items()}


def _revisions(conn, pid):
    rows = conn.execute("SELECT digest, body FROM repo_blobs WHERE project_id = ? AND kind = 'revision'", (pid,)).fetchall()
    return {row["digest"]: json.loads(row["body"]) for row in rows}


def _refs(conn, pid):
    return {row["name"]: row["revision"] for row in conn.execute(
        "SELECT name, revision FROM repo_refs WHERE project_id = ? ORDER BY name", (pid,)).fetchall()}


def _set_ref(conn, pid, name, revision):
    conn.execute("""INSERT INTO repo_refs (project_id, name, revision) VALUES (?, ?, ?)
        ON CONFLICT (project_id, name) DO UPDATE SET revision = excluded.revision""", (pid, name, revision))


def _entries(conn, pid, tree):
    """{id: version digest} of a tree, one query for each level."""
    level = [tree]
    for _depth in range(repo.TREE_DEPTH):
        level = [child for body in _bodies(conn, pid, "tree", level).values() for child in json.loads(body).values()]
    entries = {}
    for body in _bodies(conn, pid, "tree", level).values():
        entries.update(json.loads(body))
    return entries


def _snapshot(conn, pid, tree):
    """The objects of a tree, and whether every one of them could be read."""
    entries = _entries(conn, pid, tree)
    rows = _rows(conn, pid, "object", set(entries.values()))
    objects = repo._parsed({obj_id: rows[digest]["body"].encode("utf-8") for obj_id, digest in entries.items()
                            if digest in rows and not rows[digest]["is_binary"]})
    snapshot = {collection: [] for collection in SUBDIRS.values()}
    for obj_id, obj in sorted(objects.items()):
        snapshot[SUBDIRS[obj_id.split("-", 1)[0]]].append(obj)
    return snapshot, len(objects) == len(entries)


def _revision_from_push(conn, pid, row, parent, before, seen):
    """The revision a protocol 2 push amounts to, with objects laid out as the CLI lays out its files."""
    snapshot = json.loads(row["snapshot_json"])
    entries = {obj["id"]: _put(conn, pid, "object", json.dumps(obj, indent=2, ensure_ascii=False), seen)
               for collection in SUBDIRS.values() for obj in snapshot[collection]}
    digest = _put_json(conn, pid, "revision", {
        "parents": [parent] if parent else [],
        "tree": repo.tree_digest(entries, lambda data: _put_json(conn, pid, "tree", data, seen)),
        "author": json.loads(row["pusher_json"]) if row["pusher_json"] else None, "origin": "inthub",
        "time": row["created_at"], "summary": "Pushed to IntHub", "changes": repo._tree_changes(before, entries),
    }, seen)
    return digest, entries


def sync_graph(conn, pid):
    """Turn pushes that came over protocol 2 into revisions, oldest first."""
    if conn.backend == "postgresql":
        conn.execute("SELECT project_id FROM semantic_heads WHERE project_id = ? FOR UPDATE", (pid,))
    head = conn.execute("SELECT revision FROM semantic_heads WHERE project_id = ?", (pid,)).fetchone()
    pending, revision, tip = [], head["revision"] if head else None, None
    while revision:
        row = conn.execute("""SELECT revision, parent, snapshot_json, created_at, pusher_json, tip FROM semantic_versions
            WHERE project_id = ? AND revision = ?""", (pid, revision)).fetchone()
        if row["tip"]:
            tip = row["tip"]
            break
        pending.append(row)
        revision = row["parent"]
    if not pending:
        return
    entries = _entries(conn, pid, json.loads(_bodies(conn, pid, "revision", [tip])[tip])["tree"]) if tip else {}
    seen = set()
    for row in reversed(pending):
        tip, entries = _revision_from_push(conn, pid, row, tip, entries, seen)
        conn.execute("UPDATE semantic_versions SET tip = ? WHERE project_id = ? AND revision = ?", (tip, pid, row["revision"]))
    _set_ref(conn, pid, repo.DEFAULT_BRANCH, tip)


def main_history(conn, pid):
    """(digest, revision) reachable from main, children first and then newest first. Opens the transaction on SQLite."""
    if conn.backend == "sqlite":
        conn.execute("BEGIN IMMEDIATE")
    sync_graph(conn, pid)
    tip = _refs(conn, pid).get(repo.DEFAULT_BRANCH)
    revisions = _revisions(conn, pid)
    return repo.topological(reachable([tip] if tip else [], revisions.__getitem__)), revisions


def other_branches(conn, pid, revisions):
    """Branches beside main, with how far each has gone past it."""
    refs = _refs(conn, pid)
    tip = refs.get(repo.DEFAULT_BRANCH)
    behind = reachable([tip] if tip else [], revisions.__getitem__)
    return [{"name": name, "revision": revision, "ahead": len(reachable([revision], revisions.__getitem__, stop=behind))}
            for name, revision in refs.items() if name != repo.DEFAULT_BRANCH]


def snapshot_at(conn, pid, revisions, digest):
    return _snapshot(conn, pid, revisions[digest]["tree"])[0] if digest else None


def tip_of_push(conn, pid, revision):
    """The revision a protocol 2 revision ID became, for links and copies from before the graph."""
    row = conn.execute("SELECT tip FROM semantic_versions WHERE project_id = ? AND revision = ?", (pid, revision)).fetchone()
    return row["tip"] if row else None


def read_refs(db_path, ref, account_id=None, project_id=None, last_seen=None):
    ref = project_ref(ref)
    with connect(db_path) as conn:
        if conn.backend == "sqlite":
            conn.execute("BEGIN IMMEDIATE")
        project = (_project_by_id(conn, project_id, account_id) if project_id else None) or _named(conn, ref, account_id)
        if project is None:
            return {"format_version": 3, "project_id": None, "project_name": ref, "refs": {}}
        sync_graph(conn, project["id"])
        return {"format_version": 3, "project_id": project["id"], "project_name": project_handle(conn, project),
                "refs": _refs(conn, project["id"]), "last_seen": tip_of_push(conn, project["id"], last_seen) if last_seen else None}


def _digests(values, field):
    if not isinstance(values, list) or not all(isinstance(item, str) and repo.DIGEST.fullmatch(item) for item in values):
        raise APIError("INVALID_INPUT", f"{field} must list revision digests.")
    return values


def _checked_blob(blob):
    """(kind, digest, body, binary, size) of a blob, once its content proves its name."""
    if (not isinstance(blob, dict) or blob.get("kind") not in KINDS or not isinstance(blob.get("body"), str)
            or not isinstance(blob.get("digest"), str)):
        raise APIError("INVALID_INPUT", "Each blob needs a kind, digest and body.")
    binary = bool(blob.get("binary")) and blob["kind"] == "object"  # a damaged file recorded long ago
    try:
        raw = base64.b64decode(blob["body"], validate=True) if binary else blob["body"].encode("utf-8")
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise APIError("INVALID_INPUT", "A blob body cannot be read.") from exc
    if hashlib.sha256(raw).hexdigest() != blob["digest"]:
        raise APIError("INVALID_BLOB", f"Blob {blob['digest'][:12]} does not match its digest.")
    body = blob["body"]
    if binary:
        # One digest, one form: what can be text is stored as text, whatever the uploader called it.
        try:
            body, binary = (raw.decode("utf-8"), False) if b"\0" not in raw else (body, True)
        except UnicodeDecodeError:
            pass
    if not binary and "\0" in body:
        raise APIError("INVALID_INPUT", "A text body cannot hold a NUL.")
    if blob["kind"] == "revision":
        try:
            valid = repo.valid_revision(repo.strict_json(blob["body"]))
        except ValueError:
            valid = False
        if not valid:
            raise APIError("INVALID_BLOB", f"Revision {blob['digest'][:12]} has an invalid shape.")
    return blob["kind"], blob["digest"], body, binary, len(raw)


def upload_blobs(db_path, payload, account_id=None):
    """Store blobs. Nothing they name becomes reachable until a ref moves, so a broken upload costs only storage."""
    blobs = payload.get("blobs")
    if not isinstance(blobs, list):
        raise APIError("INVALID_INPUT", "blobs must be a list.")
    checked = {blob[:2]: blob for blob in map(_checked_blob, blobs)}
    with connect(db_path) as conn:
        project = _writable(conn, payload, account_id)
        pid = project["id"]
        fresh = []
        for kind in KINDS:
            of_kind = [blob for blob in checked.values() if blob[0] == kind]
            known = _rows(conn, pid, kind, [blob[1] for blob in of_kind])
            fresh += [blob for blob in of_kind if blob[1] not in known]
        adding = sum(blob[4] for blob in fresh)
        require_storage(conn, project, adding)
        for kind, digest, body, binary, _size in fresh:
            _store(conn, pid, kind, digest, body, binary)
        conn.execute("UPDATE projects SET stored_bytes = stored_bytes + ? WHERE id = ?", (adding, pid))
        return {"format_version": 3, "project_id": pid, "stored": len(fresh)}


def fetch_blobs(db_path, payload, account_id=None):
    """One page of what a clone lacks. The list is the same for the same refs, so the offset carries on from any request."""
    want, have, offset = _digests(payload.get("want"), "want"), _digests(payload.get("have"), "have"), payload.get("offset", 0)
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise APIError("INVALID_INPUT", "offset must not be negative.")
    with connect(db_path) as conn:
        project = _project_by_id(conn, payload.get("project_id"), account_id)
        if project is None:
            raise APIError("PROJECT_NOT_FOUND", "Project not found, or you are not a member.", 404)
        pid = project["id"]
        revisions = _revisions(conn, pid)
        # Only what a ref reaches is complete: an interrupted upload can leave a revision without its tree.
        connected = reachable(_refs(conn, pid).values(), revisions.__getitem__)
        if any(digest not in connected for digest in want):
            raise APIError("REVISION_NOT_FOUND", "IntHub does not have that revision.", 404)
        items = _plan(conn, pid, revisions, want, [digest for digest in have if digest in connected])
        blobs, size = [], 0
        for start in range(offset, len(items), _QUERY_BATCH):
            batch = items[start:start + _QUERY_BATCH]
            rows = {kind: _rows(conn, pid, kind, [digest for of_kind, digest in batch if of_kind == kind]) for kind in KINDS}
            for kind, digest in batch:
                row = rows[kind][digest]
                blob = {"kind": kind, "digest": digest, "body": row["body"], **({"binary": True} if row["is_binary"] else {})}
                cost = len(json.dumps(blob, ensure_ascii=False).encode("utf-8"))
                if blobs and size + cost > PAGE_BYTES:
                    return {"format_version": 3, "blobs": blobs, "total": len(items), "next_offset": offset + len(blobs)}
                blobs.append(blob)
                size += cost
        return {"format_version": 3, "blobs": blobs, "total": len(items), "next_offset": None}


def _plan(conn, pid, revisions, want, have):
    def read_revision(digest):
        if digest not in revisions:
            raise APIError("INCOMPLETE_HISTORY", f"Revision {digest[:12]} has not been uploaded.", 409)
        return revisions[digest]

    def read_node(digest, depth):
        body = _bodies(conn, pid, "tree", [digest]).get(digest)
        if body is None:
            raise APIError("INCOMPLETE_HISTORY", f"Tree {digest[:12]} has not been uploaded.", 409)
        try:
            node = json.loads(body)
        except ValueError:
            node = None
        if not repo.valid_tree_node(node, depth):
            raise APIError("INVALID_HISTORY", f"Tree {digest[:12]} has an invalid shape.", 409)
        return node

    return plan(want, have, read_revision, read_node)


def _mirror_main(conn, project, pid, snapshot, tip, payload, account_id):
    """Keep what the web views and protocol 2 read in step with main."""
    head = _head(conn, pid)
    if head["snapshot"] is not None:
        try:
            require_fast_forward(head["snapshot"], snapshot)
        except SnapshotError as exc:
            raise APIError("HISTORY_CONFLICT", f"{exc} Finish it the way main has it, then push again.", 409) from exc
    if head["snapshot_sha256"] == snapshot_sha256(snapshot):
        conn.execute("UPDATE semantic_versions SET tip = ? WHERE project_id = ? AND revision = ?", (tip, pid, head["revision"]))
        return
    _accept(conn, project, head, snapshot, revision_id(head["revision"], snapshot), payload, account_id, tip)


def update_ref(db_path, payload, account_id=None):
    """Move a branch, as a Git remote does: only from where the pusher saw it, and only forward."""
    name, old, new = payload.get("ref"), payload.get("old"), payload.get("new")
    if not repo.valid_branch_name(name):
        raise APIError("INVALID_INPUT", "Name a valid branch.")
    if new is not None and not repo.new_branch_name(name):
        raise APIError("INVALID_INPUT", f"Branch names can be up to {repo.BRANCH_MAX_BYTES} bytes.")
    _digests([digest for digest in (old, new) if digest is not None], "old and new")
    with connect(db_path) as conn:
        if conn.backend == "sqlite":
            conn.execute("BEGIN IMMEDIATE")
        project = _writable(conn, payload, account_id)
        pid = project["id"]
        sync_graph(conn, pid)
        refs = _refs(conn, pid)
        current = refs.get(name)
        if old != current:
            raise APIError("NON_FAST_FORWARD", "Remote history changed. Pull before pushing; divergent histories are preserved.",
                           409, {"remote_revision": current, "local_parent": old})
        reply = {"format_version": 3, "project_id": pid, "project_name": project_handle(conn, project),
                 "ref": name, "parent": current, "revision": new}
        if new is None:
            if name == repo.DEFAULT_BRANCH:
                raise APIError("INVALID_INPUT", f"{repo.DEFAULT_BRANCH} cannot be deleted.")
            conn.execute("DELETE FROM repo_refs WHERE project_id = ? AND name = ?", (pid, name))
            return {**reply, "changed": current is not None}
        if current == new:
            return {**reply, "changed": False}
        if current is None and len(refs) >= REFS_PER_PROJECT:
            raise APIError("QUOTA_EXCEEDED", f"A project can keep up to {REFS_PER_PROJECT} branches. Delete one first.", 403)
        conflict = repo.conflicting_ref(refs, name)
        if conflict:
            raise APIError("BRANCH_EXISTS", f"Branch {conflict} already exists, so {name} cannot.", 409)
        revisions = _revisions(conn, pid)
        items = _plan(conn, pid, revisions, [new], list(refs.values()))
        for kind in KINDS:
            wanted = [digest for of_kind, digest in items if of_kind == kind]
            missing = set(wanted) - _rows(conn, pid, kind, wanted).keys()
            if missing:
                raise APIError("INCOMPLETE_HISTORY", f"{min(missing)[:12]} has not been uploaded.", 409)
        if current and current not in reachable([new], revisions.__getitem__):
            raise APIError("NON_FAST_FORWARD", "That update would drop revisions on the remote. Pull first.", 409,
                           {"remote_revision": current, "local_parent": old})
        if repo.canonical_tree(_entries(conn, pid, revisions[new]["tree"])) != revisions[new]["tree"]:
            raise APIError("INVALID_HISTORY", "That revision's tree is not the one its objects make.", 409)
        snapshot, complete = _snapshot(conn, pid, revisions[new]["tree"])
        try:
            if not complete:
                raise SnapshotError("Some objects in this revision cannot be read.")
            validate_snapshot(snapshot)
        except SnapshotError as exc:
            raise APIError("INVALID_SNAPSHOT", str(exc)) from exc
        if name == repo.DEFAULT_BRANCH:
            _mirror_main(conn, project, pid, snapshot, new, payload, account_id)
        _set_ref(conn, pid, name, new)
        return {**reply, "changed": True, "accepted_at": now_utc()}
