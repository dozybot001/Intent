"""Git-like synchronization of a single shared semantic history, without Git."""

import re
from urllib.parse import urlencode

from intent_cli import identity, repo
from intent_cli.commands.common import require_init, require_main
from intent_cli.hub.client import http_json
from intent_cli.hub.credentials import normalize_api_base_url, GlobalHubConfigError
from intent_cli.hub.rebase import rebase_snapshot
from intent_cli.hub.restore import install_snapshot
from intent_cli.hub.runtime import hub_api_base, hub_auth_token, hub_auth_configured, load_hub
from intent_cli.hub.snapshots import SnapshotError, require_fast_forward, snapshot_sha256, validate_snapshot
from intent_cli.hub.versions import revision_id, validate_project_ref, VERSION
from intent_cli.output import error, success
from intent_cli.store import SUBDIRS, load_graph_once, workspace_write_lock, write_hub_config


def _project_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r"proj_[A-Za-z0-9_]{1,80}", value))


def _linked(result, name):
    if (not isinstance(result, dict) or result.get("format_version") != 2
            or result.get("project_name") != name or not _project_id(result.get("project_id"))):
        error("SERVER_ERROR", "Invalid remote project link response.")
    return result


def _state(base, args):
    config = load_hub(base)
    if config.get("api_base_url") is not None:
        try:
            normalize_api_base_url(config["api_base_url"])
        except GlobalHubConfigError:
            error("HUB_STATE_INVALID", "Invalid configured endpoint.")
    name = getattr(args, "project", None) or config.get("project_name") or base.parent.name
    try:
        validate_project_ref(name)
    except ValueError as exc:
        error("INVALID_INPUT", str(exc))
    if config.get("format_version") == 2:
        if config.get("project_id") is not None and not _project_id(config["project_id"]):
            error("HUB_STATE_INVALID", "Invalid project ID in remote state.")
        for field in ("revision", "baseline_sha256"):
            value = config.get(field)
            if value is not None and (not isinstance(value, str) or not VERSION.fullmatch(value)):
                error("HUB_STATE_INVALID", f"Invalid {field} in remote state.")
        if bool(config.get("revision")) != bool(config.get("baseline_sha256")):
            error("HUB_STATE_INVALID", "Revision and baseline must be stored together.")
        if getattr(args, "project", None) and name != config.get("project_name"):
            error("REMOTE_CHANGED", "Use itt remote add origin URL --project NAME to change the remote project.")
    graph = load_graph_once(base)
    snapshot = {collection: list(graph[kind].values()) for kind, collection in SUBDIRS.items()}
    try:
        validate_snapshot(snapshot)
    except SnapshotError as exc:
        error("INVALID_LOCAL_SNAPSHOT", str(exc))
    return config, name, snapshot, snapshot_sha256(snapshot)


def _remote(base, args, config, name):
    api = hub_api_base(base, args, config)
    if config.get("format_version") == 2 and config.get("revision") and api != config.get("api_base_url"):
        error("REMOTE_CHANGED", "Use itt remote add to explicitly select a different endpoint.")
    query = {"project": name}
    known = config.get("project_id") if config.get("format_version") == 2 and not getattr(args, "project", None) else None
    if known:
        # IntHub finds the project by ID, so a rename made there is followed here.
        query["project_id"] = known
    result = http_json("GET", f"{api}/api/v2/history?{urlencode(query)}", token=hub_auth_token(base, args, api))
    renamed = isinstance(result, dict) and bool(known) and result.get("project_id") == known and result.get("project_name") != name
    if renamed:
        try:
            validate_project_ref(result.get("project_name"))
        except ValueError:
            renamed = False
    if not isinstance(result, dict) or result.get("format_version") != 2 or (result.get("project_name") != name and not renamed):
        error("INVALID_REMOTE_SNAPSHOT", "IntHub returned an inconsistent project identity or protocol.")
    if (not {"project_id", "revision", "parent", "snapshot", "snapshot_sha256"} <= result.keys()
            or (result["project_id"] is not None and not _project_id(result["project_id"]))
            or (result["revision"] is not None and result["project_id"] is None)):
        error("INVALID_REMOTE_SNAPSHOT", "Remote history is missing a valid identity or required fields.")
    if config.get("format_version") == 2 and config.get("project_id") and result.get("project_id") != config["project_id"]:
        error("REMOTE_CHANGED", "The remote project was deleted or replaced; inspect and explicitly relink it.",
              suggested_fix="If it was deleted on IntHub, run itt hub link, then itt push to publish this history again.")
    if result.get("revision") is not None:
        try:
            validate_snapshot(result.get("snapshot"))
            valid = revision_id(result.get("parent"), result["snapshot"]) == result["revision"] and snapshot_sha256(result["snapshot"]) == result.get("snapshot_sha256")
        except (SnapshotError, ValueError, KeyError):
            valid = False
        if not valid:
            error("INVALID_REMOTE_SNAPSHOT", "Remote revision or snapshot checksum is invalid.")
    elif result.get("snapshot") is not None or result.get("snapshot_sha256") is not None or result.get("parent") is not None:
        error("INVALID_REMOTE_SNAPSHOT", "An empty remote must not contain a snapshot.")
    return api, result


