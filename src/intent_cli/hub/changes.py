"""What a revision changed in semantic terms: objects added, and what changed on existing ones."""

COLLECTIONS = ("intents", "snaps", "decisions")


def _relations(obj):
    active, removed = set(), set()
    for entry in obj.get("relations") or []:
        (removed if entry.get("removed_at") else active).add((entry["type"], entry["intent"]))
    return active, removed


def _changed_fields(before, after):
    """Status and relation changes. Link lists only grow as Snaps and Decisions are added, which are listed themselves."""
    changes = []
    if before.get("status") != after.get("status"):
        status = {"field": "status", "from": before.get("status"), "to": after.get("status")}
        if after.get("reason") and after.get("reason") != before.get("reason"):
            status["reason"] = after["reason"]
        changes.append(status)
    old_active, old_removed = _relations(before)
    new_active, new_removed = _relations(after)
    for kind, intent in sorted(new_active - old_active):
        changes.append({"field": "relation", "action": "added", "type": kind, "intent": intent})
    for kind, intent in sorted((new_removed - old_removed) & old_active):
        changes.append({"field": "relation", "action": "removed", "type": kind, "intent": intent})
    return changes


def semantic_changes(before, after):
    """Compare two snapshots; before is None for a project's first revision."""
    result = {}
    for collection in COLLECTIONS:
        known = {obj["id"]: obj for obj in (before or {}).get(collection, [])}
        added, changed = [], []
        for obj in after[collection]:
            if obj["id"] not in known:
                added.append(obj)
                continue
            fields = _changed_fields(known[obj["id"]], obj)
            if fields:
                changed.append({"object": obj, "changes": fields})
        result[collection] = {"added": added, "changed": changed}
    return result


def summarize(changes):
    """Counts for one line of the history list."""
    return {f"{collection}_{kind}": len(changes[collection][kind])
            for collection in COLLECTIONS for kind in ("added", "changed")}
