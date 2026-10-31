"""What the repository's files are, apart from where they live: digests, tree shapes, revision shapes.

The CLI and IntHub both read and write this format, so nothing here touches a disk.
"""

import hashlib
import heapq
import json
import math
from datetime import datetime

from intent_cli.repo_refs import DIGEST
from intent_cli.store_schema import OBJECT_ID_PATTERNS

TREE_DEPTH = 2


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _refuse_constant(name):
    raise ValueError(f"{name} is not JSON")


def _finite(text):
    value = float(text)
    if math.isinf(value):
        raise ValueError(f"{text} is too large")
    return value


def strict_json(raw):
    """Parse JSON as the standard defines it, without Python's NaN and Infinity."""
    return json.loads(raw, parse_constant=_refuse_constant, parse_float=_finite)


def _is_object_id(obj_id):
    pattern = OBJECT_ID_PATTERNS.get(obj_id.split("-", 1)[0]) if isinstance(obj_id, str) else None
    return pattern is not None and pattern.fullmatch(obj_id) is not None


def valid_revision(data):
    parents = data.get("parents") if isinstance(data, dict) else None
    tree = data.get("tree") if isinstance(data, dict) else None
    return (isinstance(parents, list) and isinstance(tree, str) and DIGEST.fullmatch(tree) is not None
            and all(isinstance(item, str) and DIGEST.fullmatch(item) for item in parents))


def valid_tree_node(node, depth):
    return (isinstance(node, dict) and all(isinstance(item, str) and DIGEST.fullmatch(item) for item in node.values())
            and (depth < TREE_DEPTH or all(_is_object_id(obj_id) for obj_id in node)))


def tree_digest(entries, store, depth=0):
    """Pass {id: version digest} to store() as TREE_DEPTH levels of buckets. One changed object rewrites only its path."""
    if depth == TREE_DEPTH:
        return store(entries)
    buckets = {}
    for obj_id, version in entries.items():
        buckets.setdefault(_digest(obj_id.encode("utf-8"))[depth], {})[obj_id] = version
    return store({key: tree_digest(bucket, store, depth + 1) for key, bucket in buckets.items()})


def canonical_tree(entries):
    """The tree any honest writer would make of these entries."""
    return tree_digest(entries, lambda data: _digest(_canonical(data)))


def _tree_changes(before, after):
    changes = [{"id": obj_id, "action": "added"} for obj_id in sorted(after.keys() - before.keys())]
    changes += [{"id": obj_id, "action": "changed"} for obj_id in sorted(after.keys() & before.keys())
                if after[obj_id] != before[obj_id]]
    changes += [{"id": obj_id, "action": "removed"} for obj_id in sorted(before.keys() - after.keys())]
    return changes


def _timestamp(revision):
    try:
        return datetime.fromisoformat(revision["time"]).timestamp()
    except (KeyError, TypeError, ValueError):
        return 0.0


def topological(revisions):
    """A {digest: revision} closed under parents, as a list: children first, then newest first."""
    waiting = dict.fromkeys(revisions, 0)
    for revision in revisions.values():
        for parent in set(revision["parents"]):
            waiting[parent] += 1
    entry = lambda digest: (-_timestamp(revisions[digest]), digest)
    ready = [entry(digest) for digest, count in waiting.items() if count == 0]
    heapq.heapify(ready)
    ordered = []
    while ready:
        _when, digest = heapq.heappop(ready)
        ordered.append((digest, revisions[digest]))
        for parent in set(revisions[digest]["parents"]):
            waiting[parent] -= 1
            if waiting[parent] == 0:
                heapq.heappush(ready, entry(parent))
    return ordered
