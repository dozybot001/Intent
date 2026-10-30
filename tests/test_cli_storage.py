import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from intent_cli import store as intent_store

from tests.cli_support import _run, _stored_intent, _stored_snap, workspace


class TestCliStorageSecurity:
    @pytest.mark.parametrize(
        ("args", "object_type", "status"),
        [
            (("intent", "activate", "../../victim"), "intent", "suspend"),
            (("intent", "suspend", "../../victim"), "intent", "active"),
            (("intent", "done", "../../victim"), "intent", "active"),
            (("intent", "cancel", "../../victim"), "intent", "active"),
            (("snap", "create", "S", "--intent", "../../victim"), "intent", "active"),
            (("decision", "deprecate", "../../victim"), "decision", "active"),
            (("inspect", "--intent", "../../victim"), "intent", "active"),
        ],
    )
    def test_explicit_traversal_ids_return_json_without_touching_target(
        self, workspace, args, object_type, status
    ):
        victim = workspace / "victim.json"
        payload = {
            "id": "../../victim",
            "object": object_type,
            "status": status,
            "what": "outside target",
            "why": "must remain unchanged",
            "snap_ids": [],
            "decision_ids": [],
            "intent_ids": [],
        }
        original = json.dumps(payload, indent=2)
        victim.write_text(original, encoding="utf-8")

        r = _run(workspace, *args)

        assert r["ok"] is False
        assert r["error"]["code"] == "INVALID_OBJECT_ID"
        assert victim.read_text(encoding="utf-8") == original
        assert list((workspace / ".intent" / "snaps").glob("snap-*.json")) == []

    def test_absolute_id_cannot_read_or_modify_external_object(self, workspace):
        target_without_suffix = workspace.parent / "absolute-decision-target"
        victim = Path(f"{target_without_suffix}.json")
        payload = {
            "id": str(target_without_suffix),
            "object": "decision",
            "status": "active",
            "what": "outside target",
            "why": "must remain unchanged",
            "intent_ids": [],
        }
        original = json.dumps(payload, indent=2)
        victim.write_text(original, encoding="utf-8")

        r = _run(
            workspace,
            "decision", "deprecate", str(target_without_suffix),
        )

        assert r["error"]["code"] == "INVALID_OBJECT_ID"
        assert victim.read_text(encoding="utf-8") == original

    def test_poisoned_stored_id_stops_before_partial_write(self, workspace):
        _run(workspace, "intent", "create", "Goal")
        intent_file = workspace / ".intent" / "intents" / "intent-001.json"
        payload = json.loads(intent_file.read_text(encoding="utf-8"))
        payload["id"] = "../../victim"
        intent_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        r = _run(workspace, "decision", "create", "Rule")

        assert r["ok"] is False
        assert r["error"]["code"] == "STORAGE_INTEGRITY_ERROR"
        assert list((workspace / ".intent" / "decisions").glob("decision-*.json")) == []

    def test_symlinked_intent_root_returns_structured_error(self, workspace):
        storage = workspace / ".intent"
        real_storage = workspace / ".intent-real"
        storage.rename(real_storage)
        try:
            storage.symlink_to(real_storage, target_is_directory=True)
        except (NotImplementedError, OSError) as exc:
            pytest.skip(f"symlinks are unavailable in this environment: {exc}")

        r = _run(workspace, "inspect")

        assert r["ok"] is False
        assert r["error"]["code"] == "UNSAFE_STORAGE"


