"""Validated, canonical semantic snapshots; no filesystem or network mutations."""

import hashlib
import json
from pathlib import Path

from intent_cli.store import (
    RELATION_FIELDS, SUBDIRS, StorageSecurityError, _validate_object_schema,
    validate_graph, validate_object_id,
)


TERMINAL_STATUSES = {"done", "cancelled", "deprecated"}


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


def _relation_key(entry):
    return json.dumps({key: value for key, value in entry.items() if key != "removed_at"}, sort_keys=True)


def _relations_grow_only(old, new):
    """Relation entries are never dropped, and one withdrawn stays withdrawn. A merge may interleave them."""
    after = {_relation_key(entry): entry for entry in new.get("relations") or []}
    for entry in old.get("relations") or []:
        current = after.get(_relation_key(entry))
        if current is None or ("removed_at" in entry and "removed_at" not in current):
            return False
    return True


def require_fast_forward(before, after):
    """Reject deleted or replaced history and reopened objects.

    Protocol 2 carries no revisions, so this compares content. A merge descends from what
    was pushed yet may reorder links and settle a conflict either way, so only losing
    something, or a finished object no longer being finished, counts as a rewrite.
    """
    mutable = {
        "intents": {"status", "reason", "snap_ids", "decision_ids", "relations"},
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
                if relation in old and not set(old[relation]) <= set(new[relation]):
                    raise SnapshotError(f"Remote history rewrote {old['id']}.{relation}.")
            if not _relations_grow_only(old, new):
                raise SnapshotError(f"Remote history rewrote {old['id']}.relations.")
            if old.get("status") in TERMINAL_STATUSES and new.get("status") not in TERMINAL_STATUSES:
                raise SnapshotError(f"Remote history changed terminal object {old['id']}.")
