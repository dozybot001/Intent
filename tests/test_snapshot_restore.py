"""Hermetic safety and recovery tests for local snapshot installation."""

import copy
import json
import os
from pathlib import Path

import pytest

from intent_cli import store
from intent_cli.hub import restore


JOURNAL = ".pull-journal.json"


def _snapshot(number):
    intent_id = f"intent-{number:03d}"
    snap_id = f"snap-{number:03d}"
    decision_id = f"decision-{number:03d}"
    common = {
        "created_at": "2026-10-04T01:02:03+00:00",
        "what": f"Snapshot {number}",
        "why": "Exercise the complete local transaction",
        "origin": "pytest",
    }
    return {
        "intents": [{
            **common, "id": intent_id, "object": "intent", "status": "active",
            "snap_ids": [snap_id], "decision_ids": [decision_id],
        }],
        "snaps": [{
            **common, "id": snap_id, "object": "snap", "intent_id": intent_id,
        }],
        "decisions": [{
            **common, "id": decision_id, "object": "decision", "status": "active",
            "intent_ids": [intent_id],
        }],
    }


def _hub(number):
    return {
        "api_base_url": "https://inthub.example",
        "format_version": 2,
        "project_name": "demo",
        "project_id": "proj_demo",
        "revision": f"{number:064x}",
        "baseline_sha256": f"{number:064x}",
    }


def _write_json(path, data):
    # Deliberately non-canonical bytes: rollback must not reserialize originals.
    path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")


def _tree_state(root):
    """Capture paths and bytes without following any symbolic links."""
    state = {}

    def visit(directory):
        for entry in sorted(directory.iterdir(), key=lambda path: path.name):
            if entry == root / ".write.lock":
                continue
            relative = str(entry.relative_to(root))
            if entry.is_symlink():
                state[relative] = ("symlink", os.readlink(entry))
            elif entry.is_dir():
                state[relative] = ("directory",)
                visit(entry)
            else:
                state[relative] = ("file", entry.read_bytes())

    visit(root)
    return state


def _symlink_or_skip(link, target, *, directory=False):
    try:
        link.symlink_to(target, target_is_directory=directory)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")


def _assert_no_transaction(base):
    assert not (base / JOURNAL).exists()
    assert not (base / JOURNAL).is_symlink()
    assert list(base.glob(".pull-*")) == []


def _assert_installed(base, snapshot, hub_config):
    for subdir, objects in snapshot.items():
        paths = sorted((base / subdir).glob("*.json"))
        assert {path.name for path in paths} == {
            f"{obj['id']}.json" for obj in objects
        }
        assert [json.loads(path.read_text(encoding="utf-8")) for path in paths] == objects
    assert json.loads((base / "hub.json").read_text(encoding="utf-8")) == hub_config


@pytest.fixture
def storage(tmp_path):
    base = tmp_path / ".intent"
    base.mkdir()
    old = _snapshot(1)
    for subdir in store.SUBDIRS.values():
        (base / subdir).mkdir()
        for obj in old[subdir]:
            _write_json(base / subdir / f"{obj['id']}.json", obj)
    _write_json(base / "hub.json", _hub(1))
    return base


def _interrupted_install(base, monkeypatch, *, after_step=1):
    """Leave a real applying journal, just as a process interruption would."""
    real_replace = restore._replace_component
    calls = 0

    def interrupt_after_replace(source, destination):
        nonlocal calls
        real_replace(source, destination)
        calls += 1
        if calls == after_step:
            raise KeyboardInterrupt("simulated process interruption")

    with monkeypatch.context() as patch:
        patch.setattr(restore, "_replace_component", interrupt_after_replace)
        with pytest.raises(KeyboardInterrupt, match="simulated process interruption"):
            with store.workspace_write_lock(base, operation="pull"):
                restore.install_snapshot(base, _snapshot(2), _hub(2))
    journal = json.loads((base / JOURNAL).read_text(encoding="utf-8"))
    assert journal["state"] == "applying"
    return journal


