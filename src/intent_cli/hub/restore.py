"""Cooperative, recoverable installation of one complete local snapshot.

The caller holds the workspace lock.  Directory-level swaps are journalled so
ordinary failures can roll back and interrupted operations can be recovered by
the next lock holder.  This is not a power-loss transaction or a defence against
non-cooperating processes replacing paths during an operation.
"""

import hashlib
import json
import os
import re
import shutil
import stat
import uuid
from intent_cli import store


JOURNAL_NAME = ".pull-journal.json"
COMPONENTS = ("intents", "snaps", "decisions", "hub.json")
SNAPSHOT_TYPES = {"intents": "intent", "snaps": "snap", "decisions": "decision"}
TRANSACTION_NAME = re.compile(r"\.pull-[0-9a-f]{32}", re.ASCII)
DIGEST = re.compile(r"[0-9a-f]{64}", re.ASCII)


class PullApplyError(store.StorageSecurityError):
    """A failed installation or recovery, with an explicit local-state boundary."""

    def __init__(self, message, *, recovery_required=False, committed=False):
        self.recovery_required = bool(recovery_required)
        self.committed = bool(committed)
        super().__init__(message)


def _exists(path):
    return path.exists() or path.is_symlink()


def _check_component(path, name, *, optional=False):
    """Check a fixed component root without following a symlink."""
    if path.is_symlink():
        raise PullApplyError(f"Pull component must not be a symlink: {path}")
    if not path.exists():
        if optional:
            return False
        raise PullApplyError(f"Pull component is missing: {path}")
    expected = path.is_file() if name == "hub.json" else path.is_dir()
    if not expected:
        raise PullApplyError(f"Pull component has an unsafe type: {path}")
    return True


def _component_digest(path):
    """Hash complete component contents, retaining but never following links."""
    digest = hashlib.sha256()

    def visit(node, relative):
        metadata = node.lstat()
        mode = metadata.st_mode
        if stat.S_ISLNK(mode):
            kind, content = "link", os.readlink(node)
        elif stat.S_ISDIR(mode):
            kind, content = "directory", ""
        elif stat.S_ISREG(mode):
            kind, content = "file", metadata.st_size
        else:
            raise PullApplyError(f"Unsupported special file in pull component: {node}")
        digest.update(json.dumps([relative, kind, content], ensure_ascii=True).encode("ascii"))
        digest.update(b"\0")
        if kind == "file":
            with node.open("rb") as source:
                for chunk in iter(lambda: source.read(65536), b""):
                    digest.update(chunk)
            digest.update(b"\0")
        elif kind == "directory":
            for child in sorted(node.iterdir(), key=lambda entry: entry.name):
                child_relative = f"{relative}/{child.name}" if relative else child.name
                visit(child, child_relative)

    visit(path, "")
    return digest.hexdigest()


def _transaction_path(base, name):
    if not isinstance(name, str) or TRANSACTION_NAME.fullmatch(name) is None:
        raise PullApplyError("Pull journal has an invalid transaction directory.", recovery_required=True)
    path = base / name
    if path.is_symlink():
        raise PullApplyError("Pull transaction directory must not be a symlink.", recovery_required=True)
    if path.resolve(strict=False).parent != base.resolve(strict=True):
        raise PullApplyError("Pull transaction directory escapes storage.", recovery_required=True)
    return path


def _validate_transaction_layout(txn):
    """Never clean a transaction containing unrelated top-level paths."""
    if not _exists(txn):
        return
    if txn.is_symlink() or not txn.is_dir():
        raise PullApplyError("Pull transaction storage is unsafe.", recovery_required=True)
    for area in txn.iterdir():
        if area.name not in {"new", "backup"} or area.is_symlink() or not area.is_dir():
            raise PullApplyError("Pull transaction contains an unexpected path.", recovery_required=True)
        for component in area.iterdir():
            if component.name not in COMPONENTS:
                raise PullApplyError("Pull transaction contains an unexpected component.", recovery_required=True)
            _check_component(component, component.name)


