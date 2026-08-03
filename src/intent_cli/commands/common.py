"""Shared helpers for CLI command handlers."""

from datetime import datetime, timezone
from functools import wraps

from intent_cli.output import error
from intent_cli.store import (
    VALID_STATUSES,
    WorkspaceBusyError,
    ensure_init,
    git_root,
    workspace_write_lock,
)


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


def workspace_mutation(command):
    """Run a mutating command under the workspace's cross-process lock."""
    @wraps(command)
    def wrapped(args):
        base = require_init()
        operation = command.__name__.removeprefix("cmd_").replace("_", ".", 1)
        try:
            with workspace_write_lock(base, operation=operation):
                return command(args)
        except WorkspaceBusyError as exc:
            error(
                "WORKSPACE_BUSY",
                "Another Intent command is writing to this workspace.",
                details={"owner": exc.owner},
                suggested_fix="Wait for that command to finish, then retry.",
            )
    return wrapped


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
