"""Semantic three-way merge: objects, not lines of text.

Snaps only grow and new IDs cannot collide, so most merges are a union. Only a
field both sides changed differently needs a person: that is a structured
conflict, listed with both values, never a text marker in a file.
"""

from copy import deepcopy

from intent_cli import relations as relation_rules
from intent_cli.store import RELATION_FIELDS

UNSET = object()


def _kind(obj_id):
    return obj_id.split("-", 1)[0]


def _relation_key(entry):
    return tuple(sorted((key, value) for key, value in entry.items() if key != "removed_at"))


def _merge_relations(ours, theirs):
    """Every record from both sides, and a withdrawal on either side wins."""
    merged = {}
    for entry in (*(ours or []), *(theirs or [])):
        key = _relation_key(entry)
        known = merged.setdefault(key, dict(entry))
        if "removed_at" in entry:
            known["removed_at"] = min(known.get("removed_at", entry["removed_at"]), entry["removed_at"])
    return sorted(merged.values(), key=lambda entry: (entry.get("created_at", ""), entry.get("intent", "")))


def _merge_object(obj_id, ancestor, ours, theirs):
    """Merge one object both sides changed. Returns (merged, conflicts)."""
    merged = deepcopy(ours)
    conflicts = []
    grow_only = RELATION_FIELDS[_kind(obj_id)]
    for field in sorted({*ours, *theirs}):
        before = (ancestor or {}).get(field, UNSET)
        mine, other = ours.get(field, UNSET), theirs.get(field, UNSET)
        if mine == other:
            continue
        if field in grow_only:
            merged[field] = [*(mine or []), *(value for value in (other or []) if value not in (mine or []))]
        elif field == "relations":
            merged[field] = _merge_relations(mine if mine is not UNSET else [], other if other is not UNSET else [])
        elif mine == before and other is not UNSET:
            merged[field] = deepcopy(other)
        elif other == before or other is UNSET:
            continue
        elif mine is UNSET:
            merged[field] = deepcopy(other)
        else:
            conflicts.append({"id": obj_id, "field": field, "ours": mine, "theirs": other,
                              "base": None if before is UNSET else before})
    return merged, conflicts


def _order_links(objects, merged_ids):
    """Links from both sides read oldest first, whichever side recorded them."""
    for obj_id in merged_ids:
        for field in RELATION_FIELDS[_kind(obj_id)]:
            links = objects[obj_id].get(field)
            if links:
                links.sort(key=lambda link: (objects.get(link, {}).get("created_at", ""), link))


def graph_conflicts(objects, ours, theirs):
    """A merge can leave an Intent with two parents, or close a cycle, though neither side did."""
    intents = {obj_id: obj for obj_id, obj in objects.items() if _kind(obj_id) == "intent"}
    conflicts = {}
    for obj_id, message in relation_rules.graph_issues(intents):
        conflicts.setdefault(obj_id, {
            "id": obj_id, "field": "relations", "message": message,
            "ours": ours.get(obj_id, {}).get("relations", []), "theirs": theirs.get(obj_id, {}).get("relations", []),
        })
    return list(conflicts.values())


def merge_objects(ancestor, ours, theirs):
    """Three-way merge of {id: object} maps. Returns (merged, conflicts)."""
    merged, combined, conflicts = {}, [], []
    for obj_id in sorted({*ours, *theirs}):
        mine, other, before = ours.get(obj_id), theirs.get(obj_id), ancestor.get(obj_id)
        if mine == other or other is None or other == before:
            merged[obj_id] = mine if mine is not None else other
        elif mine is None or mine == before:
            merged[obj_id] = other
        else:
            merged[obj_id], found = _merge_object(obj_id, before, mine, other)
            combined.append(obj_id)
            conflicts += found
    _order_links(merged, combined)
    known = {(item["id"], item["field"]) for item in conflicts}
    conflicts += [item for item in graph_conflicts(merged, ours, theirs) if (item["id"], item["field"]) not in known]
    return merged, conflicts


def possible_duplicates(objects):
    """Open Intents whose goal reads the same: two copies may have recorded one goal twice."""
    groups = {}
    for obj in objects.values():
        if obj.get("object") == "intent" and obj.get("status") in {"active", "suspend"}:
            groups.setdefault(" ".join(obj.get("what", "").casefold().split()), []).append(obj["id"])
    return [sorted(ids) for ids in groups.values() if len(ids) > 1]
