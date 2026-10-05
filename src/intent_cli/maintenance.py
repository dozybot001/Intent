"""Project-local maintenance state and verifiable, non-semantic turn receipts."""

import hashlib
import json
import math
import re
import time
from datetime import datetime

from intent_cli import store


STATE_FILE = "maintenance.json"
MAX_STATE_BYTES = 4 * 1024 * 1024
MAX_TURNS = 32
TOKEN = re.compile(r"[0-9a-f]{64}", re.ASCII)


class MaintenanceError(ValueError):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def state_path(base):
    base, _ = store._safe_storage_root(base)
    path = base / STATE_FILE
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise store.UnsafeStoragePathError(path, "Maintenance state must be a regular file")
    return path


def read_state(base):
    path = state_path(base)
    if not path.exists():
        # Existing histories are not silently opted in by an upgrade.
        return {"version": 1, "enabled": False, "generation": 0, "turns": {}}
    try:
        if path.stat().st_size > MAX_STATE_BYTES:
            raise ValueError("state exceeds its size limit")
        state = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(state, dict) or type(state.get("version")) is not int
                or state["version"] != 1 or type(state.get("enabled")) is not bool
                or type(state.get("generation")) is not int or state["generation"] < 0
                or not isinstance(state.get("turns"), dict) or len(state["turns"]) > MAX_TURNS):
            raise ValueError("invalid maintenance schema")
        for key, entry in state["turns"].items():
            if (TOKEN.fullmatch(key) is None or not isinstance(entry, dict)
                    or not all(isinstance(entry.get(field), str) for field in ("root", "session_id", "turn_id"))
                    or type(entry.get("generation")) is not int or entry["generation"] < 0
                    or type(entry.get("started_at")) not in (int, float) or not math.isfinite(entry["started_at"])
                    or type(entry.get("retry_count")) is not int or entry["retry_count"] not in (0, 1)
                    or not isinstance(entry.get("aliases"), list)
                    or len(entry["aliases"]) > 1
                    or any(not isinstance(value, str) or not value or len(value) > 1024 for value in entry["aliases"])
                    or not isinstance(entry.get("baseline"), (dict, type(None)))
                    or not isinstance(entry.get("receipt"), (dict, type(None)))
                    or not isinstance(entry.get("context"), str)
                    or not isinstance(entry.get("entry_error"), (str, type(None)))
                    or not isinstance(entry.get("continuation_reason", ""), str)):
                raise ValueError("invalid turn entry")
            if type(entry.get("stop_checked", False)) is not bool:
                raise ValueError("invalid Stop observation")
            if entry["baseline"] is not None and any(not isinstance(digest, str) or TOKEN.fullmatch(digest) is None
                                                     for digest in entry["baseline"].values()):
                raise ValueError("invalid baseline fingerprints")
        return state
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        raise MaintenanceError("MAINTENANCE_STATE_INVALID", "Maintenance state is unreadable or invalid.") from exc


def write_state(base, state):
    turns = state["turns"]
    # Prefer retaining unfinished work; no raw prompts, transcripts or diffs.
    while len(turns) > MAX_TURNS:
        oldest = next((key for key, entry in turns.items() if entry.get("receipt")), next(iter(turns)))
        del turns[oldest]
    while len(json.dumps(state, ensure_ascii=True).encode("utf-8")) > MAX_STATE_BYTES:
        if len(turns) <= 1:
            raise MaintenanceError("MAINTENANCE_STATE_TOO_LARGE", "Turn metadata exceeds the local size limit.")
        del turns[next(iter(turns))]
    try:
        store._write_json_atomic(state_path(base), state)
    except OSError as exc:
        raise MaintenanceError("MAINTENANCE_WRITE_FAILED", "Could not persist local maintenance metadata.") from exc


def set_enabled(base, enabled):
    with store.workspace_write_lock(base, operation="maintenance.configure"):
        state = read_state(base)
        if state["enabled"] != enabled:
            state["generation"] += 1
        state["enabled"] = enabled
        write_state(base, state)
    return state


def fingerprints(graph):
    return {
        obj_id: hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()
        for kind in store.SUBDIRS for obj_id, obj in graph[kind].items()
    }


def verified_graph(base):
    graph = store.load_graph_once(base)
    if not store.validate_graph(graph)["healthy"]:
        raise MaintenanceError("HISTORY_UNHEALTHY", "Intent graph has warnings; diagnose with itt doctor.")
    return graph


def turn_key(root, session_id, turn_id):
    return hashlib.sha256(json.dumps([str(root), session_id, turn_id]).encode("utf-8")).hexdigest()


def find_turn(state, root, session_id, turn_id):
    for key, entry in reversed(list(state["turns"].items())):
        if (entry["root"] == str(root) and entry["session_id"] == session_id
                and entry["generation"] == state["generation"]
                and turn_id in [entry["turn_id"], *entry["aliases"]]):
            return key, entry
    return None, None


