"""Hub command handlers for the Intent CLI."""

import hashlib
import json

from intent_cli.commands.common import now_utc, require_init, workspace_mutation
from intent_cli.hub.client import http_json
from intent_cli.hub.payload import build_sync_payload, current_repository
from intent_cli.hub.runtime import (
    config_without_auth_token,
    hub_api_base,
    hub_auth_configured,
    hub_auth_token,
    load_hub,
    sanitize_hub_config,
)
from intent_cli.output import error, success
from intent_cli.store import make_runtime_id, write_hub_config


def _repo_identity(repo):
    return {
        "provider": repo.get("provider"),
        "repo_id": repo.get("repo_id"),
    }


def _pending_link(hub):
    pending = hub.get("pending_link")
    if pending is None:
        return None
    valid = (
        isinstance(pending, dict)
        and isinstance(pending.get("workspace_id"), str)
        and bool(pending.get("workspace_id"))
        and isinstance(pending.get("repo_binding"), dict)
        and isinstance(pending.get("api_base_url"), str)
        and bool(pending.get("api_base_url"))
        and isinstance(pending.get("project_name"), str)
        and bool(pending.get("project_name"))
        and isinstance(pending.get("started_at"), str)
        and bool(pending.get("started_at"))
    )
    if not valid:
        error(
            "HUB_STATE_INVALID",
            "The repository's pending IntHub link state is invalid.",
            suggested_fix="Restore a valid .intent/hub.json from backup before retrying.",
        )
    return pending


def _pending_sync(hub):
    pending = hub.get("pending_sync")
    if pending is None:
        return None
    valid = (
        isinstance(pending, dict)
        and isinstance(pending.get("sync_batch_id"), str)
        and bool(pending.get("sync_batch_id"))
        and isinstance(pending.get("generated_at"), str)
        and bool(pending.get("generated_at"))
        and isinstance(pending.get("payload_sha256"), str)
        and len(pending.get("payload_sha256")) == 64
    )
    if not valid:
        error(
            "HUB_STATE_INVALID",
            "The repository's pending IntHub sync state is invalid.",
            suggested_fix="Restore a valid .intent/hub.json from backup before retrying.",
        )
    return pending


def _payload_sha256(payload):
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_link_state(hub, pending, repo, api_base_url):
    actual = _repo_identity(repo)
    existing = hub.get("repo_binding")
    if existing and _repo_identity(existing) != actual:
        error(
            "REPO_BINDING_MISMATCH",
            "Git remote 'origin' does not match this workspace's IntHub binding.",
            details={"expected": _repo_identity(existing), "actual": actual},
            suggested_fix="Restore the repository's bound origin before linking again.",
        )
    if pending is None:
        return
    pending_repo = pending.get("repo_binding")
    pending_url = pending.get("api_base_url")
    workspace_id = pending.get("workspace_id")
    if (
        not isinstance(pending_repo, dict)
        or _repo_identity(pending_repo) != actual
        or pending_url != api_base_url
        or not isinstance(workspace_id, str)
        or not workspace_id
    ):
        error(
            "PENDING_LINK_CONFLICT",
            "A previous unfinished IntHub link targets a different repository or endpoint.",
            details={
                "pending_api_base_url": pending_url,
                "pending_repo": (
                    _repo_identity(pending_repo)
                    if isinstance(pending_repo, dict)
                    else None
                ),
                "current_api_base_url": api_base_url,
                "current_repo": actual,
            },
            suggested_fix=(
                "Restore the original repository and endpoint, then rerun `itt hub link` "
                "to reconcile the unfinished operation."
            ),
        )


