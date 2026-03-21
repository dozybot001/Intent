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
    parse_github_remote,
    read_config,
)


def current_github_repo():
    remote = git_remote_url()
    if remote is None:
        error(
            "GIT_STATE_INVALID",
            "Git remote 'origin' is not configured.",
            suggested_fix="Add a GitHub remote, for example: git remote add origin git@github.com:<owner>/<repo>.git",
        )
    repo = parse_github_remote(remote)
    if repo is None:
        error(
            "PROVIDER_UNSUPPORTED",
            f"Remote '{remote}' is not a supported GitHub repository URL.",
            suggested_fix="Use a GitHub origin remote for IntHub V1.",
        )
    repo["remote_url"] = remote
    return repo


def snapshot_payload(base):
    return {
        "schema_version": read_config(base).get("schema_version", "1.0"),
        "intents": list_objects(base, "intent"),
        "snaps": list_objects(base, "snap"),
        "decisions": list_objects(base, "decision"),
    }


def build_sync_payload(base, hub_config):
    return {
        "sync_batch_id": hub_config["sync_batch_id"],
        "generated_at": now_utc(),
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
