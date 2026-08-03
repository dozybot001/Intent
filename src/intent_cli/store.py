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
from urllib.parse import urlsplit

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


class StoredObjectParseError(StorageSecurityError):
    """Raised when a stored object is not valid UTF-8 JSON."""

    def __init__(self, path, message):
        self.path = Path(path)
        super().__init__(f"Could not parse stored object at {self.path}: {message}")


class StoredObjectSchemaError(StorageSecurityError):
    """Raised when a stored object does not satisfy its required schema."""

    def __init__(self, path, message, *, field=None):
        self.path = Path(path)
        self.field = field
        super().__init__(f"Invalid stored object schema at {self.path}: {message}")


class StoredObjectWriteConflictError(StorageSecurityError):
    """Raised when an object create or update cannot preserve write semantics."""

    def __init__(self, path, message, *, conflicts=None):
        self.path = Path(path)
        self.conflicts = [str(conflict) for conflict in (conflicts or [])]
        super().__init__(f"Object write conflict at {self.path}: {message}")


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
        raise StoredObjectSchemaError(path, "top-level JSON must be an object")
    if "id" not in obj:
        raise StoredObjectSchemaError(
            path, "missing required field 'id'", field="id",
        )
    if not isinstance(obj["id"], str):
        raise StoredObjectSchemaError(
            path,
            f"field 'id' must be a string, got {type(obj['id']).__name__}",
            field="id",
        )
    if obj["id"] != expected_id:
        raise StoredObjectIntegrityError(
            path,
            f"field 'id' is {obj['id']!r}, expected {expected_id!r}",
        )
    return obj


REQUIRED_STRING_FIELDS = {
    "intent": ("id", "object", "created_at", "what", "why", "origin", "status"),
    "snap": ("id", "object", "created_at", "what", "why", "origin", "intent_id"),
    "decision": (
        "id", "object", "created_at", "what", "why", "origin", "status",
    ),
}
RELATION_FIELDS = {
    "intent": {"snap_ids": "snap", "decision_ids": "decision"},
    "snap": {},
    "decision": {"intent_ids": "intent"},
}


def _validate_object_schema(
    obj,
    path,
    object_type,
    expected_id,
    *,
    require_object_type=False,
):
    """Validate required object fields and relationship field types."""
    _validate_stored_object_id(obj, path, expected_id)

    for field in REQUIRED_STRING_FIELDS[object_type]:
        if field not in obj:
            raise StoredObjectSchemaError(
                path, f"missing required field {field!r}", field=field,
            )
        if not isinstance(obj[field], str):
            raise StoredObjectSchemaError(
                path,
                f"field {field!r} must be a string, got {type(obj[field]).__name__}",
                field=field,
            )

    if require_object_type and obj["object"] != object_type:
        raise StoredObjectSchemaError(
            path,
            f"field 'object' must be {object_type!r}, got {obj['object']!r}",
            field="object",
        )

    if "reason" in obj and not isinstance(obj["reason"], str):
        raise StoredObjectSchemaError(
            path,
            f"field 'reason' must be a string, got {type(obj['reason']).__name__}",
            field="reason",
        )

    for field, target_type in RELATION_FIELDS[object_type].items():
        if field not in obj:
            raise StoredObjectSchemaError(
                path, f"missing required field {field!r}", field=field,
            )
        values = obj[field]
        if not isinstance(values, list):
            raise StoredObjectSchemaError(
                path,
                f"field {field!r} must be a list of {target_type} IDs",
                field=field,
            )
        for index, value in enumerate(values):
            try:
                validate_object_id(target_type, value)
            except InvalidObjectIdError as exc:
                raise StoredObjectSchemaError(
                    path,
                    f"field {field!r} item {index} is not a valid {target_type} ID",
                    field=field,
                ) from exc

    if object_type == "snap":
        try:
            validate_object_id("intent", obj["intent_id"])
        except InvalidObjectIdError as exc:
            raise StoredObjectSchemaError(
                path,
                "field 'intent_id' is not a valid intent ID",
                field="intent_id",
            ) from exc

    return obj


def _load_and_validate_object(path, object_type, expected_id):
    """Load one object and validate its identity and required schema."""
    try:
        raw = path.read_text(encoding="utf-8")
        obj = json.loads(raw)
    except UnicodeDecodeError as exc:
        raise StoredObjectParseError(path, "file is not valid UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise StoredObjectParseError(
            path,
            f"invalid JSON at line {exc.lineno}, column {exc.colno}",
        ) from exc
    return _validate_object_schema(obj, path, object_type, expected_id)


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


