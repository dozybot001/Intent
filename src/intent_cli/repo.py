"""The semantic repository: object versions, revisions and refs, kept the way Git keeps them.

intents/, snaps/ and decisions/ stay the plain JSON working copy. Every command that
writes ends in commit_worktree, Intent's `git commit -a`, so there is no staging step
and each revision records the whole state after one command.
"""

import hashlib
import json
import os
import re
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from intent_cli import identity
from intent_cli.hub.changes import COLLECTIONS
from intent_cli.origin import detect_origin
from intent_cli.store_errors import StoredObjectIntegrityError, UnsafeStoragePathError
from intent_cli.store_paths import _safe_object_dir, _safe_storage_root
from intent_cli.store_schema import OBJECT_ID_PATTERNS, SUBDIRS

DEFAULT_BRANCH = "main"
HEAD_FILE = "HEAD"
OBJECTS = "objects"
REVISIONS = "revisions"
REFS = "refs"
BACKUPS = "backups"
SUMMARY_MAX_CHARS = 160
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
ABBREVIATION = re.compile(r"[0-9a-f]{4,64}\Z")
HEAD_RELATIVE = re.compile(r"(HEAD|[\w.-]+)((?:~[0-9]*|\^)*)\Z")


class UnknownRevisionError(ValueError):
    """A revision name that matches nothing, or more than one revision."""


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _content_path(base, directory, digest):
    return Path(base) / directory / digest[:2] / f"{digest[2:]}.json"


def _safe_directory(base, name):
    base, _resolved = _safe_storage_root(base)
    path = base / name
    if path.is_symlink():
        raise UnsafeStoragePathError(path, f"{name} must not be a symlink")
    return path


def _replace(path, raw):
    descriptor, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _install(path, raw):
    """Add a file named by its own digest. Its content can never change, so an existing one stands."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        _replace(path, raw)


def is_repository(base):
    return (Path(base) / HEAD_FILE).is_file()


def create_repository(base):
    """Lay out an empty repository: HEAD names a branch that has no revision yet, as in Git."""
    for name in (OBJECTS, REVISIONS, f"{REFS}/heads"):
        (Path(base) / name).mkdir(parents=True, exist_ok=True)
    _safe_directory(base, HEAD_FILE)
    _replace(Path(base) / HEAD_FILE, f"ref: {REFS}/heads/{DEFAULT_BRANCH}\n".encode("ascii"))


def current_branch(base):
    """The branch HEAD names."""
    text = _safe_directory(base, HEAD_FILE).read_text(encoding="ascii").strip()
    return text.removeprefix(f"ref: {REFS}/heads/")


def _branch_path(base, branch):
    return _safe_directory(base, REFS) / "heads" / branch


def head_revision(base):
    """The revision HEAD points at, or None on a branch with no revision yet."""
    path = _branch_path(base, current_branch(base))
    return path.read_text(encoding="ascii").strip() if path.is_file() else None


def read_revision(base, revision):
    path = _content_path(base, REVISIONS, revision)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StoredObjectIntegrityError(path, "revision is missing or unreadable") from exc


def _working_copy(base):
    """Every object file's bytes by ID. Bytes, not parsed JSON, so one damaged file cannot stop a write."""
    files = {}
    for object_type in SUBDIRS:
        subdir, _resolved = _safe_object_dir(base, object_type)
        for entry in sorted(subdir.iterdir()):
            if (entry.suffix == ".json" and not entry.is_symlink() and entry.is_file()
                    and OBJECT_ID_PATTERNS[object_type].fullmatch(entry.stem)):
                files[entry.stem] = entry.read_bytes()
    return files


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


def _commit(base, branch, parents, tree, summary, changes):
    revision = {
        "parents": parents, "tree": tree, "author": identity.author(), "origin": detect_origin(),
        "time": datetime.now(timezone.utc).isoformat(), "summary": summary, "changes": changes,
    }
    raw = _canonical(revision)
    digest = _digest(raw)
    _safe_directory(base, REVISIONS)
    _install(_content_path(base, REVISIONS, digest), raw)
    ref = _branch_path(base, branch)
    ref.parent.mkdir(parents=True, exist_ok=True)
    _replace(ref, f"{digest}\n".encode("ascii"))
    return digest