def _identity_warning():
    return [] if identity.author() else [identity.MISSING]


def _followed(name, remote):
    """The remote's current name, and the old one when the project was renamed on IntHub."""
    return remote["project_name"], ({"renamed_from": name} if remote["project_name"] != name else {})


def _config(api, name, remote):
    return {"format_version": 2, "api_base_url": api, "project_name": name,
            "project_id": remote.get("project_id"), "revision": remote.get("revision"),
            "baseline_sha256": remote.get("snapshot_sha256")}


def _relation(config, snapshot, local_hash, remote):
    baseline = config.get("baseline_sha256") if config.get("format_version") == 2 else None
    if remote["revision"] is None:
        return "ahead" if any(snapshot.values()) else "empty"
    if local_hash == remote["snapshot_sha256"]:
        return "up_to_date"
    if baseline == remote["snapshot_sha256"]:
        return "ahead"
    if baseline == local_hash or (baseline is None and not any(snapshot.values())):
        return "behind"
    return "diverged"


def _place(base):
    """Where this copy stands in its own history: nothing to say for an unmigrated project."""
    return {"branch": repo.current_branch(base), "head": repo.head_revision(base)} if repo.is_repository(base) else {}


def cmd_status(args):
    base = require_init()
    with workspace_write_lock(base, operation="status"):
        config, name, snapshot, digest = _state(base, args)
        place = _place(base)
    # Never contact a service the user has not chosen: without a configured
    # remote (or an explicit --api-base-url), status stays local.
    remote_configured = bool(config.get("api_base_url") or getattr(args, "api_base_url", None))
    if getattr(args, "local", False) or not remote_configured:
        success("status", {"project_name": name, **place, "remote_checked": False, "remote_configured": remote_configured,
            "local_changes": digest != config.get("baseline_sha256") and bool(config.get("baseline_sha256") or any(snapshot.values())),
            "revision": config.get("revision"), "counts": {k: len(v) for k, v in snapshot.items()}}, _identity_warning())
        return
    api, remote = _remote(base, args, config, name)
    name, followed = _followed(name, remote)
    success("status", {"project_name": name, **place, **followed, "api_base_url": api, "remote_checked": True,
        "state": _relation(config, snapshot, digest, remote), "revision": config.get("revision"),
        "remote_revision": remote["revision"], "counts": {k: len(v) for k, v in snapshot.items()}}, _identity_warning())


def cmd_remote(args):
    base = require_init()
    with workspace_write_lock(base, operation="remote"):
        config = load_hub(base)
        if args.sub == "add":
            if args.name != "origin":
                error("INVALID_INPUT", "The shared history supports one remote named origin.")
            api = normalize_api_base_url(args.url)
            name = args.project or base.parent.name
            try:
                validate_project_ref(name)
            except ValueError as exc:
                error("INVALID_INPUT", str(exc))
            if config.get("format_version") == 2 and config.get("api_base_url") == api and config.get("project_name") == name:
                success("remote.add", {"name": "origin", "api_base_url": api, "project_name": name})
                return
            write_hub_config(base, {"format_version": 2, "api_base_url": api, "project_name": name})
            success("remote.add", {"name": "origin", "api_base_url": api, "project_name": name})
        else:
            # Unconfigured projects report the default push target, marked as such.
            success("remote", {"name": "origin", "configured": bool(config.get("api_base_url")),
                "api_base_url": hub_api_base(base, args, config),
                "project_name": config.get("project_name") or base.parent.name})


def cmd_link(args):
    """Compatibility alias for configuring/linking a shared project."""
    base = require_init()
    with workspace_write_lock(base, operation="link"):
        config, name, _, _ = _state(base, args)
        name = args.project_name or name
        try:
            validate_project_ref(name)
        except ValueError as exc:
            error("INVALID_INPUT", str(exc))
        api = hub_api_base(base, args, config)
        linked = _linked(http_json("POST", f"{api}/api/v2/link", {"project_name": name}, hub_auth_token(base, args, api)), name)
        updated = {"format_version": 2, "api_base_url": api, "project_name": name,
                   "project_id": linked["project_id"]}
        if config.get("format_version") == 2 and config.get("project_id") == linked["project_id"] and config.get("api_base_url") == api:
            updated = _config(api, name, {"project_id": linked["project_id"], "revision": config.get("revision"),
                                         "snapshot_sha256": config.get("baseline_sha256")})
        write_hub_config(base, updated)
        success("hub.link", updated)


def cmd_hub_status(args):
    base = require_init()
    with workspace_write_lock(base, operation="hub.status"):
        config = load_hub(base)
        api = hub_api_base(base, args, config)
        success("hub.status", {"linked": config.get("format_version") == 2 and bool(config.get("project_id")),
            "api_base_url": api, "project_name": config.get("project_name") or base.parent.name,
            "project_id": config.get("project_id"), "revision": config.get("revision"),
            "credential_available": hub_auth_configured(api)})