def _validate_link_result(result, workspace_id, repo):
    valid = (
        isinstance(result, dict)
        and isinstance(result.get("project_id"), str)
        and bool(result.get("project_id"))
        and result.get("workspace_id") == workspace_id
        and isinstance(result.get("repo_binding"), dict)
        and _repo_identity(result["repo_binding"]) == _repo_identity(repo)
    )
    if not valid:
        error(
            "SERVER_ERROR",
            "IntHub returned an inconsistent repository link result.",
            details={
                "expected_workspace_id": workspace_id,
                "expected_repo": _repo_identity(repo),
            },
        )


def _validate_sync_result(result, payload):
    valid = (
        isinstance(result, dict)
        and result.get("sync_batch_id") == payload["sync_batch_id"]
        and result.get("project_id") == payload["project_id"]
        and result.get("workspace_id") == payload["workspace"]["workspace_id"]
        and isinstance(result.get("accepted_at"), str)
        and bool(result.get("accepted_at"))
    )
    if not valid:
        error(
            "SERVER_ERROR",
            "IntHub returned an inconsistent sync result.",
            details={
                "expected_sync_batch_id": payload["sync_batch_id"],
                "expected_project_id": payload["project_id"],
                "expected_workspace_id": payload["workspace"]["workspace_id"],
            },
        )


def cmd_hub_start(args):
    try:
        from apps.inthub_local.launcher import main as launch_main
    except ImportError:
        error(
            "HUB_NOT_CONFIGURED",
            "IntHub Local is not installed.",
            suggested_fix="Reinstall intent-cli: pip install . (from the Intent repo)",
        )

    argv = []
    if getattr(args, "port", None) is not None:
        argv += ["--port", str(args.port)]
    if getattr(args, "no_open", False):
        argv += ["--no-open"]
    launch_main(argv)


def cmd_hub_status(args):
    """Report effective local binding and credential availability without an API call."""
    base = require_init()
    hub = load_hub(base)
    api_base_url = hub_api_base(base, args, hub)
    required = ("project_id", "workspace_id", "repo_binding")
    missing = [key for key in required if not hub.get(key)]
    pending = _pending_link(hub)
    pending_sync = _pending_sync(hub)
    result = {
        "linked": not missing,
        "api_base_url": api_base_url,
        "credential_available": hub_auth_configured(api_base_url),
        "project_id": hub.get("project_id"),
        "workspace_id": hub.get("workspace_id"),
        "repo_binding": hub.get("repo_binding"),
        "last_sync_batch_id": hub.get("last_sync_batch_id"),
        "last_synced_at": hub.get("last_synced_at"),
        "link_pending": pending is not None,
        "sync_pending": pending_sync is not None,
        "missing_fields": missing,
    }
    if pending is not None:
        result["pending_link"] = {
            "workspace_id": pending.get("workspace_id"),
            "repo_binding": pending.get("repo_binding"),
            "api_base_url": pending.get("api_base_url"),
            "started_at": pending.get("started_at"),
        }
    if pending_sync is not None:
        result["pending_sync"] = {
            "sync_batch_id": pending_sync.get("sync_batch_id"),
            "generated_at": pending_sync.get("generated_at"),
        }
    success("hub.status", result)


