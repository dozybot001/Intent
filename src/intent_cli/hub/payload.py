"""Payload builders for IntHub synchronization."""

from intent_cli import __version__
from intent_cli.commands.common import now_utc
from intent_cli.output import error
from intent_cli.store import (
    git_current_branch,
    git_head_commit,
    git_is_dirty,
    git_remote_url,
    list_objects,
    parse_repository_remote,
)


def current_repository():
    remote = git_remote_url()
    if remote is None:
        error(
            "GIT_STATE_INVALID",
            "Git remote 'origin' is not configured.",
            suggested_fix=(
                "Add the repository's real GitHub or Gitee origin. "
                "Do not temporarily rewrite origin for IntHub."
            ),
        )
    repo = parse_repository_remote(remote)
    if repo is None:
        error(
            "PROVIDER_UNSUPPORTED",
            "Git remote 'origin' is not a supported GitHub or Gitee repository URL.",
            suggested_fix=(
                "Use the repository's real github.com or gitee.com origin. "
                "Do not temporarily rewrite origin for IntHub."
            ),
        )
    return repo


def require_matching_repository(repo_binding):
    """Reject pushes whose current origin differs from the saved IntHub binding."""
    current = current_repository()
    expected = {
        "provider": repo_binding.get("provider"),
        "repo_id": repo_binding.get("repo_id"),
    }
    actual = {
        "provider": current["provider"],
        "repo_id": current["repo_id"],
    }
    if actual != expected:
        error(
            "REPO_BINDING_MISMATCH",
            "Git remote 'origin' does not match this workspace's IntHub binding.",
            details={"expected": expected, "actual": actual},
            suggested_fix=(
                "Restore the repository's bound origin before pushing. "
                "Never temporarily rewrite origin to bypass provider checks."
            ),
        )
    return current


def snapshot_payload(base):
    return {
        "intents": list_objects(base, "intent"),
        "snaps": list_objects(base, "snap"),
        "decisions": list_objects(base, "decision"),
    }


def build_sync_payload(base, hub_config, *, generated_at=None):
    require_matching_repository(hub_config["repo_binding"])
    return {
        "sync_batch_id": hub_config["sync_batch_id"],
        "generated_at": generated_at or now_utc(),
        "client": {
            "name": "intent-cli",
            "version": __version__,
        },
        "project_id": hub_config["project_id"],
        "repo": hub_config["repo_binding"],
        "workspace": {
            "workspace_id": hub_config["workspace_id"],
        },
        "git": {
            "branch": git_current_branch(),
            "head_commit": git_head_commit(),
            "dirty": git_is_dirty(),
            "remote_url": git_remote_url(),
        },
        "snapshot": snapshot_payload(base),
    }
