"""Storage layer — .intent/ directory I/O and ID generation."""

import json
import subprocess
from pathlib import Path

INTENT_DIR = ".intent"
SUBDIRS = {"intent": "intents", "snap": "snaps", "decision": "decisions"}
VALID_STATUSES = {
    "intent": {"active", "suspend", "done"},
    "snap": {"active", "reverted"},
    "decision": {"active", "deprecated"},
}


def git_root():
    """Return git repo root as Path, or None."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def intent_dir():
    """Return Path to .intent/, or None if not in a git repo."""
    root = git_root()
    return root / INTENT_DIR if root else None


def ensure_init():
    """Return .intent/ Path if initialized, else None."""
    d = intent_dir()
    return d if d and d.is_dir() else None


def init_workspace():
    """Create .intent/ structure. Returns (path, error_code)."""
    root = git_root()
    if root is None:
        return None, "GIT_STATE_INVALID"
    d = root / INTENT_DIR
    if d.is_dir():
        return None, "ALREADY_EXISTS"
    d.mkdir()
    for sub in SUBDIRS.values():
        (d / sub).mkdir()
    (d / "config.json").write_text(json.dumps({"schema_version": "1.0"}, indent=2))
    return d, None


def next_id(base, object_type):
    """Generate next zero-padded ID for a given object type."""
    subdir = base / SUBDIRS[object_type]
    max_num = 0
    for f in subdir.glob(f"{object_type}-*.json"):
        try:
            num = int(f.stem.split("-", 1)[1])
            max_num = max(max_num, num)
        except (ValueError, IndexError):
            continue
    return f"{object_type}-{max_num + 1:03d}"


def read_object(base, object_type, obj_id):
    """Read object JSON by ID. Returns dict or None."""
    path = base / SUBDIRS[object_type] / f"{obj_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text())


def write_object(base, object_type, obj_id, data):
    """Write object dict to JSON file."""
    path = base / SUBDIRS[object_type] / f"{obj_id}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def list_objects(base, object_type, status=None):
    """List all objects of a type, optionally filtered by status."""
    subdir = base / SUBDIRS[object_type]
    result = []
    for f in sorted(subdir.glob(f"{object_type}-*.json")):
        obj = json.loads(f.read_text())
        if status is None or obj.get("status") == status:
            result.append(obj)
    return result


def read_config(base):
    """Read config.json. Returns dict."""
    return json.loads((base / "config.json").read_text())


def validate_graph(base):
    """Validate the object graph and return a structured report."""
    config = read_config(base)
    intents = {obj["id"]: obj for obj in list_objects(base, "intent")}
    snaps = {obj["id"]: obj for obj in list_objects(base, "snap")}
    decisions = {obj["id"]: obj for obj in list_objects(base, "decision")}
    issues = []

    if config.get("schema_version") != "1.0":
        issues.append({
            "code": "SCHEMA_VERSION_MISMATCH",
            "object": "config",
            "id": "config.json",
            "message": f"Unsupported schema_version '{config.get('schema_version')}'. Expected '1.0'.",
        })

    def add_issue(code, object_type, obj_id, message):
        issues.append({
            "code": code,
            "object": object_type,
            "id": obj_id,
            "message": message,
        })

    for object_type, objects in (
        ("intent", intents),
        ("snap", snaps),
        ("decision", decisions),
    ):
        for obj_id, obj in objects.items():
            if obj.get("object") != object_type:
                add_issue(
                    "OBJECT_TYPE_MISMATCH",
                    object_type,
                    obj_id,
                    f"Stored object type is '{obj.get('object')}', expected '{object_type}'.",
                )
            status = obj.get("status")
            if status not in VALID_STATUSES[object_type]:
                add_issue(
                    "INVALID_STATUS",
                    object_type,
                    obj_id,
                    f"Invalid status '{status}' for {object_type}.",
                )

    for intent_id, intent in intents.items():
        for snap_id in intent.get("snap_ids", []):
            snap = snaps.get(snap_id)
            if snap is None:
                add_issue(
                    "MISSING_REFERENCE",
                    "intent",
                    intent_id,
                    f"References missing snap {snap_id} in snap_ids.",
                )
                continue
            if snap.get("intent_id") != intent_id:
                add_issue(
                    "BROKEN_LINK",
                    "intent",
                    intent_id,
                    f"Snap {snap_id} points to intent {snap.get('intent_id')}, not {intent_id}.",
                )
        for decision_id in intent.get("decision_ids", []):
            decision = decisions.get(decision_id)
            if decision is None:
                add_issue(
                    "MISSING_REFERENCE",
                    "intent",
                    intent_id,
                    f"References missing decision {decision_id} in decision_ids.",
                )
                continue
            if intent_id not in decision.get("intent_ids", []):
                add_issue(
                    "BROKEN_LINK",
                    "intent",
                    intent_id,
                    f"Decision {decision_id} does not link back to this intent.",
                )

    for snap_id, snap in snaps.items():
        intent_id = snap.get("intent_id")
        intent = intents.get(intent_id)
        if intent is None:
            add_issue(
                "MISSING_REFERENCE",
                "snap",
                snap_id,
                f"Points to missing intent {intent_id}.",
            )
            continue
        if snap_id not in intent.get("snap_ids", []):
            add_issue(
                "BROKEN_LINK",
                "snap",
                snap_id,
                f"Intent {intent_id} does not include this snap in snap_ids.",
            )

    for decision_id, decision in decisions.items():
        for intent_id in decision.get("intent_ids", []):
            intent = intents.get(intent_id)
            if intent is None:
                add_issue(
                    "MISSING_REFERENCE",
                    "decision",
                    decision_id,
                    f"References missing intent {intent_id} in intent_ids.",
                )
                continue
            if decision_id not in intent.get("decision_ids", []):
                add_issue(
                    "BROKEN_LINK",
                    "decision",
                    decision_id,
                    f"Intent {intent_id} does not link back to this decision.",
                )

    return {
        "healthy": not issues,
        "issue_count": len(issues),
        "summary": {
            "schema_version": config.get("schema_version", "1.0"),
            "intent_count": len(intents),
            "snap_count": len(snaps),
            "decision_count": len(decisions),
        },
        "issues": issues,
    }
