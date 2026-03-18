"""Storage layer — .intent/ directory I/O and ID generation."""

import json
import subprocess
from pathlib import Path

INTENT_DIR = ".intent"
SUBDIRS = {"intent": "intents", "snap": "snaps", "decision": "decisions"}


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