def cmd_push(args):
    base = require_init()
    require_main(base)
    with workspace_write_lock(base, operation="push.preflight"):
        config, name, snapshot, digest = _state(base, args)
    api, remote = _remote(base, args, config, name)
    name, followed = _followed(name, remote)
    relation = _relation(config, snapshot, digest, remote)
    if relation in {"behind", "diverged"}:
        error("NON_FAST_FORWARD", "Remote history changed since this copy last synced.",
              details={"state": relation, "remote_revision": remote["revision"]},
              suggested_fix="Run `itt pull`, then push." if relation == "behind"
              else "Run `itt pull --rebase` to put local work on top of the remote, then `itt push`.")
    if args.dry_run:
        success("push", {"dry_run": True, "state": relation, "changed": relation == "ahead", "project_name": name, **followed})
        return
    with workspace_write_lock(base, operation="push"):
        current, _, _, current_hash = _state(base, args)
        if current != config or current_hash != digest:
            error("LOCAL_STATE_CHANGED", "Local history or remote configuration changed during preflight.")
        if relation in {"empty", "up_to_date"}:
            if relation == "up_to_date":
                write_hub_config(base, _config(api, name, remote))
            success("push", {"changed": False, "project_name": name, **followed, "revision": remote["revision"]})
            return
        token = hub_auth_token(base, args, api)
        if remote.get("project_id") is None:
            linked = _linked(http_json("POST", f"{api}/api/v2/link", {"project_name": name}, token), name)
            remote["project_id"] = linked["project_id"]
        # Save identity before upload; interrupted pushes retain the old baseline
        # and can reconcile by comparing the accepted snapshot on the next run.
        saved = _config(api, name, remote)
        write_hub_config(base, saved)
        parent = remote["revision"]
        revision = revision_id(parent, snapshot)
        result = http_json("POST", f"{api}/api/v2/history", {
            "project_name": name, "project_id": remote["project_id"],
            "parent": parent, "revision": revision, "snapshot": snapshot,
            "pusher": identity.author(), "repository": identity.repository()}, token)
        if (not isinstance(result, dict) or result.get("project_id") != remote["project_id"]
                or result.get("revision") != revision or result.get("snapshot_sha256") != digest):
            error("SERVER_ERROR", "Push response does not match the submitted revision; check status.")
        write_hub_config(base, _config(api, name, result))
        success("push", {**result, **followed})


def cmd_pull(args):
    base = require_init()
    require_main(base)
    with workspace_write_lock(base, operation="pull.preflight"):
        config, name, snapshot, digest = _state(base, args)
    api, remote = _remote(base, args, config, name)
    name, followed = _followed(name, remote)
    if remote["revision"] is None:
        error("SNAPSHOT_NOT_FOUND", "This remote project has no shared semantic history.")
    relation = _relation(config, snapshot, digest, remote)
    rebased = None
    if relation == "diverged":
        if not args.rebase:
            error("HISTORY_DIVERGED", "Both local and remote history changed. Neither was overwritten.",
                  details={"remote_revision": remote["revision"], "local_revision": config.get("revision")},
                  suggested_fix="Run `itt pull --rebase` to put local work on top of the remote, then `itt push`.")
        try:
            rebased, renumbered, conflicts = rebase_snapshot(snapshot, remote["snapshot"])
        except SnapshotError as exc:
            error("HISTORY_CONFLICT", str(exc), details={"remote_revision": remote["revision"]})
    if relation == "behind":
        try:
            require_fast_forward(snapshot, remote["snapshot"])
        except SnapshotError as exc:
            error("REMOTE_HISTORY_CONFLICT", str(exc))
    if args.dry_run:
        success("pull", {"dry_run": True, "changed": relation == "behind" or rebased is not None, "state": relation,
                         **({"renumbered": renumbered, "conflicts": conflicts} if rebased else {})})
        return
    with workspace_write_lock(base, operation="pull.apply"):
        current, _, _, current_hash = _state(base, args)
        if current != config or current_hash != digest:
            error("LOCAL_STATE_CHANGED", "Local history or configuration changed during download.")
        updated = _config(api, name, remote)
        if rebased:
            # The baseline is now the remote head, so what stays on top is an ordinary push.
            install_snapshot(base, rebased, updated)
            repo.commit_worktree(base, "pull.rebase", summary=f"Rebased onto {name}")
            success("pull", {"project_name": name, **followed, "project_id": remote["project_id"],
                "revision": remote["revision"], "changed": True, "state": "rebased",
                "renumbered": renumbered, "conflicts": conflicts,
                "counts": {k: len(v) for k, v in rebased.items()}})
            return
        if relation == "behind":
            install_snapshot(base, remote["snapshot"], updated)
            repo.commit_worktree(base, "pull", summary=f"Pulled from {name}")
        elif relation == "up_to_date" and updated != config:
            write_hub_config(base, updated)
        success("pull", {"project_name": name, **followed, "project_id": remote["project_id"],
            "revision": remote["revision"], "changed": relation == "behind", "state": relation,
            "counts": {k: len(v) for k, v in remote["snapshot"].items()}})