@workspace_mutation
def cmd_hub_link(args):
    base = require_init()
    hub = load_hub(base)
    repo = current_repository()
    api_base_url = hub_api_base(base, args, hub)
    token = hub_auth_token(base, args, api_base_url)
    pending = _pending_link(hub)
    _validate_link_state(hub, pending, repo, api_base_url)

    workspace_id = (
        (pending or {}).get("workspace_id")
        or hub.get("workspace_id")
        or make_runtime_id("wks")
    )
    project_name = (
        (pending or {}).get("project_name")
        or args.project_name
        or repo["name"]
    )
    pending_state = {
        "workspace_id": workspace_id,
        "repo_binding": repo,
        "api_base_url": api_base_url,
        "project_name": project_name,
        "started_at": (pending or {}).get("started_at") or now_utc(),
    }
    staged = config_without_auth_token(hub)
    staged["api_base_url"] = api_base_url
    staged["pending_link"] = pending_state
    write_hub_config(base, staged)

    payload = {
        "project_name": project_name,
        "repo": {
            "provider": repo["provider"],
            "repo_id": repo["repo_id"],
            "owner": repo["owner"],
            "name": repo["name"],
        },
        "workspace": {
            "workspace_id": workspace_id,
        },
    }
    result = http_json("POST", f"{api_base_url}/api/v1/hub/link", payload, token)
    _validate_link_result(result, workspace_id, repo)

    updated = {
        "api_base_url": api_base_url,
        "workspace_id": result["workspace_id"],
        "project_id": result["project_id"],
        "repo_binding": result["repo_binding"],
        "last_sync_batch_id": hub.get("last_sync_batch_id"),
        "last_synced_at": hub.get("last_synced_at"),
    }
    if hub.get("pending_sync") is not None:
        updated["pending_sync"] = hub["pending_sync"]
    persisted = config_without_auth_token(updated)
    write_hub_config(base, persisted)
    success(
        "hub.link",
        sanitize_hub_config(
            persisted,
            auth_configured=hub_auth_configured(api_base_url),
        ),
    )


def _sync(args, action):
    base = require_init()
    hub = load_hub(base)

    missing = [key for key in ("project_id", "workspace_id", "repo_binding") if not hub.get(key)]
    if missing:
        error(
            "NOT_LINKED",
            f"Workspace is not linked to IntHub. Missing: {', '.join(missing)}.",
            suggested_fix="Run: itt hub link",
        )
    if _pending_link(hub) is not None:
        error(
            "LINK_PENDING",
            "A repository link operation is still pending reconciliation.",
            suggested_fix="Run `itt hub link` before pushing.",
        )

    api_base_url = hub_api_base(base, args, hub)
    token = hub_auth_token(base, args, api_base_url)
    persisted = config_without_auth_token(hub)

    if args.dry_run:
        sync_hub = dict(persisted)
        sync_hub["sync_batch_id"] = make_runtime_id("sync")
        payload = build_sync_payload(base, sync_hub)
        success(action, {"dry_run": True, "payload": payload})
        return

    pending = _pending_sync(hub)
    if pending is None:
        sync_batch_id = make_runtime_id("sync")
        generated_at = now_utc()
    else:
        sync_batch_id = pending["sync_batch_id"]
        generated_at = pending["generated_at"]

    sync_hub = dict(persisted)
    sync_hub["sync_batch_id"] = sync_batch_id
    payload = build_sync_payload(base, sync_hub, generated_at=generated_at)
    payload_sha256 = _payload_sha256(payload)

    if pending is not None and pending["payload_sha256"] != payload_sha256:
        sync_batch_id = make_runtime_id("sync")
        generated_at = now_utc()
        sync_hub["sync_batch_id"] = sync_batch_id
        payload = build_sync_payload(base, sync_hub, generated_at=generated_at)
        payload_sha256 = _payload_sha256(payload)

    persisted["pending_sync"] = {
        "sync_batch_id": sync_batch_id,
        "generated_at": generated_at,
        "payload_sha256": payload_sha256,
    }
    write_hub_config(base, persisted)

    result = http_json("POST", f"{api_base_url}/api/v1/sync-batches", payload, token)
    _validate_sync_result(result, payload)

    persisted.pop("pending_sync", None)
    persisted["last_sync_batch_id"] = payload["sync_batch_id"]
    persisted["last_synced_at"] = result.get("accepted_at", payload["generated_at"])
    write_hub_config(base, persisted)
    success(
        action,
        {
            "batch": result,
            "hub": sanitize_hub_config(
                persisted,
                auth_configured=hub_auth_configured(api_base_url),
            ),
        },
    )


@workspace_mutation
def cmd_hub_sync(args):
    _sync(args, "hub.sync")


@workspace_mutation
def cmd_push(args):
    _sync(args, "push")
