"""The semantic repository: object versions, revisions and refs, kept the way Git keeps them.

intents/, snaps/ and decisions/ stay the plain JSON working copy. Every command that
writes ends in commit_worktree, Intent's `git commit -a`, so there is no staging step
and each revision records the whole state after one command.

A revision names a tree, as a Git commit does, so walking history reads only small
files and revisions share every part of the tree that did not change. Everything read
back is checked: content must match the digest that named it.
"""

import hashlib
import heapq
import json
import re
from datetime import datetime, timezone

from intent_cli import identity
from intent_cli.hub.changes import COLLECTIONS
from intent_cli.origin import detect_origin
from intent_cli.repo_refs import (  # noqa: F401
    DEFAULT_BRANCH, DIGEST, HEAD_FILE, REFS, branch_conflict, branch_revision, contained, current_branch,
    delete_branch, head_revision, list_branches, replace_file, set_branch, set_head, storage_root, valid_branch_name,
)
from intent_cli.store_errors import StoredObjectIntegrityError
from intent_cli.store_paths import _safe_object_dir, shared_root
from intent_cli.store_schema import OBJECT_ID_PATTERNS, SUBDIRS

OBJECTS = "objects"
TREES = "trees"
REVISIONS = "revisions"
TREE_DEPTH = 2
SUMMARY_MAX_CHARS = 160
ABBREVIATION = re.compile(r"[0-9a-f]{4,64}\Z")
REVISION_NAME = re.compile(r"(.+?)((?:~[0-9]*|\^)*)\Z")


class UnknownRevisionError(ValueError):
    """A revision name that matches nothing, or more than one revision."""


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _content_path(base, directory, digest):
    if not isinstance(digest, str) or DIGEST.fullmatch(digest) is None:
        raise StoredObjectIntegrityError(storage_root(base) / directory, f"{digest!r} is not a digest")
    return contained(storage_root(base), directory, digest[:2], f"{digest[2:]}.json")


def _read_content(base, directory, digest):
    """Bytes stored under a digest, checked against it."""
    path = _content_path(base, directory, digest)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise StoredObjectIntegrityError(path, "stored content is missing") from exc
    if _digest(raw) != digest:
        raise StoredObjectIntegrityError(path, "stored content does not match its digest")
    return raw


def _install(path, raw):
    """Add a file named by its own digest. Its content can never change, so an existing one stands."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        replace_file(path, raw)


def _store(base, directory, data):
    raw = _canonical(data)
    digest = _digest(raw)
    _install(_content_path(base, directory, digest), raw)
    return digest


def is_repository(base):
    return (shared_root(base) / HEAD_FILE).is_file()


def create_repository(base):
    """Lay out an empty repository: HEAD names a branch that has no revision yet, as in Git."""
    root = storage_root(base)
    for name in (OBJECTS, TREES, REVISIONS, f"{REFS}/heads"):
        (root / name).mkdir(parents=True, exist_ok=True)
    set_head(base, DEFAULT_BRANCH)


def _is_object_id(obj_id):
    pattern = OBJECT_ID_PATTERNS.get(obj_id.split("-", 1)[0]) if isinstance(obj_id, str) else None
    return pattern is not None and pattern.fullmatch(obj_id) is not None


def _json(raw, path):
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise StoredObjectIntegrityError(path, "stored content is not JSON") from exc


def read_revision(base, revision):
    data = _json(_read_content(base, REVISIONS, revision), _content_path(base, REVISIONS, revision))
    parents = data.get("parents") if isinstance(data, dict) else None
    tree = data.get("tree") if isinstance(data, dict) else None
    if (not isinstance(parents, list) or not isinstance(tree, str) or DIGEST.fullmatch(tree) is None
            or not all(isinstance(item, str) and DIGEST.fullmatch(item) for item in parents)):
        raise StoredObjectIntegrityError(_content_path(base, REVISIONS, revision), "revision has an invalid shape")
    return data


def _write_tree(base, entries, depth=0):
    """Store {id: version digest} as TREE_DEPTH levels of buckets. One changed object rewrites only its path."""
    if depth == TREE_DEPTH:
        return _store(base, TREES, entries)
    buckets = {}
    for obj_id, version in entries.items():
        buckets.setdefault(_digest(obj_id.encode("utf-8"))[depth], {})[obj_id] = version
    return _store(base, TREES, {key: _write_tree(base, bucket, depth + 1) for key, bucket in buckets.items()})


def _tree_node(base, digest, depth):
    path = _content_path(base, TREES, digest)
    node = _json(_read_content(base, TREES, digest), path)
    if (not isinstance(node, dict) or not all(isinstance(item, str) and DIGEST.fullmatch(item) for item in node.values())
            or (depth == TREE_DEPTH and not all(_is_object_id(obj_id) for obj_id in node))):
        raise StoredObjectIntegrityError(path, "tree has an invalid shape")
    return node


def _read_tree(base, digest, depth=0):
    node = _tree_node(base, digest, depth)
    if depth == TREE_DEPTH:
        return node
    return {obj_id: version for child in node.values() for obj_id, version in _read_tree(base, child, depth + 1).items()}


def tree_at(base, revision):
    """{id: version digest} as they stood at a revision."""
    return _read_tree(base, read_revision(base, revision)["tree"]) if revision else {}


def read_version(base, digest):
    """One object version's bytes."""
    return _read_content(base, OBJECTS, digest)


