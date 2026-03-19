"""Shared helpers for CLI command handlers."""

from datetime import datetime, timezone

from intent_cli.output import error
from intent_cli.store import VALID_STATUSES, ensure_init, git_root


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def require_init():
    """Return .intent/ base path, or exit with a structured error."""
    base = ensure_init()
    if base is not None:
        return base
    if git_root() is None:
        error(
            "GIT_STATE_INVALID",
            "Not inside a Git repository.",
            suggested_fix="cd into a git repo and run: itt init",
        )
    error(
        "NOT_INITIALIZED",
        ".intent/ directory not found.",
        suggested_fix="itt init",
    )


def validate_status_filter(object_type, status):
    """Validate a --status filter against the object's state machine."""
    if status is None:
        return
    allowed = sorted(VALID_STATUSES[object_type])
    if status not in allowed:
        error(
            "INVALID_INPUT",
            f"Invalid status '{status}' for {object_type}. Allowed values: {', '.join(allowed)}.",
            suggested_fix=f"Use one of: {', '.join(allowed)}",
        )
