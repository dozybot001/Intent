"""Keep every storage path inside .intent/."""

from pathlib import Path
from intent_cli.store_errors import InvalidObjectIdError, UnsafeStoragePathError
from intent_cli.store_schema import SUBDIRS, validate_object_id


WORKTREES = "worktrees"


def shared_root(base):
    """The .intent/ a linked Git worktree's private directory belongs to; otherwise base itself."""
    base = Path(base)
    return base.parent.parent if base.parent.name == WORKTREES else base


def _safe_storage_root(base):
    """Return a real .intent directory that is not itself a symlink."""
    base = Path(base)
    if base.is_symlink():
        raise UnsafeStoragePathError(base, ".intent storage must not be a symlink")
    if not base.is_dir():
        raise UnsafeStoragePathError(base, ".intent storage is not a directory")
    try:
        resolved = base.resolve(strict=True)
        resolved_parent = base.parent.resolve(strict=True)
    except OSError as exc:
        raise UnsafeStoragePathError(base, "Could not resolve .intent storage") from exc
    if resolved.parent != resolved_parent:
        raise UnsafeStoragePathError(base, ".intent storage escapes its repository")
    return base, resolved


def _safe_object_dir(base, object_type):
    """Return the real object directory after enforcing the storage boundary."""
    if object_type not in SUBDIRS:
        raise InvalidObjectIdError(object_type, None)

    base, resolved_base = _safe_storage_root(base)
    subdir = base / SUBDIRS[object_type]
    if subdir.is_symlink():
        raise UnsafeStoragePathError(
            subdir, f"{object_type} storage directory must not be a symlink"
        )
    if not subdir.exists():
        # Git keeps no empty folders, so a clone of a committed .intent/ can lack one.
        subdir.mkdir()
    if not subdir.is_dir():
        raise UnsafeStoragePathError(
            subdir, f"{object_type} storage path is not a directory"
        )
    try:
        resolved_subdir = subdir.resolve(strict=True)
    except OSError as exc:
        raise UnsafeStoragePathError(
            subdir, f"Could not resolve {object_type} storage directory"
        ) from exc
    if resolved_subdir.parent != resolved_base:
        raise UnsafeStoragePathError(
            subdir, f"{object_type} storage directory escapes .intent"
        )
    return subdir, resolved_subdir


def _safe_object_path(base, object_type, obj_id):
    """Build a contained object path and reject every symlink redirection."""
    validate_object_id(object_type, obj_id)
    subdir, resolved_subdir = _safe_object_dir(base, object_type)
    path = subdir / f"{obj_id}.json"
    if path.is_symlink():
        raise UnsafeStoragePathError(path, "Object file must not be a symlink")
    try:
        resolved_path = path.resolve(strict=False)
    except OSError as exc:
        raise UnsafeStoragePathError(path, "Could not resolve object path") from exc
    if resolved_path.parent != resolved_subdir:
        raise UnsafeStoragePathError(path, "Object path escapes its storage directory")
    return path
