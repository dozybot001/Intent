"""Storage layer — .intent/ directory I/O and ID generation."""

import json
import os
import re
import subprocess
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

INTENT_DIR = ".intent"
SUBDIRS = {"intent": "intents", "snap": "snaps", "decision": "decisions"}
HUB_CONFIG = "hub.json"
VALID_STATUSES = {
    "intent": {"active", "suspend", "done", "cancelled"},
    "decision": {"active", "deprecated"},
}
OBJECT_ID_PATTERNS = {
    object_type: re.compile(rf"{object_type}-[0-9]+", re.ASCII)
    for object_type in SUBDIRS
}


class StorageSecurityError(RuntimeError):
    """Base class for storage paths or data that are unsafe to use."""


class InvalidObjectIdError(StorageSecurityError):
    """Raised when an object ID cannot name an object of the requested type."""

    def __init__(self, object_type, obj_id):
        self.object_type = object_type
        self.obj_id = obj_id
        super().__init__(
            f"Invalid {object_type} ID {obj_id!r}; expected "
            f"'{object_type}-' followed by ASCII digits."
        )


class UnsafeStoragePathError(StorageSecurityError):
    """Raised when a storage path escapes or redirects the .intent boundary."""

    def __init__(self, path, message):
        self.path = Path(path)
        super().__init__(f"{message}: {self.path}")


class StoredObjectIntegrityError(StorageSecurityError):
    """Raised when a stored object's filename and identity fields disagree."""

    def __init__(self, path, message):
        self.path = Path(path)
        super().__init__(f"Invalid stored object at {self.path}: {message}")


class WorkspaceBusyError(RuntimeError):
    """Raised when another Intent writer holds the workspace lock."""


def validate_object_id(object_type, obj_id):
    """Validate and return a type-specific, path-safe local object ID."""
    pattern = OBJECT_ID_PATTERNS.get(object_type)
    if (
        pattern is None
        or not isinstance(obj_id, str)
        or pattern.fullmatch(obj_id) is None
    ):
        raise InvalidObjectIdError(object_type, obj_id)
    return obj_id


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


def _validate_stored_object_id(obj, path, expected_id):
    """Verify that object data agrees with its storage filename."""
    if not isinstance(obj, dict):
        raise StoredObjectIntegrityError(path, "top-level JSON must be an object")
    if obj.get("id") != expected_id:
        raise StoredObjectIntegrityError(
            path,
            f"field 'id' is {obj.get('id')!r}, expected {expected_id!r}",
        )
    return obj


def _load_and_validate_object_id(path, expected_id):
    """Load JSON and verify that its ID agrees with its storage filename."""
    obj = json.loads(path.read_text(encoding="utf-8"))
    return _validate_stored_object_id(obj, path, expected_id)


def git_root():
    """Return git repo root as Path, or None."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def intent_dir():
    """Return Path to .intent/, or None if not in a git repo."""
    root = git_root()
    return root / INTENT_DIR if root else None


def ensure_init():
    """Return .intent/ Path if initialized, else None."""
    d = intent_dir()
    if d is None or (not d.exists() and not d.is_symlink()):
        return None
    _safe_storage_root(d)
    for object_type in SUBDIRS:
        _safe_object_dir(d, object_type)
    return d


def init_workspace():
    """Create .intent/ structure. Returns (path, error_code)."""
    root = git_root()
    if root is None:
        return None, "GIT_STATE_INVALID"
    d = root / INTENT_DIR
    if d.is_symlink():
        raise UnsafeStoragePathError(d, ".intent storage must not be a symlink")
    if d.is_dir():
        return None, "ALREADY_EXISTS"
    try:
        d.mkdir()
    except FileExistsError:
        return None, "ALREADY_EXISTS"
    for sub in SUBDIRS.values():
        (d / sub).mkdir()
    return d, None


def ensure_local_git_exclude(root):
    """Exclude .intent/ through Git's repository-local info/exclude file."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-path", "info/exclude"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        path = Path(result.stdout.strip())
        if not path.is_absolute():
            path = root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if any(line.strip() in {INTENT_DIR, f"{INTENT_DIR}/"} for line in existing.splitlines()):
            return True
        with path.open("a", encoding="utf-8") as exclude_file:
            if existing and not existing.endswith("\n"):
                exclude_file.write("\n")
            exclude_file.write(f"{INTENT_DIR}/\n")
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


@contextmanager
def workspace_write_lock(base, timeout=10.0):
    """Serialize writers for one workspace without leaving a stale lock state."""
    base, _resolved_base = _safe_storage_root(base)
    lock_path = base / ".write.lock"
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
                        "Another Intent command is writing to this workspace."
                    )
                time.sleep(0.05)
        yield
    finally:
        if acquired:
            unlock()
        lock_file.close()