class TestAtomicWrites:
    def test_create_object_links_complete_temp_without_replacing(
        self, workspace, monkeypatch
    ):
        base = workspace / ".intent"
        destination = base / "intents" / "intent-001.json"
        payload = _stored_intent()
        calls = []
        real_link = intent_store.os.link

        def record_link(source, target):
            source_path = Path(source)
            target_path = Path(target)
            calls.append((source_path, target_path))
            assert source_path.parent == target_path.parent
            assert json.loads(source_path.read_text()) == payload
            real_link(source, target)

        monkeypatch.setattr(intent_store.os, "link", record_link)
        intent_store.create_object(base, "intent", "intent-001", payload)

        assert calls and calls[0][1] == destination
        assert json.loads(destination.read_text()) == payload
        assert list(destination.parent.glob(f".{destination.name}.*.tmp")) == []

    def test_update_object_replaces_from_same_directory(self, workspace, monkeypatch):
        base = workspace / ".intent"
        destination = base / "intents" / "intent-001.json"
        original = _stored_intent()
        intent_store.create_object(base, "intent", "intent-001", original)
        updated = dict(original, status="suspend")
        calls = []
        real_replace = intent_store.os.replace

        def record_replace(source, target):
            source_path = Path(source)
            target_path = Path(target)
            calls.append((source_path, target_path))
            assert source_path.parent == target_path.parent
            assert json.loads(source_path.read_text()) == updated
            real_replace(source, target)

        monkeypatch.setattr(intent_store.os, "replace", record_replace)
        intent_store.update_object(base, "intent", "intent-001", updated)

        assert calls and calls[0][1] == destination
        assert json.loads(destination.read_text()) == updated
        assert list(destination.parent.glob(f".{destination.name}.*.tmp")) == []

    def test_update_object_cleans_temp_and_preserves_old_file_when_replace_fails(
        self, workspace, monkeypatch
    ):
        base = workspace / ".intent"
        destination = base / "intents" / "intent-001.json"
        original = _stored_intent()
        intent_store.create_object(base, "intent", "intent-001", original)
        updated = dict(original, status="suspend")

        def fail_replace(_source, _target):
            raise OSError("replace failed")

        monkeypatch.setattr(intent_store.os, "replace", fail_replace)
        with pytest.raises(OSError, match="replace failed"):
            intent_store.update_object(base, "intent", "intent-001", updated)

        assert json.loads(destination.read_text()) == original
        assert list(destination.parent.glob(f".{destination.name}.*.tmp")) == []

    def test_update_object_never_creates_a_missing_destination(self, workspace):
        base = workspace / ".intent"
        destination = base / "intents" / "intent-001.json"

        with pytest.raises(intent_store.StoredObjectWriteConflictError):
            intent_store.update_object(
                base, "intent", "intent-001", _stored_intent(),
            )

        assert not destination.exists()

    def test_create_cleans_temp_when_destination_appears_during_commit(
        self, workspace, monkeypatch
    ):
        base = workspace / ".intent"
        destination = base / "intents" / "intent-001.json"

        def destination_appeared(_source, _target):
            raise FileExistsError("racing creator won")

        monkeypatch.setattr(intent_store.os, "link", destination_appeared)
        with pytest.raises(intent_store.StoredObjectWriteConflictError):
            intent_store.create_object(
                base, "intent", "intent-001", _stored_intent(),
            )

        assert not destination.exists()
        assert list(destination.parent.glob(f".{destination.name}.*.tmp")) == []

    def test_write_hub_config_is_atomic(self, workspace, monkeypatch):
        base = workspace / ".intent"
        destination = base / "hub.json"
        real_replace = intent_store.os.replace
        calls = []

        def record_replace(source, target):
            calls.append((Path(source), Path(target)))
            real_replace(source, target)

        monkeypatch.setattr(intent_store.os, "replace", record_replace)
        intent_store.write_hub_config(base, {"api_base_url": "http://127.0.0.1"})

        assert calls and calls[0][0].parent == destination.parent
        assert calls[0][1] == destination
        assert json.loads(destination.read_text()) == {
            "api_base_url": "http://127.0.0.1"
        }

    def test_hub_status_normalizes_corrupt_hub_json(self, workspace):
        hub_config = workspace / ".intent" / "hub.json"
        hub_config.write_text('{"api_base_url":', encoding="utf-8")

        result = _run(workspace, "hub", "status")

        assert result["ok"] is False
        assert result["error"]["code"] == "STORAGE_PARSE_ERROR"
        assert result["error"]["details"]["path"] == str(hub_config)

    def test_hub_status_rejects_symlinked_hub_json(self, workspace, tmp_path):
        target = tmp_path / "outside-hub.json"
        target.write_text("{}", encoding="utf-8")
        hub_config = workspace / ".intent" / "hub.json"
        try:
            hub_config.symlink_to(target)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks are unavailable")

        result = _run(workspace, "hub", "status")

        assert result["ok"] is False
        assert result["error"]["code"] == "UNSAFE_STORAGE"
        assert json.loads(target.read_text(encoding="utf-8")) == {}

    def test_casefold_occupied_id_is_counted_and_never_overwritten(self, workspace):
        base = workspace / ".intent"
        occupied = base / "intents" / "intent-001.JSON"
        original = json.dumps(_stored_intent(), indent=2)
        occupied.write_text(original, encoding="utf-8")

        result = _run(workspace, "intent", "create", "New goal")

        assert result["ok"] is True
        assert result["result"]["id"] == "intent-002"
        assert occupied.read_text(encoding="utf-8") == original
        assert (base / "intents" / "intent-002.json").is_file()

    def test_create_rejects_casefold_destination_conflict_without_overwrite(
        self, workspace
    ):
        base = workspace / ".intent"
        occupied = base / "intents" / "intent-001.JSON"
        original = json.dumps(_stored_intent(), indent=2)
        occupied.write_text(original, encoding="utf-8")

        with pytest.raises(intent_store.StoredObjectWriteConflictError):
            intent_store.create_object(
                base, "intent", "intent-001", _stored_intent(),
            )

        assert occupied.read_text(encoding="utf-8") == original

    def test_update_rejects_noncanonical_casefold_destination(self, workspace):
        base = workspace / ".intent"
        occupied = base / "intents" / "intent-001.JSON"
        original = json.dumps(_stored_intent(), indent=2)
        occupied.write_text(original, encoding="utf-8")

        with pytest.raises(intent_store.StoredObjectWriteConflictError):
            intent_store.update_object(
                base,
                "intent",
                "intent-001",
                dict(_stored_intent(), status="suspend"),
            )

        assert occupied.read_text(encoding="utf-8") == original

    def test_workspace_write_lock_times_out_for_second_writer(self, workspace):
        base = workspace / ".intent"
        with intent_store.workspace_write_lock(base, operation="hub.link"):
            with pytest.raises(intent_store.WorkspaceBusyError) as exc_info:
                with intent_store.workspace_write_lock(base, timeout=0.01):
                    pass
            assert exc_info.value.owner["pid"] == os.getpid()
            assert exc_info.value.owner["operation"] == "hub.link"
            assert exc_info.value.owner["started_at"]

        assert (base / ".write.lock").read_bytes() == b""

    def test_inspect_waits_for_complete_multi_file_snapshot(self, workspace):
        base = workspace / ".intent"
        intent_store.create_object(
            base, "intent", "intent-001", _stored_intent(),
        )

        with ThreadPoolExecutor(max_workers=1) as pool:
            with intent_store.workspace_write_lock(base):
                intent_store.create_object(
                    base, "snap", "snap-001", _stored_snap(),
                )
                reader = pool.submit(_run, workspace, "inspect")
                threading.Event().wait(0.3)
                assert reader.done() is False

                intent = intent_store.read_object(
                    base, "intent", "intent-001",
                )
                intent["snap_ids"].append("snap-001")
                intent_store.update_object(
                    base, "intent", "intent-001", intent,
                )

            result = reader.result(timeout=5)

        assert result["ok"] is True
        assert result["active_intents"][0]["latest_snap"]["id"] == "snap-001"
        assert result["warnings"] == []

    def test_concurrent_cli_writers_receive_unique_ids(self, workspace):
        def create(index):
            return _run(workspace, "intent", "create", f"Goal {index}")

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(create, range(8)))

        assert all(result["ok"] is True for result in results)
        assert {result["result"]["id"] for result in results} == {
            f"intent-{index:03d}" for index in range(1, 9)
        }
        assert _run(workspace, "doctor")["result"]["healthy"] is True


def test_a_clone_of_a_committed_history_lacks_empty_folders(tmp_path):
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"), ITT_FORMAT="json")
    run = lambda *args: subprocess.run([sys.executable, "-m", "intent_cli", *args], cwd=tmp_path, env=env, capture_output=True, text=True)
    assert run("init", "--host", "codex").returncode == 0
    assert run("intent", "create", "Goal").returncode == 0
    (tmp_path / ".intent" / "decisions").rmdir()
    assert json.loads(run("inspect").stdout)["ok"] is True
    assert (tmp_path / ".intent" / "decisions").is_dir()


def test_help_is_a_command_too():
    result = subprocess.run([sys.executable, "-m", "intent_cli", "help"], capture_output=True, text=True,
                            env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src")))
    assert result.returncode == 0 and "usage" in result.stdout.lower()