def working_copy(base):
    """Every object file's bytes by ID. Bytes, not parsed JSON, so one damaged file cannot stop a write."""
    files = {}
    for object_type in SUBDIRS:
        subdir, _resolved = _safe_object_dir(base, object_type)
        for entry in sorted(subdir.iterdir()):
            if (entry.suffix == ".json" and not entry.is_symlink() and entry.is_file()
                    and OBJECT_ID_PATTERNS[object_type].fullmatch(entry.stem)):
                files[entry.stem] = entry.read_bytes()
    return files


def _parsed(files):
    """Objects from stored bytes. A file that is no object (itt migrate --force keeps them) counts as absent."""
    objects = {}
    for obj_id, raw in files.items():
        try:
            obj = json.loads(raw)
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("id") == obj_id:
            objects[obj_id] = obj
    return objects


def working_objects(base):
    return _parsed(working_copy(base))


def _tree_changes(before, after):
    changes = [{"id": obj_id, "action": "added"} for obj_id in sorted(after.keys() - before.keys())]
    changes += [{"id": obj_id, "action": "changed"} for obj_id in sorted(after.keys() & before.keys())
                if after[obj_id] != before[obj_id]]
    changes += [{"id": obj_id, "action": "removed"} for obj_id in sorted(before.keys() - after.keys())]
    return changes


def _summary(operation, changes, files):
    """One generated line, like a commit subject: what ran, and on what."""
    subject = next((change for change in changes if change["action"] == "added"), changes[0])
    try:
        what = json.loads(files[subject["id"]]).get("what", "")
    except (KeyError, ValueError, AttributeError):
        what = ""
    extra = f" and {len(changes) - 1} more" if len(changes) > 1 else ""
    text = f"{operation} {subject['id']}{extra}" + (f": {what}" if what else "")
    return text[:SUMMARY_MAX_CHARS]


def save_worktree(base):
    """Store the working copy's content without a revision, like a stash, and return its tree."""
    files = working_copy(base)
    for raw in files.values():
        _install(_content_path(base, OBJECTS, _digest(raw)), raw)
    return _write_tree(base, {obj_id: _digest(raw) for obj_id, raw in files.items()})


def read_saved(base, tree):
    """Bytes of every object in a saved tree."""
    return {obj_id: read_version(base, digest) for obj_id, digest in _read_tree(base, tree).items()}


def commit_worktree(base, operation, summary=None, merge_parent=None):
    """Record the working copy as a revision on the current branch. No change, no revision, unless it ends a merge."""
    files = working_copy(base)
    tree = {obj_id: _digest(raw) for obj_id, raw in files.items()}
    head = head_revision(base)
    before = tree_at(base, head)
    changes = _tree_changes(before, tree)
    if not changes and merge_parent is None:
        return None
    for obj_id, digest in tree.items():
        if before.get(obj_id) != digest:
            _install(_content_path(base, OBJECTS, digest), files[obj_id])
    digest = _store(base, REVISIONS, {
        "parents": [*([head] if head else []), *([merge_parent] if merge_parent else [])],
        "tree": _write_tree(base, tree), "author": identity.author(), "origin": detect_origin(),
        "time": datetime.now(timezone.utc).isoformat(), "summary": summary or _summary(operation, changes, files),
        "changes": changes,
    })
    set_branch(base, current_branch(base), digest)
    return digest


def uncommitted(base):
    """Changes in the working copy since HEAD: something wrote without recording, or was interrupted."""
    return _tree_changes(tree_at(base, head_revision(base)), {obj_id: _digest(raw) for obj_id, raw in working_copy(base).items()})


def _all_revisions(base):
    root = contained(storage_root(base), REVISIONS)
    return sorted(f"{folder.name}{entry.stem}" for folder in root.iterdir() if folder.is_dir() and not folder.is_symlink()
                  for entry in folder.glob("*.json"))