def test_install_replaces_complete_snapshot_and_hub_without_moving_lock(storage):
    with store.workspace_write_lock(storage, operation="pull"):
        lock_before = (storage / ".write.lock").stat()
        restore.install_snapshot(storage, _snapshot(2), _hub(2))
        lock_after = (storage / ".write.lock").stat()
        assert (lock_after.st_dev, lock_after.st_ino) == (
            lock_before.st_dev, lock_before.st_ino,
        )
        _assert_installed(storage, _snapshot(2), _hub(2))
        _assert_no_transaction(storage)

    assert (storage / ".write.lock").stat().st_ino == lock_before.st_ino


def test_install_preserves_extra_files_directories_and_links(storage, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sentinel").write_bytes(b"outside must remain untouched")
    (storage / "root-note").write_bytes(b"root extra")
    _symlink_or_skip(storage / "root-link", outside, directory=True)
    for subdir in store.SUBDIRS.values():
        directory = storage / subdir
        (directory / ".private-note").write_bytes(b"hidden extra")
        (directory / "README.txt").write_bytes(b"not an object")
        (directory / "assets").mkdir()
        (directory / "assets" / "nested.bin").write_bytes(b"nested extra")
        (directory / "empty-extra-directory").mkdir()
        _symlink_or_skip(directory / "outside-link", outside, directory=True)
        _symlink_or_skip(directory / "dangling-link", tmp_path / "does-not-exist")

    before = _tree_state(storage)
    outside_before = _tree_state(outside)
    with store.workspace_write_lock(storage, operation="pull"):
        restore.install_snapshot(storage, _snapshot(2), _hub(2))

    after = _tree_state(storage)
    extras = {
        path: entry for path, entry in before.items()
        if not path.endswith(".json")
    }
    assert {path: after[path] for path in extras} == extras
    assert _tree_state(outside) == outside_before
    _assert_installed(storage, _snapshot(2), _hub(2))
    _assert_no_transaction(storage)


def test_install_does_not_persist_auth_token_from_hub_config(storage):
    config = dict(_hub(2), auth_token="must-not-persist")
    with store.workspace_write_lock(storage, operation="pull"):
        restore.install_snapshot(storage, _snapshot(2), config)
    _assert_installed(storage, _snapshot(2), _hub(2))
    assert b"must-not-persist" not in (storage / "hub.json").read_bytes()
    _assert_no_transaction(storage)


@pytest.mark.parametrize("component", ["intents", "snaps", "decisions", "hub.json"])
def test_symlinked_live_component_is_rejected_before_install(
    storage, tmp_path, component,
):
    selected = storage / component
    outside = tmp_path / f"outside-{component}"
    selected.rename(outside)
    _symlink_or_skip(selected, outside, directory=component != "hub.json")
    before = _tree_state(storage)
    outside_before = (
        _tree_state(outside) if outside.is_dir() else outside.read_bytes()
    )
    with store.workspace_write_lock(storage, operation="pull"):
        with pytest.raises((restore.PullApplyError, store.StorageSecurityError)):
            restore.install_snapshot(storage, _snapshot(2), _hub(2))
    assert _tree_state(storage) == before
    assert (
        _tree_state(outside) if outside.is_dir() else outside.read_bytes()
    ) == outside_before
    _assert_no_transaction(storage)


@pytest.mark.parametrize("subdir", list(store.SUBDIRS.values()))
def test_symlinked_existing_object_is_not_followed_or_replaced(
    storage, tmp_path, subdir,
):
    object_type = next(key for key, value in store.SUBDIRS.items() if value == subdir)
    path = storage / subdir / f"{object_type}-001.json"
    outside = tmp_path / f"outside-{object_type}.json"
    path.rename(outside)
    _symlink_or_skip(path, outside)
    before = _tree_state(storage)
    outside_before = outside.read_bytes()
    with store.workspace_write_lock(storage, operation="pull"):
        with pytest.raises((restore.PullApplyError, store.StorageSecurityError)):
            restore.install_snapshot(storage, _snapshot(2), _hub(2))
    assert _tree_state(storage) == before
    assert outside.read_bytes() == outside_before
    _assert_no_transaction(storage)


@pytest.mark.parametrize("failed_step", range(1, 9))
def test_each_backup_or_install_failure_rolls_back_original_bytes(
    storage, monkeypatch, failed_step,
):
    before = _tree_state(storage)
    real_replace = restore._replace_component
    calls = 0

    def fail_once(source, destination):
        nonlocal calls
        calls += 1
        if calls == failed_step:
            raise OSError(f"injected rename failure {failed_step}")
        return real_replace(source, destination)

    monkeypatch.setattr(restore, "_replace_component", fail_once)
    with store.workspace_write_lock(storage, operation="pull"):
        with pytest.raises(restore.PullApplyError) as exc_info:
            restore.install_snapshot(storage, _snapshot(2), _hub(2))

    assert exc_info.value.recovery_required is False
    assert exc_info.value.committed is False
    assert _tree_state(storage) == before
    _assert_no_transaction(storage)


def test_commit_marker_write_failure_rolls_back_original_bytes(storage, monkeypatch):
    before = _tree_state(storage)
    real_write = restore._write_journal
    calls = 0

    def fail_commit_marker(base, journal):
        nonlocal calls
        calls += 1
        if calls == 2:
            assert journal["state"] == "committed"
            raise OSError("injected commit marker failure")
        return real_write(base, journal)

    monkeypatch.setattr(restore, "_write_journal", fail_commit_marker)
    with store.workspace_write_lock(storage, operation="pull"):
        with pytest.raises(restore.PullApplyError) as exc_info:
            restore.install_snapshot(storage, _snapshot(2), _hub(2))

    assert calls == 2
    assert exc_info.value.recovery_required is False
    assert exc_info.value.committed is False
    assert _tree_state(storage) == before
    _assert_no_transaction(storage)


def test_initial_journal_write_failure_preserves_original_tree_and_removes_staging(
    storage, monkeypatch,
):
    before = _tree_state(storage)

    def fail_initial_journal(_base, journal):
        assert journal["state"] == "applying"
        raise OSError("initial applying journal could not be persisted")

    monkeypatch.setattr(restore, "_write_journal", fail_initial_journal)
    with store.workspace_write_lock(storage, operation="pull"):
        with pytest.raises(restore.PullApplyError) as exc_info:
            restore.install_snapshot(storage, _snapshot(2), _hub(2))
    assert exc_info.value.committed is False
    assert exc_info.value.recovery_required is False
    assert _tree_state(storage) == before
    _assert_no_transaction(storage)


def test_hub_serialization_failure_preserves_original_tree_and_removes_staging(storage):
    before = _tree_state(storage)
    config = dict(_hub(2), not_json_serializable=object())
    with store.workspace_write_lock(storage, operation="pull"):
        with pytest.raises(restore.PullApplyError) as exc_info:
            restore.install_snapshot(storage, _snapshot(2), config)
    assert exc_info.value.committed is False
    assert exc_info.value.recovery_required is False
    assert _tree_state(storage) == before
    _assert_no_transaction(storage)


@pytest.mark.parametrize("after_step", range(1, 9))
def test_next_lock_rolls_back_interrupted_applying_transaction(
    storage, monkeypatch, after_step,
):
    before = _tree_state(storage)
    _interrupted_install(storage, monkeypatch, after_step=after_step)
    lock_before = (storage / ".write.lock").stat()

    with store.workspace_write_lock(storage, operation="inspect"):
        # Recovery must complete before a lock caller sees any storage data.
        assert _tree_state(storage) == before
        _assert_no_transaction(storage)
        lock_after = (storage / ".write.lock").stat()
        assert (lock_after.st_dev, lock_after.st_ino) == (
            lock_before.st_dev, lock_before.st_ino,
        )


def test_failed_rollback_requires_recovery_and_next_lock_finishes_it(storage, monkeypatch):
    before = _tree_state(storage)
    real_replace = restore._replace_component

    def fail_install_and_rollback(source, destination):
        source = Path(source)
        if source.parent.name == "new":
            raise OSError("injected install failure")
        if source.parent.name == "backup":
            raise OSError("injected rollback failure")
        return real_replace(source, destination)

    with monkeypatch.context() as patch:
        patch.setattr(restore, "_replace_component", fail_install_and_rollback)
        with store.workspace_write_lock(storage, operation="pull"):
            with pytest.raises(restore.PullApplyError) as exc_info:
                restore.install_snapshot(storage, _snapshot(2), _hub(2))

    assert exc_info.value.recovery_required is True
    assert exc_info.value.committed is False
    assert (storage / JOURNAL).is_file()
    with store.workspace_write_lock(storage, operation="inspect"):
        assert _tree_state(storage) == before
        _assert_no_transaction(storage)


@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
def test_committed_cleanup_failure_recovers_without_undoing_install(
    storage, monkeypatch, failure,
):
    def fail_cleanup(_base, journal):
        assert journal["state"] == "committed"
        raise failure("injected cleanup interruption")

    with monkeypatch.context() as patch:
        patch.setattr(restore, "_cleanup_transaction", fail_cleanup)
        with store.workspace_write_lock(storage, operation="pull"):
            if failure is OSError:
                with pytest.raises(restore.PullApplyError) as exc_info:
                    restore.install_snapshot(storage, _snapshot(2), _hub(2))
                assert exc_info.value.committed is True
                assert exc_info.value.recovery_required is True
            else:
                with pytest.raises(KeyboardInterrupt):
                    restore.install_snapshot(storage, _snapshot(2), _hub(2))

    journal = json.loads((storage / JOURNAL).read_text(encoding="utf-8"))
    assert journal["state"] == "committed"
    _assert_installed(storage, _snapshot(2), _hub(2))
    with store.workspace_write_lock(storage, operation="inspect"):
        _assert_installed(storage, _snapshot(2), _hub(2))
        _assert_no_transaction(storage)


def test_single_cleanup_failure_is_recovered_but_reports_committed(storage, monkeypatch):
    real_cleanup = restore._cleanup_transaction
    calls = 0

    def fail_once(base, journal):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("one-time cleanup failure")
        return real_cleanup(base, journal)

    monkeypatch.setattr(restore, "_cleanup_transaction", fail_once)
    with store.workspace_write_lock(storage, operation="pull"):
        with pytest.raises(restore.PullApplyError) as exc_info:
            restore.install_snapshot(storage, _snapshot(2), _hub(2))

    assert calls == 2
    assert exc_info.value.committed is True
    assert exc_info.value.recovery_required is False
    _assert_installed(storage, _snapshot(2), _hub(2))
    _assert_no_transaction(storage)


def test_committed_recovery_cleans_partially_removed_backup_without_rollback(
    storage, monkeypatch,
):
    def remove_backup_file_then_interrupt(base, journal):
        assert journal["state"] == "committed"
        backup = base / journal["txn_dir"] / "backup"
        (backup / "intents" / "intent-001.json").unlink()
        raise KeyboardInterrupt("backup cleanup was interrupted")

    with monkeypatch.context() as patch:
        patch.setattr(restore, "_cleanup_transaction", remove_backup_file_then_interrupt)
        with store.workspace_write_lock(storage, operation="pull"):
            with pytest.raises(KeyboardInterrupt):
                restore.install_snapshot(storage, _snapshot(2), _hub(2))

    with store.workspace_write_lock(storage, operation="inspect"):
        _assert_installed(storage, _snapshot(2), _hub(2))
        _assert_no_transaction(storage)


def test_ensure_init_recovers_before_requiring_missing_live_object_directory(
    storage, monkeypatch,
):
    before = _tree_state(storage)
    _interrupted_install(storage, monkeypatch, after_step=1)
    assert not (storage / "intents").exists()
    monkeypatch.setattr(store, "git_root", lambda: storage.parent)
    monkeypatch.chdir(storage.parent)

    assert store.ensure_init() == storage
    assert _tree_state(storage) == before
    _assert_no_transaction(storage)


def test_install_when_original_hub_config_is_absent(storage):
    (storage / "hub.json").unlink()
    with store.workspace_write_lock(storage, operation="pull"):
        restore.install_snapshot(storage, _snapshot(2), _hub(2))
    _assert_installed(storage, _snapshot(2), _hub(2))
    _assert_no_transaction(storage)


def test_failure_with_no_original_hub_restores_absence(storage, monkeypatch):
    (storage / "hub.json").unlink()
    before = _tree_state(storage)
    real_write = restore._write_journal

    def fail_commit(base, journal):
        if journal["state"] == "committed":
            raise OSError("commit failed after installing initially absent hub")
        return real_write(base, journal)

    monkeypatch.setattr(restore, "_write_journal", fail_commit)
    with store.workspace_write_lock(storage, operation="pull"):
        with pytest.raises(restore.PullApplyError) as exc_info:
            restore.install_snapshot(storage, _snapshot(2), _hub(2))
    assert exc_info.value.committed is False
    assert exc_info.value.recovery_required is False
    assert _tree_state(storage) == before
    assert not (storage / "hub.json").exists()
    _assert_no_transaction(storage)


@pytest.mark.parametrize("after_step", range(1, 8))
def test_interrupted_install_with_no_original_hub_restores_absence(
    storage, monkeypatch, after_step,
):
    (storage / "hub.json").unlink()
    before = _tree_state(storage)
    _interrupted_install(storage, monkeypatch, after_step=after_step)
    with store.workspace_write_lock(storage, operation="inspect"):
        assert _tree_state(storage) == before
        assert not (storage / "hub.json").exists()
        _assert_no_transaction(storage)


@pytest.mark.parametrize("bad_snapshot", [
    None, [],
    {"intents": [], "snaps": []},
    {"intents": {}, "snaps": [], "decisions": []},
    {"intents": [None], "snaps": [], "decisions": []},
])
def test_invalid_snapshot_container_is_rejected_before_staging(storage, bad_snapshot):
    before = _tree_state(storage)
    with store.workspace_write_lock(storage, operation="pull"):
        with pytest.raises((restore.PullApplyError, store.StorageSecurityError)):
            restore.install_snapshot(storage, bad_snapshot, _hub(2))
    assert _tree_state(storage) == before
    _assert_no_transaction(storage)


@pytest.mark.parametrize(("subdir", "field", "value"), [
    ("intents", "id", "../../victim"),
    ("intents", "id", "intent-١٢٣"),
    ("intents", "object", "snap"),
    ("intents", "created_at", None),
    ("intents", "status", "unknown"),
    ("intents", "snap_ids", "snap-002"),
    ("intents", "decision_ids", ["../../victim"]),
    ("snaps", "intent_id", "../../victim"),
    ("decisions", "status", "unknown"),
    ("decisions", "intent_ids", ["snap-002"]),
])
def test_invalid_remote_object_is_rejected_before_staging(
    storage, subdir, field, value,
):
    before = _tree_state(storage)
    snapshot = _snapshot(2)
    snapshot[subdir][0][field] = value
    with store.workspace_write_lock(storage, operation="pull"):
        with pytest.raises((restore.PullApplyError, store.StorageSecurityError)):
            restore.install_snapshot(storage, snapshot, _hub(2))
    assert _tree_state(storage) == before
    _assert_no_transaction(storage)


def test_duplicate_remote_ids_are_rejected_before_staging(storage):
    before = _tree_state(storage)
    snapshot = _snapshot(2)
    snapshot["intents"].append(copy.deepcopy(snapshot["intents"][0]))
    with store.workspace_write_lock(storage, operation="pull"):
        with pytest.raises((restore.PullApplyError, store.StorageSecurityError)):
            restore.install_snapshot(storage, snapshot, _hub(2))
    assert _tree_state(storage) == before
    _assert_no_transaction(storage)


@pytest.mark.parametrize("raw", [b'{"state":', b"[]", b"{}", b'"not an object"'])
def test_malformed_journal_blocks_lock_caller_without_mutation(storage, raw):
    (storage / JOURNAL).write_bytes(raw)
    before = _tree_state(storage)
    with pytest.raises((restore.PullApplyError, store.StorageSecurityError)):
        with store.workspace_write_lock(storage, operation="inspect"):
            pytest.fail("unsafe recovery must not yield the lock")
    assert _tree_state(storage) == before


@pytest.mark.parametrize("state", [[], {}, False, 42, "unknown"])
def test_invalid_journal_state_is_a_structured_failure_not_type_error(
    storage, monkeypatch, state,
):
    journal = _interrupted_install(storage, monkeypatch)
    journal["state"] = state
    _write_json(storage / JOURNAL, journal)
    before = _tree_state(storage)
    with pytest.raises(restore.PullApplyError) as exc_info:
        with store.workspace_write_lock(storage, operation="inspect"):
            pytest.fail("malformed recovery must not yield the lock")
    assert exc_info.value.recovery_required is True
    assert _tree_state(storage) == before


@pytest.mark.parametrize("component", ["live", "backup"])
def test_modified_applying_component_blocks_recovery_before_any_mutation(
    storage, monkeypatch, component,
):
    journal = _interrupted_install(storage, monkeypatch, after_step=2)
    if component == "backup":
        path = storage / journal["txn_dir"] / "backup" / "intents" / "intent-001.json"
    else:
        path = storage / "intents" / "intent-002.json"
    path.write_bytes(path.read_bytes() + b"\nchanged outside transaction")
    before = _tree_state(storage)
    with pytest.raises(restore.PullApplyError) as exc_info:
        with store.workspace_write_lock(storage, operation="inspect"):
            pytest.fail("unverified recovery must not yield the lock")
    assert exc_info.value.recovery_required is True
    assert _tree_state(storage) == before


@pytest.mark.parametrize("txn_dir", [
    "../outside", "/tmp/pull-escape", ".", "", ".pull-not-hex",
    ".pull-" + "a" * 32 + "/nested", None,
])
def test_journal_transaction_path_cannot_escape_or_select_arbitrary_directory(
    storage, monkeypatch, tmp_path, txn_dir,
):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "sentinel").write_bytes(b"must not be touched")
    journal = _interrupted_install(storage, monkeypatch)
    journal["txn_dir"] = txn_dir
    _write_json(storage / JOURNAL, journal)
    before = _tree_state(storage)
    outside_before = _tree_state(outside)
    with pytest.raises((restore.PullApplyError, store.StorageSecurityError)):
        with store.workspace_write_lock(storage, operation="inspect"):
            pytest.fail("unsafe recovery must not yield the lock")
    assert _tree_state(storage) == before
    assert _tree_state(outside) == outside_before