def _read_journal(base):
    path = base / JOURNAL_NAME
    if not _exists(path):
        return None
    if path.is_symlink() or not path.is_file():
        raise PullApplyError("Pull journal must be a regular file.", recovery_required=True)
    try:
        journal = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise PullApplyError("Pull journal is unreadable or malformed.", recovery_required=True) from exc
    if (
        not isinstance(journal, dict)
        or type(journal.get("version")) is not int
        or journal["version"] != 1
        or not isinstance(journal.get("state"), str)
        or journal["state"] not in {"applying", "committed"}
        or not isinstance(journal.get("original_exists"), dict)
        or set(journal["original_exists"]) != set(COMPONENTS)
        or any(type(value) is not bool for value in journal["original_exists"].values())
        or not isinstance(journal.get("original_sha256"), dict)
        or set(journal["original_sha256"]) != set(COMPONENTS)
        or not isinstance(journal.get("target_sha256"), dict)
        or set(journal["target_sha256"]) != set(COMPONENTS)
    ):
        raise PullApplyError("Pull journal has an invalid schema.", recovery_required=True)
    for name in COMPONENTS:
        original = journal["original_sha256"][name]
        target = journal["target_sha256"][name]
        if (
            not isinstance(target, str)
            or DIGEST.fullmatch(target) is None
            or (journal["original_exists"][name] and (
                not isinstance(original, str) or DIGEST.fullmatch(original) is None
            ))
            or (not journal["original_exists"][name] and original is not None)
            or (name != "hub.json" and not journal["original_exists"][name])
        ):
            raise PullApplyError("Pull journal has invalid component identities.", recovery_required=True)
    _transaction_path(base, journal.get("txn_dir"))
    return journal


def _write_journal(base, journal):
    path = base / JOURNAL_NAME
    if path.is_symlink():
        raise PullApplyError("Pull journal must not be a symlink.", recovery_required=True)
    store._write_json_atomic(path, journal)


def _replace_component(source, destination):
    os.replace(source, destination)


def _remove_component(path, name):
    if not _check_component(path, name, optional=True):
        return
    if name == "hub.json":
        path.unlink()
    else:
        shutil.rmtree(path)


def _cleanup_transaction(base, journal):
    txn = _transaction_path(base, journal["txn_dir"])
    _validate_transaction_layout(txn)
    if txn.exists():
        shutil.rmtree(txn)
    (base / JOURNAL_NAME).unlink(missing_ok=True)


def _validate_recovery_state(base, txn, journal):
    """Validate every affected path before rollback changes any live component."""
    _validate_transaction_layout(txn)
    committed = journal["state"] == "committed"
    for name in COMPONENTS:
        live, backup = base / name, txn / "backup" / name
        live_exists = _check_component(live, name, optional=True)
        backup_exists = _check_component(backup, name, optional=True)
        original = journal["original_sha256"][name]
        target = journal["target_sha256"][name]
        if backup_exists and not committed:
            if not journal["original_exists"][name] or _component_digest(backup) != original:
                raise PullApplyError("Pull backup does not match the original component.", recovery_required=True)
        if committed:
            if not live_exists or _component_digest(live) != target:
                raise PullApplyError("Committed pull component has changed or is missing.", recovery_required=True, committed=True)
        elif backup_exists:
            if live_exists and _component_digest(live) not in {original, target}:
                raise PullApplyError("Pull component changed outside its transaction.", recovery_required=True)
        elif journal["original_exists"][name]:
            if not live_exists or _component_digest(live) != original:
                raise PullApplyError("Original pull component is unavailable for recovery.", recovery_required=True)
        elif live_exists and _component_digest(live) != target:
            raise PullApplyError("New pull component changed outside its transaction.", recovery_required=True)


def recover_pending_snapshot(base):
    """Recover one journal under the already-held stable workspace lock."""
    base, _resolved = store._safe_storage_root(base)
    journal = _read_journal(base)
    if journal is None:
        return False
    committed = journal["state"] == "committed"
    try:
        txn = _transaction_path(base, journal["txn_dir"])
        _validate_recovery_state(base, txn, journal)
        if not committed:
            for name in reversed(COMPONENTS):
                live, backup = base / name, txn / "backup" / name
                if _exists(backup):
                    _remove_component(live, name)
                    _replace_component(backup, live)
                elif not journal["original_exists"][name]:
                    _remove_component(live, name)
        _cleanup_transaction(base, journal)
        return True
    except Exception as exc:
        raise PullApplyError(
            f"Pull {'cleanup' if committed else 'recovery'} failed: {exc}",
            recovery_required=True,
            committed=committed,
        ) from exc


