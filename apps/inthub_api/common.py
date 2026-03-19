"""Shared helpers for the IntHub API."""

import uuid
from datetime import datetime, timezone


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def make_remote_object_id(workspace_id, local_object_id):
    return f"{workspace_id}__{local_object_id}"


def split_remote_object_id(remote_object_id):
    parts = remote_object_id.split("__", 1)
    if len(parts) != 2:
        raise ValueError("Invalid remote object ID.")
    return parts[0], parts[1]


class APIError(Exception):
    def __init__(self, code, message, status=400, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}


def require_repo(repo):
    required = ("provider", "repo_id", "owner", "name")
    missing = [key for key in required if not repo.get(key)]
    if missing:
        raise APIError(
            "INVALID_INPUT",
            f"Missing repo fields: {', '.join(missing)}.",
            status=400,
        )
