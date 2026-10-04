"""Content-addressed semantic revisions, independent of source-control Git."""

import hashlib
import json
import re

from intent_cli.hub.snapshots import snapshot_sha256

VERSION = re.compile(r"[a-f0-9]{64}\Z")


def validate_project_name(value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 120
            or value != value.strip() or value in {".", ".."}
            or any(ord(char) < 32 or ord(char) == 127 or char in "/\\" for char in value)):
        raise ValueError("Project name must be 1–120 characters, without slashes or control characters.")
    try:
        value.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("Project name must be valid UTF-8.") from exc
    return value


def revision_id(parent, snapshot):
    if parent is not None and (not isinstance(parent, str) or not VERSION.fullmatch(parent)):
        raise ValueError("Parent revision must be a SHA-256 revision ID or null.")
    raw = json.dumps({"parent": parent, "snapshot_sha256": snapshot_sha256(snapshot)},
                     sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
