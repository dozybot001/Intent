"""Put local work on top of newer remote history, like `git pull --rebase`.

Two copies that recorded in parallel can hold different objects under the same
ID. The remote's history stays exactly as it is; what only this copy recorded
takes the next free IDs, and references follow it.
"""

from copy import deepcopy

from intent_cli.hub.snapshots import SnapshotError, require_fast_forward, validate_snapshot
from intent_cli.store import RELATION_FIELDS, SUBDIRS

# What may differ between two copies of one object (see require_fast_forward).
MUTABLE = {"intent": {"status", "reason", "snap_ids", "decision_ids", "relations"},
           "decision": {"status", "reason", "intent_ids"}, "snap": set()}
TERMINAL = {"done", "cancelled", "deprecated"}


def _identity(kind, obj):
    return {key: value for key, value in obj.items() if key not in MUTABLE[kind]}


def _number(obj_id):
    return int(obj_id.split("-", 1)[1])


def _relation_key(entry):
    return {key: value for key, value in entry.items() if key != "removed_at"}


def _rewrite(obj, kind, renumbered):
    """Point an object that only this copy has at the new IDs."""
    rebased = deepcopy(obj)
    rebased["id"] = renumbered.get(obj["id"], obj["id"])
    for field in RELATION_FIELDS[kind]:
        rebased[field] = [renumbered.get(value, value) for value in obj[field]]
    for field in ("intent_id", "source_intent_id"):
        if field in rebased:
            rebased[field] = renumbered.get(rebased[field], rebased[field])
    for entry in rebased.get("relations") or []:
        entry["intent"] = renumbered.get(entry["intent"], entry["intent"])
    return rebased


def _merge(theirs, mine, kind, renumbered, conflicts):
    """The remote's object, plus what this copy added to it."""
    merged = deepcopy(theirs)
    for field in RELATION_FIELDS[kind]:
        merged[field] += [value for value in (renumbered.get(item, item) for item in mine[field]) if value not in merged[field]]
    if kind == "intent":
        local = _rewrite(mine, kind, renumbered).get("relations") or []
        known = merged.get("relations") or []
        for entry in known:
            twin = next((item for item in local if _relation_key(item) == _relation_key(entry)), None)
            if twin and "removed_at" in twin and "removed_at" not in entry:
                entry["removed_at"] = twin["removed_at"]
        added = [entry for entry in local if all(_relation_key(entry) != _relation_key(item) for item in known)]
        if added:
            merged["relations"] = known + added
    if mine.get("status") != theirs.get("status"):
        if theirs.get("status") not in TERMINAL and mine.get("status") in TERMINAL:
            merged["status"] = mine["status"]
            if "reason" in mine:
                merged["reason"] = mine["reason"]
        else:
            conflicts.append({"id": theirs["id"], "kept": theirs.get("status"), "local": mine.get("status")})
    return merged


def rebase_snapshot(local, remote):
    """Return (snapshot, renumbered, conflicts), or raise SnapshotError leaving nothing changed."""
    renumbered, shared = {}, {}
    for kind, collection in SUBDIRS.items():
        theirs = {obj["id"]: obj for obj in remote[collection]}
        fresh, shared[kind] = [], {}
        for obj in local[collection]:
            if obj["id"] in theirs and _identity(kind, obj) == _identity(kind, theirs[obj["id"]]):
                shared[kind][obj["id"]] = obj
            else:
                fresh.append(obj)
        last = max(map(_number, theirs), default=0)
        fresh.sort(key=lambda obj: (obj["created_at"], _number(obj["id"])))
        renumbered.update({obj["id"]: f"{kind}-{number:03d}" for number, obj in enumerate(fresh, last + 1)})
    conflicts = []
    merged = {}
    for kind, collection in SUBDIRS.items():
        kept = [_merge(obj, shared[kind][obj["id"]], kind, renumbered, conflicts) if obj["id"] in shared[kind] else deepcopy(obj)
                for obj in remote[collection]]
        added = [_rewrite(obj, kind, renumbered) for obj in local[collection] if obj["id"] in renumbered]
        merged[collection] = kept + sorted(added, key=lambda obj: _number(obj["id"]))
    try:
        validate_snapshot(merged)
        require_fast_forward(remote, merged)
    except SnapshotError as exc:
        raise SnapshotError(f"The two histories cannot be combined automatically: {exc}") from exc
    return merged, renumbered, conflicts