def begin_turn(base, state, session_id, turn_id, prompt, context_factory):
    root = base.parent.resolve()
    key, entry = find_turn(state, root, session_id, turn_id)
    if entry is not None:
        return key, entry
    # Stop's continuation gets a new host turn ID. An exact, issued reason
    # maps it back to the original obligation, without resetting its budget.
    for key, entry in reversed(list(state["turns"].items())):
        if (entry["root"] == str(root) and entry["session_id"] == session_id
                and entry["generation"] == state["generation"]
                and entry.get("continuation_reason") == prompt and prompt
                and entry["retry_count"] == 1 and len(entry["aliases"]) < 1):
            entry["aliases"].append(turn_id)
            write_state(base, state)
            return key, entry
    key = turn_key(root, session_id, turn_id)
    graph = None
    try:
        graph = verified_graph(base)
        baseline = fingerprints(graph)
        unavailable = None
    except (store.StorageSecurityError, MaintenanceError, OSError) as exc:
        baseline, unavailable = None, type(exc).__name__
    entry = {"root": str(root), "session_id": session_id, "turn_id": turn_id,
             "generation": state["generation"], "started_at": time.time(),
             "baseline": baseline, "entry_error": unavailable, "aliases": [],
             "retry_count": 0, "receipt": None}
    entry["context"] = context_factory(base, key, entry, graph)
    state["turns"][key] = entry
    write_state(base, state)
    return key, entry


def close_turn(base, key, outcome, reason, objects):
    if not isinstance(key, str) or TOKEN.fullmatch(key) is None:
        raise MaintenanceError("INVALID_INPUT", "Use the turn token supplied by the entry hook.")
    if not isinstance(reason, str) or len(reason) > 600:
        raise MaintenanceError("INVALID_INPUT", "A receipt reason must be at most 600 characters.")
    if outcome in {"no-op", "failed"} and not reason.strip():
        raise MaintenanceError("INVALID_INPUT", "no-op and failed require a short reason.")
    with store.workspace_write_lock(base, operation="maintenance.close"):
        state = read_state(base)
        entry = state["turns"].get(key)
        if (not state["enabled"] or entry is None or entry["root"] != str(base.parent.resolve())
                or entry["generation"] != state["generation"]):
            raise MaintenanceError("TURN_NOT_ACTIVE", "This project has no active matching turn.")
        verified, hashes = False, {}
        if outcome != "failed":
            graph = verified_graph(base)
            hashes = fingerprints(graph)
            verified = True
        references = {}
        if outcome == "recorded":
            if entry["baseline"] is None:
                # Recovery is allowed in the same turn. Without a baseline,
                # verify newly-created objects rather than claiming knowledge
                # of changes to older objects that could not be inspected.
                changed = {}
                for kind in store.SUBDIRS:
                    for obj_id, obj in graph[kind].items():
                        try:
                            created = datetime.fromisoformat(obj["created_at"])
                            fresh = created.tzinfo is not None and created.timestamp() >= entry["started_at"]
                        except (ValueError, TypeError, OverflowError):
                            fresh = False
                        if fresh:
                            changed[obj_id] = hashes[obj_id]
            else:
                changed = {obj_id: digest for obj_id, digest in hashes.items()
                           if entry["baseline"].get(obj_id) != digest}
            selected = objects or list(changed)
            if not selected or any(obj_id not in changed for obj_id in selected):
                raise MaintenanceError("RECORDING_UNVERIFIED", "recorded needs existing objects changed since this turn began.")
            references = {obj_id: changed[obj_id] for obj_id in selected}
        elif objects:
            raise MaintenanceError("INVALID_INPUT", "Only recorded receipts accept object IDs.")
        receipt = {"outcome": outcome, "reason": reason.strip(), "verified": verified, "objects": references}
        changed = receipt != entry["receipt"]
        entry["receipt"] = receipt
        if changed:
            write_state(base, state)
        return {"turn": key, "outcome": outcome, "objects": list(references), "verified": verified, "changed": changed}


def receipt_valid(base, entry):
    receipt = entry.get("receipt")
    if not isinstance(receipt, dict):
        return False
    outcome = receipt.get("outcome")
    reason = receipt.get("reason")
    if outcome == "failed":
        return isinstance(reason, str) and bool(reason.strip())
    if outcome not in {"recorded", "no-op"} or receipt.get("verified") is not True:
        return False
    if outcome == "no-op" and (not isinstance(reason, str) or not reason.strip()):
        return False
    references = receipt.get("objects")
    if not isinstance(references, dict) or (outcome == "recorded" and not references):
        return False
    try:
        current = fingerprints(verified_graph(base))
    except (store.StorageSecurityError, MaintenanceError, OSError):
        return False
    return all(current.get(obj_id) == digest for obj_id, digest in references.items())
