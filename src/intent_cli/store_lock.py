"""One writer at a time in a workspace, across processes."""

import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from intent_cli.store_errors import UnsafeStoragePathError, WorkspaceBusyError
from intent_cli.store_paths import _safe_storage_root, shared_root


def _read_lock_owner(lock_file):
    try:
        lock_file.seek(0)
        raw = lock_file.read(4096).lstrip(b"\0")
        if not raw:
            return {}
        owner = json.loads(raw.decode("utf-8"))
        if not isinstance(owner, dict):
            return {}
        return {
            key: owner[key]
            for key in ("pid", "operation", "started_at")
            if key in owner
        }
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _write_lock_owner(lock_file, operation):
    owner = {
        "pid": os.getpid(),
        "operation": operation or "unknown",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    lock_file.seek(0)
    lock_file.truncate()
    lock_file.write(json.dumps(owner, ensure_ascii=True).encode("ascii"))
    lock_file.flush()
    os.fsync(lock_file.fileno())


@contextmanager
def workspace_write_lock(base, timeout=10.0, operation=None):
    """Serialize writers for one workspace without leaving a stale lock state."""
    base, _resolved_base = _safe_storage_root(base)
    # Worktrees share refs and revisions, so they share one writer too.
    lock_path = shared_root(base) / ".write.lock"
    if lock_path.is_symlink():
        raise UnsafeStoragePathError(lock_path, "Workspace lock must not be a symlink")
    lock_file = lock_path.open("a+b")
    acquired = False
    deadline = time.monotonic() + timeout

    if os.name == "nt":
        import msvcrt

        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()

        def try_lock():
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)

        def unlock():
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        def try_lock():
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        def unlock():
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    try:
        while not acquired:
            try:
                try_lock()
                acquired = True
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise WorkspaceBusyError(
                        "Another Intent command is writing to this workspace.",
                        owner=_read_lock_owner(lock_file),
                    )
                time.sleep(0.05)
        _write_lock_owner(lock_file, operation)
        # Lazy import avoids the storage/installer dependency cycle. Recovery
        # needs only the root and lock, not complete live object directories.
        from intent_cli.hub.restore import recover_pending_snapshot
        recover_pending_snapshot(base)
        yield
    finally:
        if acquired:
            lock_file.seek(0)
            lock_file.truncate()
            if os.name == "nt":
                lock_file.write(b"\0")
                lock_file.flush()
            unlock()
        lock_file.close()
