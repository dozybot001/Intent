"""Validated, canonical semantic snapshots; no filesystem or network mutations."""

import hashlib
import json
from pathlib import Path

from intent_cli.store import (
    RELATION_FIELDS, SUBDIRS, StorageSecurityError, _validate_object_schema,
    validate_graph, validate_object_id,
)


class SnapshotError(ValueError):
    pass


def validate_snapshot(snapshot):
    """Reject malformed objects and duplicate identities before building a graph."""
    if not isinstance(snapshot, dict) or set(snapshot) != set(SUBDIRS.values()):
        raise SnapshotError("Snapshot must contain intents, snaps, and decisions arrays.")
    try:
        json.dumps(snapshot, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise SnapshotError("Snapshot must be finite, UTF-8 encodable JSON.") from exc
    graph = {}
    for kind, collection in SUBDIRS.items():
        objects = snapshot[collection]
        if not isinstance(objects, list):
            raise SnapshotError(f"Snapshot {collection} must be an array.")
        graph[kind] = {}
        for obj in objects:
            if not isinstance(obj, dict):
                raise SnapshotError(f"Each {collection} entry must be an object.")
            obj_id = obj.get("id")
            try:
                validate_object_id(kind, obj_id)
                _validate_object_schema(
                    obj, Path("snapshot") / collection / f"{obj_id}.json",
                    kind, obj_id, require_object_type=True,
                )
            except StorageSecurityError as exc:
                raise SnapshotError(str(exc)) from exc
            if obj_id in graph[kind]:
                raise SnapshotError(f"Duplicate {kind} ID: {obj_id}.")
            for field in RELATION_FIELDS[kind]:
                if len(obj[field]) != len(set(obj[field])):
                    raise SnapshotError(f"Duplicate references in {obj_id}.{field}.")
            graph[kind][obj_id] = obj
    result = validate_graph(graph)
    if not result["healthy"]:
        raise SnapshotError(result["issues"][0]["message"])
    return snapshot


def snapshot_sha256(snapshot):
    """Ignore collection order, but preserve relation order and all object fields."""
    canonical = {
        collection: sorted(snapshot[collection], key=lambda obj: obj["id"])
        for collection in SUBDIRS.values()
    }
    raw = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def require_fast_forward(before, after):
    """Reject deleted/replaced history and reverse terminal lifecycle transitions."""
    mutable = {
        "intents": {"status", "reason", "snap_ids", "decision_ids"},
        "decisions": {"status", "reason", "intent_ids"},
        "snaps": set(),
    }
    for collection, allowed in mutable.items():
        new_by_id = {obj["id"]: obj for obj in after[collection]}
        for old in before[collection]:
            new = new_by_id.get(old["id"])
            if new is None:
                raise SnapshotError(f"Remote history removed {old['id']}.")
            if {k: v for k, v in old.items() if k not in allowed} != {
                k: v for k, v in new.items() if k not in allowed
            }:
                raise SnapshotError(f"Remote history rewrote {old['id']}.")
            for relation in ("snap_ids", "decision_ids", "intent_ids"):
                if relation in old and new[relation][:len(old[relation])] != old[relation]:
                    raise SnapshotError(f"Remote history rewrote {old['id']}.{relation}.")
            if old.get("status") in {"done", "cancelled", "deprecated"} and new != old:
                raise SnapshotError(f"Remote history changed terminal object {old['id']}.")
            if "reason" in old and new.get("reason") != old["reason"]:
                raise SnapshotError(f"Remote history rewrote {old['id']}.reason.")
