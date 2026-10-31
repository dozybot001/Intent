"""HEAD and branches, and the safe file operations everything in the repository rests on.

A ref holds a revision digest and HEAD names a branch. Neither is trusted when read
back: a stored name or digest never reaches a path unvalidated.
"""

import os
import re
import tempfile

from intent_cli.store_errors import StoredObjectIntegrityError, UnsafeStoragePathError
from intent_cli.store_paths import _safe_storage_root, shared_root

DEFAULT_BRANCH = "main"
REMOTE = "origin"
HEAD_FILE = "HEAD"
REFS = "refs"
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
BRANCH = re.compile(r"[^\W.][\w.-]*(?:/[^\W.][\w.-]*)*\Z")
BRANCH_MAX_BYTES = 200
WINDOWS_RESERVED = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?\Z", re.IGNORECASE)


def contained(root, *parts):
    """A path under root with no symlink along the way, so nothing stored can redirect a write."""
    path = root
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise UnsafeStoragePathError(path, "Repository paths must not be symlinks")
    return path


def storage_root(base):
    return _safe_storage_root(shared_root(base))[0]


def replace_file(path, raw):
    """Install a whole file atomically and durably."""
    descriptor, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    if os.name != "nt":
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def valid_branch_name(name):
    """Git's rules, plus names Windows cannot store and names that read as a full digest."""
    return (isinstance(name, str) and BRANCH.fullmatch(name) is not None and ".." not in name and name != "HEAD"
            and DIGEST.fullmatch(name) is None
            and not any(part.endswith((".", ".lock")) or WINDOWS_RESERVED.fullmatch(part) for part in name.split("/")))


def new_branch_name(name):
    """A name every copy can store as a file. Branches made before this limit stay valid."""
    return valid_branch_name(name) and len(name.encode("utf-8")) <= BRANCH_MAX_BYTES


def _head_path(base):
    root, _resolved = _safe_storage_root(base)
    return contained(root, HEAD_FILE)


def current_branch(base):
    """The branch HEAD names."""
    path = _head_path(base)
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as exc:
        raise StoredObjectIntegrityError(path, "HEAD cannot be read") from exc
    prefix = f"ref: {REFS}/heads/"
    name = text[len(prefix):] if text.startswith(prefix) else ""
    if not valid_branch_name(name):
        raise StoredObjectIntegrityError(path, "HEAD does not name a branch")
    return name


def set_head(base, branch):
    replace_file(_head_path(base), f"ref: {REFS}/heads/{branch}\n".encode("utf-8"))


def _branch_path(base, branch):
    if not valid_branch_name(branch):
        raise UnsafeStoragePathError(storage_root(base) / REFS, f"{branch!r} is not a branch name")
    return contained(storage_root(base), REFS, "heads", *branch.split("/"))


def _read_ref(path):
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if DIGEST.fullmatch(text) is None:
        raise StoredObjectIntegrityError(path, "branch does not hold a revision")
    return text


def _write_ref(path, revision):
    path.parent.mkdir(parents=True, exist_ok=True)
    replace_file(path, f"{revision}\n".encode("ascii"))


def branch_revision(base, branch):
    return _read_ref(_branch_path(base, branch))


def set_branch(base, branch, revision):
    _write_ref(_branch_path(base, branch), revision)


def _names(folder):
    if not folder.is_dir():
        return []
    names = (path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file() and not path.is_symlink())
    return sorted(name for name in names if valid_branch_name(name))


def list_branches(base):
    return _names(contained(storage_root(base), REFS, "heads"))


def _remote_path(base, branch):
    if not valid_branch_name(branch):
        raise UnsafeStoragePathError(storage_root(base) / REFS, f"{branch!r} is not a branch name")
    return contained(storage_root(base), REFS, "remotes", REMOTE, *branch.split("/"))


def remote_revision(base, branch):
    """Where the remote's branch stood when it was last fetched or pushed, like refs/remotes/origin/main."""
    return _read_ref(_remote_path(base, branch))


def set_remote_revision(base, branch, revision):
    _write_ref(_remote_path(base, branch), revision)


def remote_branches(base):
    folder = contained(storage_root(base), REFS, "remotes", REMOTE)
    return {name: _read_ref(_remote_path(base, name)) for name in _names(folder)}


def delete_remote_branch(base, branch):
    _unlink_ref(_remote_path(base, branch), contained(storage_root(base), REFS, "remotes", REMOTE))


def _unlink_ref(path, root):
    path.unlink(missing_ok=True)
    parent = path.parent
    while parent != root and parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent


def conflicting_ref(names, name):
    """The name a new ref cannot sit beside: a and a/b are a file and a folder, and A and a can be one file."""
    folded = name.casefold()
    for other in names:
        theirs = other.casefold()
        if other != name and (theirs == folded or theirs.startswith(f"{folded}/") or folded.startswith(f"{theirs}/")):
            return other
    return None


def branch_conflict(base, branch):
    return conflicting_ref(list_branches(base), branch)


def delete_branch(base, branch):
    _unlink_ref(_branch_path(base, branch), contained(storage_root(base), REFS, "heads"))


def head_revision(base):
    """The revision HEAD points at, or None on a branch with no revision yet."""
    return branch_revision(base, current_branch(base))
