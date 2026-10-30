"""Storage layer — .intent/ directory I/O and ID generation."""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from intent_cli.store_errors import InvalidObjectIdError, StorageSecurityError, StoredObjectIntegrityError, StoredObjectParseError, StoredObjectSchemaError, StoredObjectWriteConflictError, UnsafeStoragePathError, WorkspaceBusyError  # noqa: F401
from intent_cli.store_schema import CHECKPOINT_FIELDS, CHECKPOINT_FIELD_MAX_CHARS, INTENT_DIR, OBJECT_ID_PATTERNS, RELATION_FIELDS, REQUIRED_STRING_FIELDS, SUBDIRS, VALID_STATUSES, _validate_author, _validate_checkpoint, _validate_git, _validate_object_schema, _validate_relations, _validate_stored_object_id, validate_object_id  # noqa: F401
from intent_cli.store_paths import _safe_object_dir, _safe_object_path, _safe_storage_root  # noqa: F401
from intent_cli.store_lock import _read_lock_owner, _write_lock_owner, workspace_write_lock  # noqa: F401
from intent_cli.store_graph import validate_graph  # noqa: F401

HUB_CONFIG = "hub.json"


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
    except (ValueError, RecursionError) as exc:
        raise StoredObjectParseError(path, "JSON exceeds decoder limits") from exc
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
    """Find semantic storage independently; Git only supplies a default root."""
    current = Path.cwd()
    for parent in (current, *current.parents):
        candidate = parent / INTENT_DIR
        if candidate.exists() or candidate.is_symlink():
            return candidate
        if (parent / ".git").exists():
            break
    return (git_root() or current) / INTENT_DIR


def ensure_init():
    """Return .intent/ Path if initialized, else None."""
    d = intent_dir()
    if d is None or (not d.exists() and not d.is_symlink()):
        return None
    _safe_storage_root(d)
    journal = d / ".pull-journal.json"
    if journal.exists() or journal.is_symlink():
        # Interrupted directory swaps may temporarily leave object directories
        # absent. Recover under the stable root lock before validating them.
        with workspace_write_lock(d, operation="pull.recover"):
            pass
    for object_type in SUBDIRS:
        _safe_object_dir(d, object_type)
    return d


def init_workspace():
    """Create .intent/ structure. Returns (path, error_code)."""
    root = git_root() or Path.cwd()
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


def ensure_local_git_exclude(root, patterns=(f"{INTENT_DIR}/",)):
    """Exclude private local metadata through repository-local info/exclude."""
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
        present = {line.strip().rstrip("/") for line in existing.splitlines()}
        missing = [pattern for pattern in patterns if pattern.rstrip("/") not in present]
        if not missing:
            return True
        with path.open("a", encoding="utf-8") as exclude_file:
            if existing and not existing.endswith("\n"):
                exclude_file.write("\n")
            exclude_file.write("\n".join(missing) + "\n")
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _entry_order(item):
    match = re.search(r"-([0-9]+)\.json$", item.name, re.ASCII | re.IGNORECASE)
    return (int(match.group(1)) if match else float("inf"), item.name.casefold(), item.name)


def _object_entry_groups(base, object_type):
    """Enumerate object-looking entries grouped by case-insensitive filename."""
    subdir, resolved_subdir = _safe_object_dir(base, object_type)
    prefix = f"{object_type}-"
    groups = {}
    # Numeric order, so intent-1000 follows intent-999.
    entries = sorted(subdir.iterdir(), key=_entry_order)
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


def create_objects(base, object_type, objects):
    """Create many objects like create_object, scanning the directory only once."""
    subdir, _resolved_subdir = _safe_object_dir(base, object_type)
    occupied = {entry.name.casefold() for entry in subdir.iterdir()}
    for data in objects:
        obj_id = data.get("id") if isinstance(data, dict) else None
        path = _safe_object_path(base, object_type, obj_id)
        _validate_object_schema(
            data, path, object_type, obj_id, require_object_type=True,
        )
        if path.name.casefold() in occupied:
            raise StoredObjectWriteConflictError(
                path,
                "a case-insensitive destination name is already occupied",
                conflicts=_casefold_name_conflicts(path.parent, path.name),
            )
        _create_json_atomic(path, data)
        occupied.add(path.name.casefold())


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
    base, _resolved_base = _safe_storage_root(base)
    path = base / HUB_CONFIG
    if path.is_symlink():
        raise UnsafeStoragePathError(path, "Hub config must not be a symlink")
    if not path.exists():
        return None
    if not path.is_file():
        raise UnsafeStoragePathError(path, "Hub config must be a regular file")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise StoredObjectParseError(path, str(exc)) from exc
    if not isinstance(data, dict):
        raise StoredObjectSchemaError(path, "top-level JSON must be an object")
    return data


def write_hub_config(base, data):
    """Atomically write hub.json."""
    base, _resolved_base = _safe_storage_root(base)
    path = base / HUB_CONFIG
    if path.is_symlink():
        raise UnsafeStoragePathError(path, "Hub config must not be a symlink")
    if not isinstance(data, dict):
        raise StoredObjectSchemaError(path, "top-level JSON must be an object")
    _write_json_atomic(path, data)