def commit_worktree(base, operation, summary=None):
    """Record the working copy as a revision on the current branch. No change, no revision."""
    files = _working_copy(base)
    tree = {obj_id: _digest(raw) for obj_id, raw in files.items()}
    head = head_revision(base)
    before = read_revision(base, head)["tree"] if head else {}
    changes = _tree_changes(before, tree)
    if not changes:
        return None
    _safe_directory(base, OBJECTS)
    for obj_id, digest in tree.items():
        if before.get(obj_id) != digest:
            _install(_content_path(base, OBJECTS, digest), files[obj_id])
    return _commit(base, current_branch(base), [head] if head else [], tree,
                   summary or _summary(operation, changes, files), changes)


def uncommitted(base):
    """Changes in the working copy since HEAD: something wrote without recording, or was interrupted."""
    head = head_revision(base)
    before = read_revision(base, head)["tree"] if head else {}
    return _tree_changes(before, {obj_id: _digest(raw) for obj_id, raw in _working_copy(base).items()})


def _all_revisions(base):
    root = _safe_directory(base, REVISIONS)
    return sorted(f"{folder.name}{entry.stem}" for folder in root.iterdir() if folder.is_dir()
                  for entry in folder.glob("*.json"))


def _named_revision(base, name):
    if name == "HEAD":
        revision = head_revision(base)
        if revision is None:
            raise UnknownRevisionError("This repository has no revisions yet.")
        return revision
    path = _branch_path(base, name)
    if re.fullmatch(r"[\w.-]+", name) and path.is_file():
        return path.read_text(encoding="ascii").strip()
    if ABBREVIATION.fullmatch(name):
        matches = [digest for digest in _all_revisions(base) if digest.startswith(name)]
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise UnknownRevisionError(f"Revision {name} is ambiguous: it matches {len(matches)} revisions.")
    raise UnknownRevisionError(f"Unknown revision {name!r}.")


def resolve_revision(base, spec):
    """Turn HEAD, HEAD~2, HEAD^, a branch name, or a unique digest prefix into a full digest."""
    match = HEAD_RELATIVE.fullmatch(spec or "")
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


def walk(base, start=None):
    """Revisions reachable from start, newest first, as (digest, revision)."""
    pending = [start or head_revision(base)] if (start or head_revision(base)) else []
    seen = {}
    while pending:
        digest = pending.pop()
        if digest not in seen:
            seen[digest] = read_revision(base, digest)
            pending.extend(seen[digest]["parents"])
    return sorted(seen.items(), key=lambda item: (item[1]["time"], item[0]), reverse=True)


def snapshot_at(base, revision):
    """The objects as they stood at a revision, in the shape semantic_changes compares."""
    snapshot = {collection: [] for collection in COLLECTIONS}
    tree = read_revision(base, revision)["tree"] if revision else {}
    for obj_id, digest in sorted(tree.items()):
        data = json.loads(_content_path(base, OBJECTS, digest).read_text(encoding="utf-8"))
        snapshot[SUBDIRS[obj_id.split("-", 1)[0]]].append(data)
    return snapshot


def verify(base):
    """Check every reachable revision and object version against its digest."""
    issues = []
    checked = set()

    def check(kind, path, expected):
        if not path.is_file():
            issues.append({"code": f"{kind}_MISSING", "id": expected, "message": f"{path} is missing"})
            return False
        if _digest(path.read_bytes()) != expected:
            issues.append({"code": f"{kind}_CORRUPT", "id": expected, "message": f"{path} does not match its digest"})
            return False
        return True

    pending = [head_revision(base)] if head_revision(base) else []
    while pending:
        digest = pending.pop()
        if digest in checked:
            continue
        checked.add(digest)
        if not check("REVISION", _content_path(base, REVISIONS, digest), digest):
            continue
        revision = read_revision(base, digest)
        pending.extend(revision["parents"])
        for version in revision["tree"].values():
            if version not in checked:
                checked.add(version)
                check("OBJECT_VERSION", _content_path(base, OBJECTS, version), version)
    return issues


def migrate(base):
    """Turn a 7.x workspace into a repository, its objects forming the first revision."""
    backups = _safe_directory(base, BACKUPS)
    backups.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backups / f"intent-7-{stamp}.tar.gz"
    with tarfile.open(backup, "w:gz") as archive:
        for name in (*SUBDIRS.values(), "hub.json", "maintenance.json"):
            if (Path(base) / name).exists():
                archive.add(Path(base) / name, arcname=name)
    create_repository(base)
    return commit_worktree(base, "migrate", summary="Migrated from Intent 7"), backup
