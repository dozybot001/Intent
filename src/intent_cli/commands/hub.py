"""Hub command handlers for the Intent CLI."""

import sys
from pathlib import Path

from intent_cli.commands.common import require_init
from intent_cli.hub.client import http_json
from intent_cli.hub.payload import build_sync_payload, current_github_repo
from intent_cli.hub.runtime import (
    hub_api_base,
    hub_auth_token,
    load_hub,
    sanitize_hub_config,
)
from intent_cli.output import error, success
from intent_cli.store import make_runtime_id, write_hub_config


def cmd_hub_start(args):
    launcher = Path.cwd() / "apps" / "inthub_local" / "launcher.py"
    if not launcher.exists():
        error(
            "HUB_NOT_CONFIGURED",
            "IntHub Local source not found in current directory.",
            suggested_fix="cd into the cloned Intent repo, then run: itt hub start",
        )

    # Add repo root to sys.path so `apps.*` imports resolve
    repo_root = str(Path.cwd())
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from apps.inthub_local.launcher import main as launch_main

    argv = []
    if getattr(args, "port", None) is not None:
        argv += ["--port", str(args.port)]
    if getattr(args, "no_open", False):
        argv += ["--no-open"]
    launch_main(argv or None)


def cmd_hub_link(args):
    base = require_init()
    hub = load_hub(base)
    repo = current_github_repo()

    if args.api_base_url:
        hub["api_base_url"] = args.api_base_url.rstrip("/")
    api_base_url = hub.get("api_base_url")
    if not api_base_url:
        error(
            "HUB_NOT_CONFIGURED",
            "IntHub API base URL is not configured.",
            suggested_fix="Run: itt hub link --api-base-url http://127.0.0.1:8000",
        )

    if args.token:
        hub["auth_token"] = args.token
    elif "auth_token" not in hub:
        hub["auth_token"] = ""

    token = hub_auth_token(base, args)

    workspace_id = hub.get("workspace_id") or make_runtime_id("wks")
    payload = {
        "project_name": args.project_name or repo["name"],
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

    updated = {
        "api_base_url": api_base_url,
        "auth_token": hub.get("auth_token", ""),
        "workspace_id": result["workspace_id"],
        "project_id": result["project_id"],
        "repo_binding": result["repo_binding"],
        "last_sync_batch_id": hub.get("last_sync_batch_id"),
        "last_synced_at": hub.get("last_synced_at"),
    }
    write_hub_config(base, updated)
    success("hub.link", sanitize_hub_config(updated))


def cmd_hub_sync(args):
    base = require_init()
    hub = load_hub(base)

    missing = [key for key in ("project_id", "workspace_id", "repo_binding") if not hub.get(key)]
    if missing:
        error(
            "NOT_LINKED",
            f"Workspace is not linked to IntHub. Missing: {', '.join(missing)}.",
            suggested_fix="Run: itt hub link",
        )

    api_base_url = hub_api_base(base, args)
    token = hub_auth_token(base, args)

    sync_hub = dict(hub)
    sync_hub["sync_batch_id"] = make_runtime_id("sync")
    payload = build_sync_payload(base, sync_hub)

    if args.dry_run:
        success("hub.sync", {"dry_run": True, "payload": payload})
        return

    result = http_json("POST", f"{api_base_url}/api/v1/sync-batches", payload, token)

    hub["last_sync_batch_id"] = payload["sync_batch_id"]
    hub["last_synced_at"] = result.get("accepted_at", payload["generated_at"])
    write_hub_config(base, hub)
    success(
        "hub.sync",
        {
            "batch": result,
            "hub": sanitize_hub_config(hub),
        },
    )
