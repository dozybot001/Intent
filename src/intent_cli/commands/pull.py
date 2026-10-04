"""Explicit, account-private restoration of one IntHub workspace snapshot."""

import re
from urllib.parse import urlencode

from intent_cli.commands.common import now_utc, require_init
from intent_cli.commands.hub import _pending_link, _pending_sync, _repo_identity
from intent_cli.hub.client import http_json
from intent_cli.hub.credentials import normalize_api_base_url
from intent_cli.hub.payload import current_repository
from intent_cli.hub.restore import PullApplyError, install_snapshot
from intent_cli.hub.runtime import config_without_auth_token, hub_api_base, hub_auth_token, load_hub
from intent_cli.hub.snapshots import SnapshotError, require_fast_forward, snapshot_sha256, validate_snapshot
from intent_cli.output import error, success
from intent_cli.store import SUBDIRS, load_graph_once, workspace_write_lock


def _nonempty_text(value):
    if not isinstance(value, str) or not value:
        return False
    try:
        value.encode("utf-8")
    except UnicodeError:
        return False
    return True


def _local_state(base):
    hub = load_hub(base)
    for field in ("project_id", "workspace_id", "api_base_url"):
        value = hub.get(field)
        if value is not None and not _nonempty_text(value):
            error("HUB_STATE_INVALID", f"The local {field} must be a nonempty string.")
    binding = hub.get("repo_binding")
    if binding is not None and (
        not isinstance(binding, dict)
        or not isinstance(binding.get("provider"), str)
        or binding.get("provider") not in {"github", "gitee"}
        or not _nonempty_text(binding.get("repo_id"))
    ):
        error("HUB_STATE_INVALID", "The local repository binding is invalid.")
    if _pending_link(hub) or _pending_sync(hub):
        error("HUB_OPERATION_PENDING", "Reconcile pending link/push before pulling.")
    graph = load_graph_once(base)
    snapshot = {collection: list(graph[kind].values()) for kind, collection in SUBDIRS.items()}
    try:
        validate_snapshot(snapshot)
    except SnapshotError as exc:
        error("INVALID_LOCAL_SNAPSHOT", str(exc), suggested_fix="Run: itt doctor")
    return hub, snapshot, snapshot_sha256(snapshot)


def _source(hub):
    source = hub.get("pull_source")
    if source is not None and (
        not isinstance(source, dict)
        or not _nonempty_text(source.get("project_id"))
        or not _nonempty_text(source.get("workspace_id"))
        or not _nonempty_text(source.get("sync_batch_id"))
        or type(source.get("sequence_id")) is not int or source["sequence_id"] < 1
        or not isinstance(source.get("snapshot_sha256"), str)
        or re.fullmatch(r"[a-f0-9]{64}", source["snapshot_sha256"]) is None
    ):
        error("HUB_STATE_INVALID", "The local pull provenance is invalid.")
    return source


def _validate_result(result, repo, project_id, workspace_id):
    valid = (
        isinstance(result, dict) and type(result.get("format_version")) is int
        and result["format_version"] == 1
        and _nonempty_text(result.get("project_id"))
        and (not project_id or result["project_id"] == project_id)
        and isinstance(result.get("repo_binding"), dict)
        and _repo_identity(result["repo_binding"]) == _repo_identity(repo)
        and _nonempty_text(result.get("source_workspace_id"))
        and (not workspace_id or result["source_workspace_id"] == workspace_id)
        and isinstance(result.get("batch"), dict)
    )
    batch = result.get("batch", {}) if isinstance(result, dict) else {}
    valid = valid and (
        _nonempty_text(batch.get("sync_batch_id"))
        and type(batch.get("sequence_id")) is int and batch["sequence_id"] > 0
        and _nonempty_text(batch.get("accepted_at"))
        and _nonempty_text(batch.get("generated_at"))
    )
    if not valid:
        error("INVALID_REMOTE_SNAPSHOT", "IntHub returned an inconsistent snapshot identity or version.")
    try:
        validate_snapshot(result.get("snapshot"))
    except SnapshotError as exc:
        error("INVALID_REMOTE_SNAPSHOT", str(exc))
    return result["snapshot"]


