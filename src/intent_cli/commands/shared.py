"""What this copy knows of its remote: where it is, how its branches stand, and what status reports."""

import re
from urllib.parse import urlencode

from intent_cli import identity, repo
from intent_cli.commands.common import place, require_init, require_repository
from intent_cli.hub.client import http_json
from intent_cli.hub.credentials import normalize_api_base_url, GlobalHubConfigError
from intent_cli.hub.runtime import hub_api_base, hub_auth_token, hub_auth_configured, load_hub
from intent_cli.hub.snapshots import SnapshotError, validate_snapshot
from intent_cli.hub.versions import validate_project_ref, VERSION
from intent_cli.output import error, success
from intent_cli.store import SUBDIRS, load_graph_once, shared_root, workspace_write_lock, write_hub_config

FORMAT = 3
FORMATS = {2, FORMAT}  # 2 kept the last pushed revision, which still finds a merge base for a first pull


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
    name = getattr(args, "project", None) or config.get("project_name") or shared_root(base).parent.name
    try:
        validate_project_ref(name)
    except ValueError as exc:
        error("INVALID_INPUT", str(exc))
    if config.get("format_version") in FORMATS:
        if config.get("project_id") is not None and not _project_id(config["project_id"]):
            error("HUB_STATE_INVALID", "Invalid project ID in remote state.")
        if config.get("revision") is not None and not VERSION.fullmatch(str(config["revision"])):
            error("HUB_STATE_INVALID", "Invalid revision in remote state.")
        if getattr(args, "project", None) and name != config.get("project_name"):
            error("REMOTE_CHANGED", "Use itt remote add origin URL --project NAME to change the remote project.")
    graph = load_graph_once(base)
    snapshot = {collection: list(graph[kind].values()) for kind, collection in SUBDIRS.items()}
    try:
        validate_snapshot(snapshot)
    except SnapshotError as exc:
        error("INVALID_LOCAL_SNAPSHOT", str(exc))
    return config, name, snapshot


def _valid_refs(refs):
    return isinstance(refs, dict) and all(
        repo.new_branch_name(name) and isinstance(tip, str) and repo.DIGEST.fullmatch(tip)
        and repo.conflicting_ref(refs, name) is None for name, tip in refs.items())


def _remote(base, args, config, name):
    api = hub_api_base(base, args, config)
    if config.get("project_id") and api != config.get("api_base_url"):
        error("REMOTE_CHANGED", "Use itt remote add to explicitly select a different endpoint.")
    query = {"project": name}
    known = config.get("project_id") if not getattr(args, "project", None) else None
    if known:
        # IntHub finds the project by ID, so a rename made there is followed here.
        query["project_id"] = known
    if config.get("revision"):
        query["last_seen"] = config["revision"]
    result = http_json("GET", f"{api}/api/v3/refs?{urlencode(query)}", token=hub_auth_token(base, args, api))
    renamed = isinstance(result, dict) and bool(known) and result.get("project_id") == known and result.get("project_name") != name
    if renamed:
        try:
            validate_project_ref(result.get("project_name"))
        except ValueError:
            renamed = False
    if not isinstance(result, dict) or result.get("format_version") != FORMAT or (result.get("project_name") != name and not renamed):
        error("INVALID_REMOTE_HISTORY", "IntHub returned an inconsistent project identity or protocol.")
    last_seen = result.get("last_seen")
    if (not _valid_refs(result.get("refs")) or (result.get("project_id") is not None and not _project_id(result["project_id"]))
            or (result["refs"] and result.get("project_id") is None)
            or (last_seen is not None and not (isinstance(last_seen, str) and repo.DIGEST.fullmatch(last_seen)))):
        error("INVALID_REMOTE_HISTORY", "Remote refs are missing a valid identity or digest.")
    if config.get("project_id") and result.get("project_id") != config["project_id"]:
        error("REMOTE_CHANGED", "The remote project was deleted or replaced; inspect and explicitly relink it.",
              suggested_fix="If it was deleted on IntHub, run itt hub link, then itt push to publish this history again.")
    return api, result


def _identity_warning():
    return [] if identity.author() else [identity.MISSING]


def _followed(name, remote):
    """The remote's current name, and the old one when the project was renamed on IntHub."""
    return remote["project_name"], ({"renamed_from": name} if remote["project_name"] != name else {})


def _config(config, api, name, project_id, remote=None):
    """What hub.json keeps. A copy from before the graph also keeps the tip its last seen push became."""
    last_seen_tip = (remote or {}).get("last_seen") or config.get("last_seen_tip")
    return {"format_version": FORMAT, "api_base_url": api, "project_name": name, "project_id": project_id,
            **({"revision": config["revision"]} if config.get("revision") else {}),
            **({"last_seen_tip": last_seen_tip} if last_seen_tip else {})}


