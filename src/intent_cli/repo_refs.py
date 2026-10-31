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
HEAD_FILE = "HEAD"
REFS = "refs"
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
BRANCH = re.compile(r"[^\W.][\w.-]*(?:/[^\W.][\w.-]*)*\Z")
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


def branch_revision(base, branch):
    path = _branch_path(base, branch)
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if DIGEST.fullmatch(text) is None:
        raise StoredObjectIntegrityError(path, "branch does not hold a revision")
    return text


def set_branch(base, branch, revision):
    ref = _branch_path(base, branch)
    ref.parent.mkdir(parents=True, exist_ok=True)
    replace_file(ref, f"{revision}\n".encode("ascii"))


def list_branches(base):
    heads = contained(storage_root(base), REFS, "heads")
    if not heads.is_dir():
        return []
    names = (path.relative_to(heads).as_posix() for path in heads.rglob("*") if path.is_file() and not path.is_symlink())
    return sorted(name for name in names if valid_branch_name(name))


def branch_conflict(base, branch):
    """The existing branch a new name cannot sit beside: refs a and a/b are a file and a folder."""
    parts = branch.split("/")
    for depth in range(1, len(parts)):
        prefix = "/".join(parts[:depth])
        if valid_branch_name(prefix) and _branch_path(base, prefix).is_file():
            return prefix
    return next((name for name in list_branches(base) if name.startswith(f"{branch}/")), None)


def delete_branch(base, branch):
    path = _branch_path(base, branch)
    path.unlink()
    heads = contained(storage_root(base), REFS, "heads")
    parent = path.parent
    while parent != heads and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent


def head_revision(base):
    """The revision HEAD points at, or None on a branch with no revision yet."""
    return branch_revision(base, current_branch(base))