def _object_entry_groups(base, object_type):
    """Enumerate object-looking entries grouped by case-insensitive filename."""
    subdir, resolved_subdir = _safe_object_dir(base, object_type)
    prefix = f"{object_type}-"
    groups = {}
    entries = sorted(
        subdir.iterdir(),
        key=lambda item: (item.name.casefold(), item.name),
    )
    for entry in entries:
        folded = entry.name.casefold()
        if folded.startswith(prefix) and folded.endswith(".json"):
            groups.setdefault(folded, []).append(entry)
    return subdir, resolved_subdir, groups


def _object_entry_identity(entry, object_type):
    """Return the canonical ID encoded by an object-looking filename."""
    match = re.fullmatch(
        rf"({object_type}-[0-9]+)\.json",
        entry.name.casefold(),
        re.ASCII,
    )
    if match is None:
        raise StoredObjectIntegrityError(
            entry, "filename is not a valid object ID",
        )
    obj_id = match.group(1)
    validate_object_id(object_type, obj_id)
    return obj_id, f"{obj_id}.json"


def _validate_discovered_object_path(entry, resolved_subdir):
    """Reject symlinked, non-file, or redirected directory entries."""
    if entry.is_symlink():
        raise UnsafeStoragePathError(entry, "Object file must not be a symlink")
    if not entry.is_file():
        raise StoredObjectIntegrityError(entry, "object path is not a regular file")
    try:
        resolved_entry = entry.resolve(strict=True)
    except OSError as exc:
        raise UnsafeStoragePathError(entry, "Could not resolve object file") from exc
    if resolved_entry.parent != resolved_subdir:
        raise UnsafeStoragePathError(
            entry, "Object file escapes its storage directory",
        )


def _casefold_name_conflicts(directory, target_name):
    """Return every directory entry colliding with target_name by casefold."""
    folded_target = target_name.casefold()
    return sorted(
        (
            entry
            for entry in directory.iterdir()
            if entry.name.casefold() == folded_target
        ),
        key=lambda entry: entry.name,
    )


def next_id(base, object_type):
    """Generate next zero-padded ID for a given object type."""
    _subdir, _resolved_subdir, groups = _object_entry_groups(base, object_type)
    max_num = 0
    for entries in groups.values():
        if len(entries) > 1:
            raise StoredObjectIntegrityError(
                entries[0],
                "multiple directory entries have the same case-insensitive name: "
                + ", ".join(entry.name for entry in entries),
            )
        obj_id, _canonical_name = _object_entry_identity(entries[0], object_type)
        num = int(obj_id.split("-", 1)[1])
        max_num = max(max_num, num)
    return f"{object_type}-{max_num + 1:03d}"


def read_object(base, object_type, obj_id):
    """Read object JSON by ID. Returns dict or None."""
    path = _safe_object_path(base, object_type, obj_id)
    conflicts = _casefold_name_conflicts(path.parent, path.name)
    if not conflicts:
        return None
    if len(conflicts) != 1 or conflicts[0].name != path.name:
        raise StoredObjectIntegrityError(
            conflicts[0],
            f"non-canonical or conflicting filename for {path.name!r}",
        )
    _validate_discovered_object_path(path, path.parent.resolve(strict=True))
    return _load_and_validate_object(path, object_type, obj_id)


def _write_json_temp(path, data):
    """Write and fsync a complete JSON temporary file beside its destination."""
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
        return temp_path
    except BaseException:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


def _write_json_atomic(path, data):
    """Write JSON through a same-directory temporary file and atomic replace."""
    temp_path = _write_json_temp(path, data)
    try:
        os.replace(str(temp_path), str(path))
    finally:
        temp_path.unlink(missing_ok=True)


def _create_json_atomic(path, data):
    """Atomically install complete JSON only when the destination is absent."""
    temp_path = _write_json_temp(path, data)
    try:
        try:
            os.link(str(temp_path), str(path))
        except FileExistsError as exc:
            raise StoredObjectWriteConflictError(
                path, "destination already exists",
            ) from exc
    finally:
        temp_path.unlink(missing_ok=True)


def create_object(base, object_type, obj_id, data):
    """Atomically create an object without replacing any existing entry."""
    path = _safe_object_path(base, object_type, obj_id)
    _validate_object_schema(
        data, path, object_type, obj_id, require_object_type=True,
    )
    conflicts = _casefold_name_conflicts(path.parent, path.name)
    if conflicts:
        raise StoredObjectWriteConflictError(
            path,
            "a case-insensitive destination name is already occupied",
            conflicts=conflicts,
        )
    _create_json_atomic(path, data)


def update_object(base, object_type, obj_id, data):
    """Atomically replace an existing canonical object, never create one."""
    path = _safe_object_path(base, object_type, obj_id)
    _validate_object_schema(
        data, path, object_type, obj_id, require_object_type=True,
    )
    conflicts = _casefold_name_conflicts(path.parent, path.name)
    if len(conflicts) != 1 or conflicts[0].name != path.name:
        message = (
            "destination does not exist"
            if not conflicts
            else "only a non-canonical or conflicting destination exists"
        )
        raise StoredObjectWriteConflictError(
            path, message, conflicts=conflicts,
        )
    _validate_discovered_object_path(path, path.parent.resolve(strict=True))
    _write_json_atomic(path, data)