def _named_revision(base, name):
    if name == "HEAD":
        revision = head_revision(base)
        if revision is None:
            raise UnknownRevisionError("This repository has no revisions yet.")
        return revision
    if DIGEST.fullmatch(name):
        if _content_path(base, REVISIONS, name).is_file():
            return name
        raise UnknownRevisionError(f"Unknown revision {name!r}.")
    if valid_branch_name(name) and branch_revision(base, name):
        return branch_revision(base, name)
    if ABBREVIATION.fullmatch(name):
        matches = [digest for digest in _all_revisions(base) if digest.startswith(name)]
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise UnknownRevisionError(f"Revision {name} is ambiguous: it matches {len(matches)} revisions.")
    raise UnknownRevisionError(f"Unknown revision {name!r}.")


def resolve_revision(base, spec):
    """Turn HEAD, HEAD~2, HEAD^, a branch name, or a unique digest prefix into a full digest."""
    match = REVISION_NAME.fullmatch(spec or "")
    if match is None:
        raise UnknownRevisionError(f"Unknown revision {spec!r}.")
    revision = _named_revision(base, match.group(1))
    for step in re.findall(r"~[0-9]*|\^", match.group(2)):
        for _ in range(int(step[1:] or 1) if step[0] == "~" else 1):
            parents = read_revision(base, revision)["parents"]
            if not parents:
                raise UnknownRevisionError(f"Revision {spec!r} goes back past the first revision.")
            revision = parents[0]
    return revision


def _timestamp(revision):
    try:
        return datetime.fromisoformat(revision["time"]).timestamp()
    except (KeyError, TypeError, ValueError):
        return 0.0


def _reachable(base, start):
    revisions, pending = {}, [start] if start else []
    while pending:
        digest = pending.pop()
        if digest not in revisions:
            revisions[digest] = read_revision(base, digest)
            pending.extend(revisions[digest]["parents"])
    return revisions


def walk(base, start=None):
    """Revisions reachable from start as (digest, revision): children first, then newest first."""
    revisions = _reachable(base, start or head_revision(base))
    waiting = dict.fromkeys(revisions, 0)
    for revision in revisions.values():
        for parent in set(revision["parents"]):
            waiting[parent] += 1
    entry = lambda digest: (-_timestamp(revisions[digest]), digest)
    ready = [entry(digest) for digest, count in waiting.items() if count == 0]
    heapq.heapify(ready)
    ordered = []
    while ready:
        _when, digest = heapq.heappop(ready)
        ordered.append((digest, revisions[digest]))
        for parent in set(revisions[digest]["parents"]):
            waiting[parent] -= 1
            if waiting[parent] == 0:
                heapq.heappush(ready, entry(parent))
    return ordered


def is_ancestor(base, older, newer):
    return older in _reachable(base, newer)


def merge_base(base, one, other):
    """The newest best common ancestor: shared by both, and no parent of another shared revision."""
    mine, theirs = _reachable(base, one), _reachable(base, other)
    shared = mine.keys() & theirs.keys()
    behind = {parent for digest in shared for parent in mine[digest]["parents"]}
    return max(shared - behind, key=lambda digest: (_timestamp(mine[digest]), digest), default=None)


def objects_at(base, revision):
    """{id: object} as they stood at a revision."""
    return _parsed({obj_id: read_version(base, digest) for obj_id, digest in tree_at(base, revision).items()})


def snapshot_at(base, revision):
    """The objects as they stood at a revision, in the shape semantic_changes compares."""
    snapshot = {collection: [] for collection in COLLECTIONS}
    for obj_id, obj in sorted(objects_at(base, revision).items()):
        snapshot[SUBDIRS[obj_id.split("-", 1)[0]]].append(obj)
    return snapshot


def verify(base):
    """Check every revision, tree and object version reachable from any branch against its digest."""
    issues = []
    checked = set()

    def problem(kind, digest, exc):
        state = "MISSING" if not exc.path.exists() else "CORRUPT"
        issues.append({"code": f"{kind}_{state}", "id": digest, "message": str(exc)})

    def check_tree(digest, depth=0):
        if digest in checked:
            return
        checked.add(digest)
        try:
            node = _tree_node(base, digest, depth)
        except StoredObjectIntegrityError as exc:
            problem("TREE", digest, exc)
            return
        for child in node.values():
            if depth < TREE_DEPTH:
                check_tree(child, depth + 1)
            elif child not in checked:
                checked.add(child)
                try:
                    read_version(base, child)
                except StoredObjectIntegrityError as exc:
                    problem("OBJECT_VERSION", child, exc)

    pending = []
    for name in list_branches(base):
        try:
            pending.append(branch_revision(base, name))
        except StoredObjectIntegrityError as exc:
            problem("BRANCH", name, exc)
    while pending:
        digest = pending.pop()
        if digest in checked:
            continue
        checked.add(digest)
        try:
            revision = read_revision(base, digest)
        except StoredObjectIntegrityError as exc:
            problem("REVISION", digest, exc)
            continue
        pending.extend(revision["parents"])
        check_tree(revision["tree"])
    return issues
