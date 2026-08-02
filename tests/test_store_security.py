"""Security boundaries for local object IDs and .intent storage paths."""

import json
from pathlib import Path

import pytest

from intent_cli import store


@pytest.fixture
def storage(tmp_path):
    base = tmp_path / ".intent"
    base.mkdir()
    for subdir in store.SUBDIRS.values():
        (base / subdir).mkdir()
    return base


def _object(object_type, obj_id):
    obj = {
        "id": obj_id,
        "object": object_type,
        "created_at": "2026-08-02T00:00:00+00:00",
        "what": "security fixture",
        "why": "exercise the storage boundary",
        "origin": "pytest",
    }
    if object_type == "intent":
        obj.update({
            "status": "active",
            "snap_ids": [],
            "decision_ids": [],
        })
    elif object_type == "snap":
        obj["intent_id"] = "intent-001"
    elif object_type == "decision":
        obj.update({"status": "active", "intent_ids": []})
    return obj


def _write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def _symlink_or_skip(link, target, *, target_is_directory=False):
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlinks are unavailable in this environment: {exc}")


@pytest.mark.parametrize(
    ("object_type", "obj_id"),
    [
        ("intent", "intent-001"),
        ("snap", "snap-1000"),
        ("decision", "decision-9"),
    ],
)
def test_validate_object_id_accepts_type_specific_ascii_ids(object_type, obj_id):
    assert store.validate_object_id(object_type, obj_id) == obj_id


@pytest.mark.parametrize(
    "obj_id",
    [
        "",
        "intent-",
        "snap-001",
        "intent-001.json",
        "intent-001/extra",
        "intent-001\\extra",
        "../victim",
        "../../victim",
        "/tmp/victim",
        r"C:\victim",
        r"\\server\share\victim",
        " intent-001",
        "intent-001 ",
        "intent-001:stream",
        "intent-١٢٣",
        "intent-\x00",
        None,
        1,
    ],
)
def test_validate_object_id_rejects_noncanonical_or_path_ids(obj_id):
    with pytest.raises(store.InvalidObjectIdError):
        store.validate_object_id("intent", obj_id)


@pytest.mark.parametrize("object_type", ["intent", "snap", "decision"])
def test_valid_object_round_trip_stays_in_type_directory(storage, object_type):
    obj_id = f"{object_type}-001"
    obj = _object(object_type, obj_id)

    store.create_object(storage, object_type, obj_id, obj)

    assert store.read_object(storage, object_type, obj_id) == obj
    assert (storage / store.SUBDIRS[object_type] / f"{obj_id}.json").is_file()


def test_read_and_write_reject_out_of_boundary_ids_before_io(storage, tmp_path):
    victim = tmp_path / "victim.json"
    original = json.dumps(_object("intent", "intent-001"))
    victim.write_text(original, encoding="utf-8")

    for bad_id in ("../../victim", str(victim.with_suffix(""))):
        with pytest.raises(store.InvalidObjectIdError):
            store.read_object(storage, "intent", bad_id)
        with pytest.raises(store.InvalidObjectIdError):
            store.create_object(storage, "intent", bad_id, _object("intent", bad_id))

    assert victim.read_text(encoding="utf-8") == original


@pytest.mark.parametrize(
    ("filename", "data", "message"),
    [
        (
            "intent-001.json",
            _object("intent", "../../victim"),
            "field 'id'",
        ),
        (
            "intent-not-ascii-١.json",
            _object("intent", "intent-not-ascii-١"),
            "filename",
        ),
    ],
)
def test_list_objects_rejects_filename_id_or_object_mismatch(
    storage, filename, data, message
):
    path = storage / "intents" / filename
    _write_json(path, data)

    with pytest.raises(store.StoredObjectIntegrityError, match=message):
        store.list_objects(storage, "intent")


def test_object_type_mismatch_remains_available_to_graph_diagnostics(storage):
    path = storage / "intents" / "intent-001.json"
    obj = _object("intent", "intent-001")
    obj["object"] = "snap"
    _write_json(path, obj)

    assert store.list_objects(storage, "intent")[0]["object"] == "snap"
    report = store.validate_graph(store.load_graph_once(storage))

    assert any(
        issue["code"] == "OBJECT_TYPE_MISMATCH"
        and issue["object"] == "intent"
        and issue["id"] == "intent-001"
        for issue in report["issues"]
    )