def _relation(base, branch, head, tip):
    """How this branch stands against the remote's. A tip not fetched yet can only be judged by where it was last seen."""
    if tip is None:
        return "ahead" if head else "empty"
    if tip == head:
        return "up_to_date"
    if head is None:
        return "behind"
    if tip in repo.reachable_from(base, [head]):
        return "ahead"
    seen = repo.remote_revision(base, branch)
    if seen == tip:
        return "behind" if head in repo.reachable_from(base, [tip]) else "diverged"
    return "behind" if seen == head else "diverged"


def _distance(base, head, tip, seen):
    """Revisions on each side, as `git status` counts them. Behind is known only for a tip fetched here."""
    if not head or not tip:
        return {}
    ours = repo.reachable_from(base, [head])
    theirs = repo.reachable_from(base, [tip]) if seen == tip else None
    known = theirs if theirs is not None else repo.reachable_from(base, [seen] if seen else [])
    return {"ahead": len(ours.keys() - known.keys()), **({"behind": len(theirs.keys() - ours.keys())} if theirs is not None else {})}


def cmd_status(args):
    base = require_init()
    with workspace_write_lock(base, operation="status"):
        where = place(base)
        if "merging" in where:  # a half-merged working copy need not form a valid snapshot
            config, kinds = load_hub(base), [obj_id.split("-", 1)[0] for obj_id in repo.working_objects(base)]
            success("status", {"project_name": config.get("project_name") or shared_root(base).parent.name, **where,
                               "remote_checked": False, "remote_configured": bool(config.get("api_base_url")), "local_changes": True,
                               "counts": {collection: kinds.count(kind) for kind, collection in SUBDIRS.items()}})
            return
        config, name, snapshot = _state(base, args)
        seen = repo.remote_revision(base, where["branch"]) if where else None
    # Never contact a service the user has not chosen: without a configured
    # remote (or an explicit --api-base-url), status stays local.
    counts = {k: len(v) for k, v in snapshot.items()}
    remote_configured = bool(config.get("api_base_url") or getattr(args, "api_base_url", None))
    if getattr(args, "local", False) or not remote_configured:
        success("status", {"project_name": name, **where, "remote_checked": False, "remote_configured": remote_configured,
            "local_changes": bool(where) and where["head"] != seen, "revision": seen, "counts": counts}, _identity_warning())
        return
    require_repository(base)
    api, remote = _remote(base, args, config, name)
    name, followed = _followed(name, remote)
    tip = remote["refs"].get(where["branch"])
    success("status", {"project_name": name, **where, **followed, "api_base_url": api, "remote_checked": True,
        "state": _relation(base, where["branch"], where["head"], tip), "revision": seen,
        **_distance(base, where["head"], tip, seen), "remote_revision": tip, "branches": remote["refs"], "counts": counts}, _identity_warning())


def cmd_remote(args):
    base = require_init()
    with workspace_write_lock(base, operation="remote"):
        config = load_hub(base)
        if args.sub == "add":
            if args.name != "origin":
                error("INVALID_INPUT", "The shared history supports one remote named origin.")
            api = normalize_api_base_url(args.url)
            name = args.project or shared_root(base).parent.name
            try:
                validate_project_ref(name)
            except ValueError as exc:
                error("INVALID_INPUT", str(exc))
            if config.get("format_version") in FORMATS and config.get("api_base_url") == api and config.get("project_name") == name:
                success("remote.add", {"name": "origin", "api_base_url": api, "project_name": name})
                return
            write_hub_config(base, {"format_version": FORMAT, "api_base_url": api, "project_name": name})
            success("remote.add", {"name": "origin", "api_base_url": api, "project_name": name})
        else:
            # Unconfigured projects report the default push target, marked as such.
            success("remote", {"name": "origin", "configured": bool(config.get("api_base_url")),
                "api_base_url": hub_api_base(base, args, config),
                "project_name": config.get("project_name") or shared_root(base).parent.name})


def cmd_link(args):
    """Compatibility alias for configuring/linking a shared project."""
    base = require_init()
    with workspace_write_lock(base, operation="link"):
        config, name, _snapshot = _state(base, args)
        name = args.project_name or name
        try:
            validate_project_ref(name)
        except ValueError as exc:
            error("INVALID_INPUT", str(exc))
        api = hub_api_base(base, args, config)
        linked = _linked(http_json("POST", f"{api}/api/v2/link", {"project_name": name}, hub_auth_token(base, args, api)), name)
        updated = _config(config, api, name, linked["project_id"])
        write_hub_config(base, updated)
        success("hub.link", updated)


def cmd_hub_status(args):
    base = require_init()
    with workspace_write_lock(base, operation="hub.status"):
        config = load_hub(base)
        api = hub_api_base(base, args, config)
        success("hub.status", {"linked": config.get("format_version") in FORMATS and bool(config.get("project_id")),
            "api_base_url": api, "project_name": config.get("project_name") or shared_root(base).parent.name,
            "project_id": config.get("project_id"),
            "revision": repo.remote_revision(base, repo.current_branch(base)) if repo.is_repository(base) else None,
            "credential_available": hub_auth_configured(api)})