def test_symlinked_journal_is_rejected_without_touching_target(storage, tmp_path):
    target = tmp_path / "outside-journal.json"
    target.write_bytes(b"outside journal must remain unchanged")
    _symlink_or_skip(storage / JOURNAL, target)
    before = _tree_state(storage)
    with pytest.raises((restore.PullApplyError, store.StorageSecurityError)):
        with store.workspace_write_lock(storage, operation="inspect"):
            pytest.fail("unsafe recovery must not yield the lock")
    assert _tree_state(storage) == before
    assert target.read_bytes() == b"outside journal must remain unchanged"


@pytest.mark.parametrize("component", ["transaction", "new", "backup"])
def test_symlinked_transaction_component_blocks_recovery_without_following_link(
    storage, monkeypatch, tmp_path, component,
):
    journal = _interrupted_install(storage, monkeypatch)
    transaction = storage / journal["txn_dir"]
    selected = transaction if component == "transaction" else transaction / component
    outside = tmp_path / f"outside-{component}"
    selected.rename(outside)
    _symlink_or_skip(selected, outside, directory=True)
    before = _tree_state(storage)
    outside_before = _tree_state(outside)
    with pytest.raises((restore.PullApplyError, store.StorageSecurityError)):
        with store.workspace_write_lock(storage, operation="inspect"):
            pytest.fail("unsafe recovery must not yield the lock")
    assert _tree_state(storage) == before
    assert _tree_state(outside) == outside_before


@pytest.mark.parametrize("entry_type", ["file", "directory"])
def test_unrelated_transaction_root_entry_blocks_recovery_without_deleting_it(
    storage, monkeypatch, entry_type,
):
    journal = _interrupted_install(storage, monkeypatch)
    unexpected = storage / journal["txn_dir"] / "unrelated-user-data"
    if entry_type == "directory":
        unexpected.mkdir()
        (unexpected / "sentinel").write_bytes(b"must not be removed")
    else:
        unexpected.write_bytes(b"must not be removed")
    before = _tree_state(storage)
    with pytest.raises(restore.PullApplyError) as exc_info:
        with store.workspace_write_lock(storage, operation="inspect"):
            pytest.fail("unknown transaction paths must not be cleaned automatically")
    assert exc_info.value.recovery_required is True
    assert _tree_state(storage) == before
