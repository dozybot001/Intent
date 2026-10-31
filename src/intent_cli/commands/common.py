"""Shared helpers for CLI command handlers."""

from datetime import datetime, timezone
from functools import wraps

from intent_cli import repo
from intent_cli.output import error, hold_reports
from intent_cli.store import (
    SUBDIRS,
    VALID_STATUSES,
    WorkspaceBusyError,
    ensure_init,
    resolve_object_id,
    workspace_write_lock,
)

ID_ARGUMENTS = ("id", "intent", "into", "other", "source", "part_of", "derived_from",
                "succeeds", "depends_on", "conflicts_with")


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def require_init():
    """Return .intent/ base path, or exit with a structured error."""
    base = ensure_init()
    if base is not None:
        return base
    error(
        "NOT_INITIALIZED",
        ".intent/ directory not found.",
        suggested_fix="itt init",
    )


def expand_ids(base, args):
    """Let every ID argument be a unique prefix, the way Git takes short hashes."""
    for name in ID_ARGUMENTS:
        value = getattr(args, name, None)
        kind = value.split("-", 1)[0] if isinstance(value, str) else ""
        if kind in SUBDIRS:
            setattr(args, name, resolve_object_id(base, kind, value))


def require_repository(base):
    """Stop a write to a 7.x workspace: its history has to move to a repository first."""
    if not repo.is_repository(base):
        error(
            "REPOSITORY_NOT_MIGRATED",
            "This project still uses the Intent 7 format, which this version can read but not write.",
            suggested_fix="itt migrate",
        )
    state = repo.read_merge_state(base)
    if state is not None:
        error(
            "MERGE_IN_PROGRESS",
            f"A merge of {state['branch']} is in progress.",
            suggested_fix="itt resolve ID ..., then itt merge --continue, or itt merge --abort.",
        )


def require_main(base):
    """Remote sync follows main until the next protocol carries branches."""
    require_repository(base)
    branch = repo.current_branch(base)
    if branch != repo.DEFAULT_BRANCH:
        error(
            "NOT_ON_MAIN",
            f"Push and pull work on {repo.DEFAULT_BRANCH}; this copy is on {branch}.",
            suggested_fix=f"Merge {branch} into {repo.DEFAULT_BRANCH}, then push from there.",
        )


def workspace_mutation(command):
    """Run a mutating command under the workspace's lock, ending in one revision."""
    @wraps(command)
    def wrapped(args):
        base = require_init()
        require_repository(base)
        expand_ids(base, args)
        operation = command.__name__.removeprefix("cmd_").replace("_", ".", 1)
        try:
            with workspace_write_lock(base, operation=operation), hold_reports():
                command(args)
                repo.commit_worktree(base, operation)
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