def test_read_object_rejects_identity_mismatch(storage):
    path = storage / "intents" / "intent-001.json"
    _write_json(path, _object("intent", "intent-999"))

    with pytest.raises(store.StoredObjectIntegrityError, match="field 'id'"):
        store.read_object(storage, "intent", "intent-001")


def test_create_object_rejects_identity_mismatch_before_creating_file(storage):
    path = storage / "intents" / "intent-001.json"

    with pytest.raises(store.StoredObjectIntegrityError, match="field 'id'"):
        store.create_object(
            storage,
            "intent",
            "intent-001",
            _object("intent", "../../victim"),
        )

    assert not path.exists()


def test_poisoned_stored_id_is_never_used_as_a_write_path(storage, tmp_path):
    victim = tmp_path / "victim.json"
    victim.write_text("unchanged", encoding="utf-8")
    poisoned = _object("intent", "../../victim")
    _write_json(storage / "intents" / "intent-001.json", poisoned)

    with pytest.raises(store.StoredObjectIntegrityError):
        store.list_objects(storage, "intent")

    assert victim.read_text(encoding="utf-8") == "unchanged"


def test_rejects_intent_root_symlink(tmp_path):
    outside = tmp_path / "outside-store"
    outside.mkdir()
    for subdir in store.SUBDIRS.values():
        (outside / subdir).mkdir()
    linked_base = tmp_path / ".intent"
    _symlink_or_skip(linked_base, outside, target_is_directory=True)

    with pytest.raises(store.UnsafeStoragePathError, match="must not be a symlink"):
        store.read_object(linked_base, "intent", "intent-001")


@pytest.mark.parametrize("object_type", ["intent", "snap", "decision"])
def test_rejects_object_directory_symlink(storage, tmp_path, object_type):
    subdir = storage / store.SUBDIRS[object_type]
    subdir.rmdir()
    outside = tmp_path / f"outside-{object_type}"
    outside.mkdir()
    _symlink_or_skip(subdir, outside, target_is_directory=True)

    with pytest.raises(store.UnsafeStoragePathError, match="must not be a symlink"):
        store.create_object(
            storage,
            object_type,
            f"{object_type}-001",
            _object(object_type, f"{object_type}-001"),
        )

    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("object_type", ["intent", "snap", "decision"])
def test_rejects_object_file_symlink_without_reading_or_replacing_target(
    storage, tmp_path, object_type
):
    obj_id = f"{object_type}-001"
    external = tmp_path / f"external-{object_type}.json"
    original = json.dumps(_object(object_type, obj_id))
    external.write_text(original, encoding="utf-8")
    link = storage / store.SUBDIRS[object_type] / f"{obj_id}.json"
    _symlink_or_skip(link, external)

    with pytest.raises(store.UnsafeStoragePathError, match="must not be a symlink"):
        store.read_object(storage, object_type, obj_id)
    with pytest.raises(store.UnsafeStoragePathError, match="must not be a symlink"):
        store.list_objects(storage, object_type)
    with pytest.raises(store.UnsafeStoragePathError, match="must not be a symlink"):
        store.create_object(storage, object_type, obj_id, _object(object_type, obj_id))

    assert link.is_symlink()
    assert external.read_text(encoding="utf-8") == original


def test_workspace_lock_rejects_symlink(storage, tmp_path):
    external = tmp_path / "external-lock"
    external.write_bytes(b"")
    _symlink_or_skip(storage / ".write.lock", external)

    with pytest.raises(store.UnsafeStoragePathError, match="must not be a symlink"):
        with store.workspace_write_lock(storage):
            pass

    assert external.read_bytes() == b""


def test_graph_loads_each_type_once_and_validation_is_in_memory(
    storage, monkeypatch
):
    calls = []
    real_scan = store._scan_object_type

    def record_scan(base, object_type, *, tolerant):
        calls.append((object_type, tolerant))
        return real_scan(base, object_type, tolerant=tolerant)

    monkeypatch.setattr(store, "_scan_object_type", record_scan)
    graph = store.load_graph_once(storage)

    assert calls == [
        ("intent", False),
        ("snap", False),
        ("decision", False),
    ]

    def fail_scan(*_args, **_kwargs):
        raise AssertionError("validate_graph must not read storage")

    monkeypatch.setattr(store, "_scan_object_type", fail_scan)
    assert store.validate_graph(graph) == {"healthy": True, "issues": []}