def _stage_snapshot(base, new, snapshot, hub_config):
    if not isinstance(snapshot, dict) or set(snapshot) != set(SNAPSHOT_TYPES):
        raise PullApplyError("Pull snapshot must contain the three object arrays.")
    if not isinstance(hub_config, dict):
        raise PullApplyError("Local pull configuration must be an object.")
    for directory, object_type in SNAPSHOT_TYPES.items():
        values = snapshot[directory]
        if not isinstance(values, list):
            raise PullApplyError(f"Pull snapshot {directory} must be an array.")
        shutil.copytree(base / directory, new / directory, symlinks=True)
        # Only canonical, validated semantic objects are replaced. Other local
        # files and directories (including links) remain unchanged in the copy.
        for previous in store.list_objects(new, object_type):
            (new / directory / f"{previous['id']}.json").unlink()
        seen = set()
        for obj in values:
            if not isinstance(obj, dict):
                raise PullApplyError(f"Pull snapshot {directory} contains a non-object.")
            obj_id = store.validate_object_id(object_type, obj.get("id"))
            if obj_id in seen:
                raise PullApplyError(f"Pull snapshot contains duplicate ID {obj_id}.")
            seen.add(obj_id)
            store.create_object(new, object_type, obj_id, obj)
    report = store.validate_graph(store.load_graph_once(new))
    if not report["healthy"]:
        raise PullApplyError("Pull snapshot has invalid object relationships or statuses.")
    safe_config = dict(hub_config)
    safe_config.pop("auth_token", None)
    store._write_json_atomic(new / "hub.json", safe_config)


def install_snapshot(base, snapshot, hub_config):
    """Install all objects/config, or recover originals after ordinary failure.

    The caller must already hold ``workspace_write_lock(base)``. A simulated or
    real process interruption deliberately leaves the journal for the next
    holder. The stable lock file is never moved or replaced.
    """
    try:
        base, _resolved = store._safe_storage_root(base)
        if _read_journal(base) is not None:
            raise PullApplyError("A previous pull requires recovery before installation.", recovery_required=True)
        original_exists, original_digests = {}, {}
        for name in COMPONENTS:
            present = _check_component(base / name, name, optional=name == "hub.json")
            original_exists[name] = present
            original_digests[name] = _component_digest(base / name) if present else None
        txn = _transaction_path(base, f".pull-{uuid.uuid4().hex}")
    except PullApplyError:
        raise
    except Exception as exc:
        raise PullApplyError(f"Pull preflight failed: {exc}") from exc
    journal = None
    created = False
    try:
        txn.mkdir(mode=0o700)
        created = True
        new, backup = txn / "new", txn / "backup"
        new.mkdir()
        backup.mkdir()
        _stage_snapshot(base, new, snapshot, hub_config)
        journal = {
            "version": 1,
            "txn_dir": txn.name,
            "state": "applying",
            "original_exists": original_exists,
            "original_sha256": original_digests,
            "target_sha256": {name: _component_digest(new / name) for name in COMPONENTS},
        }
        _write_journal(base, journal)
        for name in COMPONENTS:
            if original_exists[name]:
                _replace_component(base / name, backup / name)
            _replace_component(new / name, base / name)
        committed_journal = dict(journal, state="committed")
        _write_journal(base, committed_journal)
        _cleanup_transaction(base, committed_journal)
    except Exception as exc:
        persisted = None
        try:
            persisted = _read_journal(base)
            if persisted is not None:
                recover_pending_snapshot(base)
            elif created:
                _validate_transaction_layout(txn)
                shutil.rmtree(txn)
        except Exception as recovery_exc:
            raise PullApplyError(
                f"Pull installation failed ({exc}); recovery also failed ({recovery_exc}).",
                recovery_required=True,
                committed=bool(persisted and persisted["state"] == "committed"),
            ) from exc
        raise PullApplyError(
            f"Pull installation failed: {exc}",
            recovery_required=False,
            committed=bool(persisted and persisted["state"] == "committed"),
        ) from exc