def cmd_pull(args):
    base = require_init()
    with workspace_write_lock(base, operation="pull.preflight"):
        hub, local, local_hash = _local_state(base)
        repo = current_repository()
        if hub.get("repo_binding") and _repo_identity(hub["repo_binding"]) != _repo_identity(repo):
            error("REPO_BINDING_MISMATCH", "Git origin does not match this checkout's binding.")
        source = _source(hub)
        api_base_url = hub_api_base(base, args, hub)
        if (hub.get("project_id") or source) and hub.get("api_base_url") and (
            normalize_api_base_url(hub["api_base_url"]) != api_base_url
        ):
            error("PULL_SOURCE_MISMATCH", "Pull cannot silently switch the bound IntHub endpoint.")
        workspace_id = args.workspace or (source or {}).get("workspace_id") or hub.get("workspace_id")
        if source and workspace_id != source["workspace_id"] and any(local.values()):
            error("PULL_SOURCE_MISMATCH", "A nonempty checkout cannot switch its pull source.")
        token = hub_auth_token(base, args, api_base_url)

    # Network latency never holds the local writer lock. Recheck everything below.
    query = {"provider": repo["provider"], "repo_id": repo["repo_id"]}
    if workspace_id:
        query["workspace_id"] = workspace_id
    result = http_json("GET", f"{api_base_url}/api/v1/hub/snapshot?{urlencode(query)}", token=token)
    remote = _validate_result(result, repo, hub.get("project_id") or (source or {}).get("project_id"), workspace_id)
    remote_hash = snapshot_sha256(remote)
    batch = result["batch"]

    with workspace_write_lock(base, operation="pull.apply"):
        current_hub, current, current_hash = _local_state(base)
        if current_hub != hub or current_hash != local_hash or _repo_identity(current_repository()) != _repo_identity(repo):
            error("LOCAL_STATE_CHANGED", "Local history, binding, or Git origin changed during download; nothing was applied.")
        same_source = source and source["workspace_id"] == result["source_workspace_id"]
        if same_source and batch["sequence_id"] < source["sequence_id"]:
            error("REMOTE_HISTORY_REWOUND", "The remote source returned an older accepted revision.")
        if same_source and batch["sync_batch_id"] == source["sync_batch_id"] and (
            remote_hash != source["snapshot_sha256"] or batch["sequence_id"] != source["sequence_id"]
        ):
            error("REMOTE_HISTORY_CONFLICT", "An existing remote batch changed its content or revision.")
        if same_source and batch["sequence_id"] == source["sequence_id"] and (
            batch["sync_batch_id"] != source["sync_batch_id"] or remote_hash != source["snapshot_sha256"]
        ):
            error("REMOTE_HISTORY_CONFLICT", "An existing accepted revision changed its batch or content.")

        baseline = (source or {}).get("snapshot_sha256") if same_source else None
        if result["source_workspace_id"] == hub.get("workspace_id"):
            baseline = hub.get("last_snapshot_sha256") or baseline
        if baseline is not None and (
            not isinstance(baseline, str) or re.fullmatch(r"[a-f0-9]{64}", baseline) is None
        ):
            error("HUB_STATE_INVALID", "The local synchronized snapshot baseline is invalid.")

        identical = remote_hash == local_hash
        remote_unchanged = baseline is not None and baseline == remote_hash
        if not identical and not remote_unchanged:
            if baseline is None and any(local.values()):
                error("LOCAL_HISTORY_CONFLICT", "Nonempty local history has no verified baseline for this source; nothing was overwritten.")
            if baseline is not None and local_hash != baseline:
                error("LOCAL_CHANGES", "Local history and remote source both changed; pull does not merge or overwrite them.")
            try:
                require_fast_forward(local, remote)
            except SnapshotError as exc:
                error("REMOTE_HISTORY_CONFLICT", str(exc))

        output = {
            "dry_run": args.dry_run, "project_id": result["project_id"],
            "source_workspace_id": result["source_workspace_id"],
            "workspace_id": hub.get("workspace_id"), "sync_batch_id": batch["sync_batch_id"],
            "sequence_id": batch["sequence_id"], "counts": {k: len(v) for k, v in remote.items()},
            "changed": not identical and not remote_unchanged,
            "local_changes": bool(baseline and local_hash != baseline and not identical),
            "linked": bool(hub.get("project_id") and hub.get("workspace_id") and hub.get("repo_binding")),
        }
        if args.dry_run or (remote_unchanged and not identical):
            success("pull", output)
            return

        provenance = {
            "project_id": result["project_id"], "workspace_id": result["source_workspace_id"],
            "sync_batch_id": batch["sync_batch_id"], "sequence_id": batch["sequence_id"],
            "snapshot_sha256": remote_hash,
        }
        if identical and hub.get("pull_source") == provenance:
            success("pull", output)
            return

        updated = config_without_auth_token(hub)
        updated.update(api_base_url=api_base_url, pull_source=provenance, last_pulled_at=now_utc())
        # A new checkout must link its own workspace before its first push.
        # Never copy the remote checkout's identity or credentials into hub.json.
        try:
            install_snapshot(base, remote, updated)
        except PullApplyError as exc:
            error("PULL_APPLY_FAILED", str(exc), details={"recovery_required": exc.recovery_required, "committed": exc.committed})
        output["last_pulled_at"] = updated["last_pulled_at"]
        success("pull", output)