def make_runtime_id(prefix):
    """Generate a runtime-scoped ID for local hub state."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def next_id(base, object_type):
    """Generate next zero-padded ID for a given object type."""
    subdir, _resolved_subdir = _safe_object_dir(base, object_type)
    max_num = 0
    for f in subdir.glob(f"{object_type}-*.json"):
        try:
            validate_object_id(object_type, f.stem)
        except InvalidObjectIdError as exc:
            raise StoredObjectIntegrityError(
                f, "filename is not a valid object ID"
            ) from exc
        _safe_object_path(base, object_type, f.stem)
        num = int(f.stem.split("-", 1)[1])
        max_num = max(max_num, num)
    return f"{object_type}-{max_num + 1:03d}"


def read_object(base, object_type, obj_id):
    """Read object JSON by ID. Returns dict or None."""
    path = _safe_object_path(base, object_type, obj_id)
    if not path.is_file():
        return None
    return _load_and_validate_object_id(path, obj_id)


def _write_json_atomic(path, data):
    """Write JSON through a same-directory temporary file and atomic replace."""
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(json.dumps(data, indent=2, ensure_ascii=False))
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(str(temp_path), str(path))
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass


def write_object(base, object_type, obj_id, data):
    """Atomically write an object dict to its JSON file."""
    path = _safe_object_path(base, object_type, obj_id)
    _validate_stored_object_id(data, path, obj_id)
    _write_json_atomic(path, data)


def list_objects(base, object_type, status=None):
    """List all objects of a type, optionally filtered by status."""
    subdir, _resolved_subdir = _safe_object_dir(base, object_type)
    result = []
    for f in sorted(subdir.glob(f"{object_type}-*.json")):
        try:
            validate_object_id(object_type, f.stem)
        except InvalidObjectIdError as exc:
            raise StoredObjectIntegrityError(
                f, "filename is not a valid object ID"
            ) from exc
        path = _safe_object_path(base, object_type, f.stem)
        obj = _load_and_validate_object_id(path, f.stem)
        if status is None or obj.get("status") == status:
            result.append(obj)
    return result



def read_hub_config(base):
    """Read hub.json if present. Returns dict or None."""
    path = base / HUB_CONFIG
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_hub_config(base, data):
    """Atomically write hub.json."""
    _write_json_atomic(base / HUB_CONFIG, data)


def git_current_branch():
    """Return current branch name, or None."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def git_head_commit():
    """Return HEAD commit SHA, or None."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def git_is_dirty():
    """Return True when the working tree has tracked or untracked changes."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, check=True,
        )
        return bool(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def git_remote_url(name="origin"):
    """Return the configured git remote URL, or None."""
    try:
        out = subprocess.run(
            ["git", "remote", "get-url", name],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def parse_github_remote(remote_url):
    """Parse a GitHub remote URL into owner/name metadata."""
    if not remote_url:
        return None

    cleaned = remote_url.strip()
    marker = "github.com"
    if marker not in cleaned:
        return None

    tail = cleaned.split(marker, 1)[1]
    tail = tail.lstrip(":/")
    if tail.endswith(".git"):
        tail = tail[:-4]

    parts = [part for part in tail.split("/") if part]
    if len(parts) < 2:
        return None

    owner, name = parts[0], parts[1]
    return {
        "provider": "github",
        "repo_id": f"{owner}/{name}",
        "owner": owner,
        "name": name,
    }


def validate_graph(base):
    """Validate the object graph and return a structured report."""
    intents = {obj["id"]: obj for obj in list_objects(base, "intent")}
    snaps = {obj["id"]: obj for obj in list_objects(base, "snap")}
    decisions = {obj["id"]: obj for obj in list_objects(base, "decision")}
    issues = []

    def add_issue(code, object_type, obj_id, message):
        issues.append({
            "code": code,
            "object": object_type,
            "id": obj_id,
            "message": message,
        })

    for object_type, objects in (
        ("intent", intents),
        ("snap", snaps),
        ("decision", decisions),
    ):
        for obj_id, obj in objects.items():
            if obj.get("object") != object_type:
                add_issue(
                    "OBJECT_TYPE_MISMATCH",
                    object_type,
                    obj_id,
                    f"Stored object type is '{obj.get('object')}', expected '{object_type}'.",
                )
            if object_type in VALID_STATUSES:
                status = obj.get("status")
                if status not in VALID_STATUSES[object_type]:
                    add_issue(
                        "INVALID_STATUS",
                        object_type,
                        obj_id,
                        f"Invalid status '{status}' for {object_type}.",
                    )

    for intent_id, intent in intents.items():
        for snap_id in intent.get("snap_ids", []):
            snap = snaps.get(snap_id)
            if snap is None:
                add_issue(
                    "MISSING_REFERENCE",
                    "intent",
                    intent_id,
                    f"References missing snap {snap_id} in snap_ids.",
                )
                continue
            if snap.get("intent_id") != intent_id:
                add_issue(
                    "BROKEN_LINK",
                    "intent",
                    intent_id,
                    f"Snap {snap_id} points to intent {snap.get('intent_id')}, not {intent_id}.",
                )
        for decision_id in intent.get("decision_ids", []):
            decision = decisions.get(decision_id)
            if decision is None:
                add_issue(
                    "MISSING_REFERENCE",
                    "intent",
                    intent_id,
                    f"References missing decision {decision_id} in decision_ids.",
                )
                continue
            if intent_id not in decision.get("intent_ids", []):
                add_issue(
                    "BROKEN_LINK",
                    "intent",
                    intent_id,
                    f"Decision {decision_id} does not link back to this intent.",
                )

    for snap_id, snap in snaps.items():
        intent_id = snap.get("intent_id")
        intent = intents.get(intent_id)
        if intent is None:
            add_issue(
                "MISSING_REFERENCE",
                "snap",
                snap_id,
                f"Points to missing intent {intent_id}.",
            )
            continue
        if snap_id not in intent.get("snap_ids", []):
            add_issue(
                "BROKEN_LINK",
                "snap",
                snap_id,
                f"Intent {intent_id} does not include this snap in snap_ids.",
            )

    for decision_id, decision in decisions.items():
        for intent_id in decision.get("intent_ids", []):
            intent = intents.get(intent_id)
            if intent is None:
                add_issue(
                    "MISSING_REFERENCE",
                    "decision",
                    decision_id,
                    f"References missing intent {intent_id} in intent_ids.",
                )
                continue
            if decision_id not in intent.get("decision_ids", []):
                add_issue(
                    "BROKEN_LINK",
                    "decision",
                    decision_id,
                    f"Intent {intent_id} does not link back to this decision.",
                )

    return {
        "healthy": not issues,
        "issues": issues,
    }