def _stored_object_issue(exc, object_type, obj_id=None):
    """Convert one recoverable stored-object failure into a doctor issue."""
    if isinstance(exc, StoredObjectParseError):
        code = "OBJECT_PARSE_ERROR"
    elif isinstance(exc, StoredObjectSchemaError):
        code = "OBJECT_SCHEMA_ERROR"
    elif isinstance(exc, UnsafeStoragePathError):
        code = "UNSAFE_STORAGE"
    else:
        code = "OBJECT_INTEGRITY_ERROR"
    issue = {
        "code": code,
        "object": object_type,
        "id": obj_id,
        "message": str(exc),
        "path": str(exc.path),
    }
    if isinstance(exc, StoredObjectSchemaError) and exc.field is not None:
        issue["field"] = exc.field
    return issue


def _scan_object_type(base, object_type, *, tolerant):
    """Load one object directory strictly or aggregate recoverable damage."""
    _subdir, resolved_subdir, groups = _object_entry_groups(base, object_type)
    objects = []
    issues = []

    for entries in groups.values():
        if len(entries) > 1:
            for entry in entries:
                exc = StoredObjectIntegrityError(
                    entry,
                    "multiple directory entries have the same case-insensitive name: "
                    + ", ".join(item.name for item in entries),
                )
                if not tolerant:
                    raise exc
                issues.append(_stored_object_issue(exc, object_type))
            continue

        entry = entries[0]
        obj_id = None
        try:
            obj_id, canonical_name = _object_entry_identity(entry, object_type)
            if entry.name != canonical_name:
                raise StoredObjectIntegrityError(
                    entry,
                    f"filename must use canonical spelling {canonical_name!r}",
                )
            _validate_discovered_object_path(entry, resolved_subdir)
            objects.append(_load_and_validate_object(entry, object_type, obj_id))
        except (
            StoredObjectIntegrityError,
            StoredObjectParseError,
            StoredObjectSchemaError,
            UnsafeStoragePathError,
        ) as exc:
            if not tolerant:
                raise
            issues.append(_stored_object_issue(exc, object_type, obj_id))

    return objects, issues


def list_objects(base, object_type, status=None):
    """List all valid objects of a type, optionally filtered by status."""
    objects, _issues = _scan_object_type(base, object_type, tolerant=False)
    if status is None:
        return objects
    return [obj for obj in objects if obj.get("status") == status]


def load_graph_once(base, *, tolerant=False):
    """Load every local object exactly once into one consistent in-memory graph."""
    graph = {
        "intent": {},
        "snap": {},
        "decision": {},
        "load_issues": [],
    }
    for object_type in SUBDIRS:
        objects, issues = _scan_object_type(
            base, object_type, tolerant=tolerant,
        )
        graph[object_type] = {obj["id"]: obj for obj in objects}
        graph["load_issues"].extend(issues)
    return graph


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


SUPPORTED_GIT_PROVIDERS = {
    "github.com": "github",
    "gitee.com": "gitee",
}


def parse_repository_remote(remote_url):
    """Parse an exact supported Git host URL into provider/repository metadata."""
    if not isinstance(remote_url, str) or not remote_url.strip():
        return None

    cleaned = remote_url.strip()
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in cleaned):
        return None

    host = None
    path = None
    if "://" in cleaned:
        try:
            parsed = urlsplit(cleaned)
            _ = parsed.port
        except ValueError:
            return None
        if (
            parsed.scheme.lower() not in {"http", "https", "ssh", "git"}
            or not parsed.hostname
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            return None
        if parsed.scheme.lower() in {"http", "https", "git"} and parsed.username:
            return None
        host = parsed.hostname.casefold()
        path = parsed.path.lstrip("/")
    else:
        match = re.fullmatch(
            r"(?:(?P<user>[^@/:]+)@)?(?P<host>[^@/:]+):(?P<path>.+)",
            cleaned,
        )
        if match is None:
            return None
        host = match.group("host").casefold()
        path = match.group("path")

    provider = SUPPORTED_GIT_PROVIDERS.get(host)
    if provider is None:
        return None
    if path.endswith(".git"):
        path = path[:-4]
    parts = path.split("/")
    if len(parts) != 2 or any(not part or part in {".", ".."} for part in parts):
        return None

    owner, name = parts
    return {
        "provider": provider,
        "repo_id": f"{owner}/{name}",
        "owner": owner,
        "name": name,
    }


def validate_graph(graph):
    """Validate one in-memory graph without reading storage again."""
    intents = graph["intent"]
    snaps = graph["snap"]
    decisions = graph["decision"]
    issues = list(graph.get("load_issues", []))

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
