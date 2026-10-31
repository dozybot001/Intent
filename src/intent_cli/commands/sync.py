"""Git-like synchronization with IntHub: fetch, pull = fetch + merge, push, clone."""

import base64
import binascii
import json

from intent_cli import identity, repo
from intent_cli.commands.common import require_init, require_repository, require_settled
from intent_cli.commands.core import initialize
from intent_cli.commands.merging import merge_into
from intent_cli.commands.shared import _config, _followed, _linked, _relation, _remote, _state
from intent_cli.hub.client import http_json
from intent_cli.hub.pack import plan
from intent_cli.hub.runtime import hub_auth_token
from intent_cli.hub.snapshots import SnapshotError, validate_snapshot
from intent_cli.hub.versions import validate_project_ref
from intent_cli.output import error, success
from intent_cli.store import ensure_init, workspace_write_lock, write_hub_config

BATCH_BYTES = 6 * 1024 * 1024


def _complete_tips(base):
    """Revisions whose whole history is here: a fetch that died part way leaves blobs, but moves no ref."""
    branches = {repo.branch_revision(base, name) for name in repo.list_branches(base)}
    return sorted({*branches, *repo.remote_branches(base).values()})


def _reader(base):
    return (lambda digest: repo.read_revision(base, digest)), (lambda digest, depth: repo.read_tree_node(base, digest, depth))


def _download(base, api, remote, token):
    have = _complete_tips(base)
    want = sorted(set(remote["refs"].values()) - set(have))
    offset = 0
    while want and offset is not None:
        page = http_json("POST", f"{api}/api/v3/fetch",
                         {"project_id": remote["project_id"], "want": want, "have": have, "offset": offset}, token)
        try:
            for blob in page["blobs"]:
                raw = base64.b64decode(blob["body"], validate=True) if blob.get("binary") else blob["body"].encode("utf-8")
                repo.install_blob(base, blob["kind"], blob["digest"], raw)
            following = page["next_offset"]
        except (KeyError, TypeError, AttributeError, binascii.Error):
            error("INVALID_REMOTE_HISTORY", "IntHub returned a malformed page of history.")
        if following is not None and (type(following) is not int or following <= offset or not page["blobs"]):
            error("INVALID_REMOTE_HISTORY", "IntHub returned a page that does not move forward.")
        offset = following
    for kind, digest in plan(want, have, *_reader(base)):
        repo.read_blob(base, kind, digest)


def _fetch(base, api, remote, token):
    """Bring the remote's branches here. Tracking refs move only once all of it has arrived. Returns what moved."""
    _download(base, api, remote, token)
    with workspace_write_lock(base, operation="fetch"):
        before = repo.remote_branches(base)
        moved = sorted(name for name, tip in remote["refs"].items() if before.get(name) != tip)
        # Gone first: a deleted fix has to leave before a new fix/x can take its place.
        for name in before.keys() - remote["refs"].keys():
            repo.delete_remote_branch(base, name)
        for name, tip in remote["refs"].items():
            repo.set_remote_revision(base, name, tip)
    return moved


def _require_valid(base, tip):
    """Refuse a remote tip that could not be this copy's working state, before anything moves."""
    snapshot, tree = repo.snapshot_at(base, tip), repo.tree_at(base, tip)
    try:
        if repo.canonical_tree(tree) != repo.read_revision(base, tip)["tree"]:
            raise SnapshotError("That revision's tree is not the one its objects make.")
        if sum(map(len, snapshot.values())) != len(tree):
            raise SnapshotError("Some objects in this revision cannot be read.")
        validate_snapshot(snapshot)
    except SnapshotError as exc:
        error("INVALID_REMOTE_HISTORY", str(exc))
    return snapshot


def cmd_fetch(args):
    base = require_init()
    with workspace_write_lock(base, operation="fetch.preflight"):
        require_repository(base)
        config, name, _snapshot = _state(base, args)
    api, remote = _remote(base, args, config, name)
    name, followed = _followed(name, remote)
    if remote["project_id"] is None:
        error("SNAPSHOT_NOT_FOUND", "This remote project has no shared semantic history.")
    moved = _fetch(base, api, remote, hub_auth_token(base, args, api))
    with workspace_write_lock(base, operation="fetch.config"):
        write_hub_config(base, _config(config, api, name, remote["project_id"], remote))
    success("fetch", {"project_name": name, **followed, "project_id": remote["project_id"], "branches": remote["refs"], "updated": moved})


def _outgoing(kind, digest, raw):
    """A blob for the wire. A damaged file recorded long ago stays in history, so it travels as base64."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = None
    if text is None or "\0" in text:
        return {"kind": kind, "digest": digest, "body": base64.b64encode(raw).decode("ascii"), "binary": True}
    return {"kind": kind, "digest": digest, "body": text}


def _upload(base, api, remote, name, head, token):
    """Send what the remote lacks. Blobs mean nothing there until a ref moves, so a failure part way is harmless."""
    known = repo.reachable_from(base, _complete_tips(base))
    items = plan([head], [tip for tip in remote["refs"].values() if tip in known], *_reader(base))

    def send(blobs):
        http_json("POST", f"{api}/api/v3/upload", {"project_id": remote["project_id"], "project_name": name, "blobs": blobs}, token)

    batch, size = [], 0
    for kind, digest in items:
        blob = _outgoing(kind, digest, repo.read_blob(base, kind, digest))
        cost = len(json.dumps(blob))  # as the client encodes it: most non-ASCII text takes six bytes a character
        if batch and size + cost > BATCH_BYTES:
            send(batch)
            batch, size = [], 0
        batch.append(blob)
        size += cost
    if batch:
        send(batch)
    return sum(kind == "revision" for kind, _digest in items)


def _delete_remote(base, args, config, api, remote, name, followed):
    branch = args.delete
    if not repo.valid_branch_name(branch):
        error("INVALID_INPUT", f"{branch!r} is not a valid branch name.")
    tip = remote["refs"].get(branch)
    if tip is None:
        error("BRANCH_NOT_FOUND", f"The remote has no branch {branch}.")
    http_json("POST", f"{api}/api/v3/refs", {"project_id": remote["project_id"], "project_name": name, "ref": branch,
                                             "old": tip, "new": None}, hub_auth_token(base, args, api))
    with workspace_write_lock(base, operation="push.delete"):
        repo.delete_remote_branch(base, branch)
    success("push", {"project_name": name, **followed, "deleted": branch, "changed": True})


def cmd_push(args):
    base = require_init()
    with workspace_write_lock(base, operation="push.preflight"):
        require_settled(base)
        config, name, _snapshot = _state(base, args)
        branch, head = repo.current_branch(base), repo.head_revision(base)
        unrecorded = len(repo.uncommitted(base))
    api, remote = _remote(base, args, config, name)
    name, followed = _followed(name, remote)
    if getattr(args, "delete", None):
        _delete_remote(base, args, config, api, remote, name, followed)
        return
    tip = remote["refs"].get(branch)
    state = _relation(base, branch, head, tip)
    if state in {"behind", "diverged"}:
        error("NON_FAST_FORWARD", "Remote history changed since this copy last synced.",
              details={"state": state, "remote_revision": tip},
              suggested_fix="Run `itt pull`, then push." if state == "behind"
              else "Run `itt pull` to merge the remote, then `itt push`.")
    warnings = [f"{unrecorded} change(s) in the working copy are not in a revision, so they were not pushed."] if unrecorded else []
    if args.dry_run:
        success("push", {"dry_run": True, "state": state, "changed": state == "ahead", "project_name": name, "branch": branch, **followed}, warnings)
        return
    if state != "ahead":
        if tip:
            with workspace_write_lock(base, operation="push"):
                repo.set_remote_revision(base, branch, tip)
        success("push", {"changed": False, "project_name": name, "branch": branch, **followed, "revision": tip}, warnings)
        return
    token = hub_auth_token(base, args, api)
    if remote.get("project_id") is None:
        remote["project_id"] = _linked(http_json("POST", f"{api}/api/v2/link", {"project_name": name}, token), name)["project_id"]
    sent = _upload(base, api, remote, name, head, token)
    result = http_json("POST", f"{api}/api/v3/refs", {
        "project_name": name, "project_id": remote["project_id"], "ref": branch, "old": tip, "new": head,
        "pusher": identity.author(), "repository": identity.repository()}, token)
    if not isinstance(result, dict) or result.get("project_id") != remote["project_id"] or result.get("revision") != head:
        error("SERVER_ERROR", "Push response does not match the submitted revision; check status.")
    with workspace_write_lock(base, operation="push"):
        repo.set_remote_revision(base, branch, head)
        write_hub_config(base, _config(config, api, name, remote["project_id"]))
    success("push", {**result, **followed, "branch": branch, "revisions_sent": sent}, warnings)


def cmd_pull(args):
    """Fetch the remote, then merge its copy of this branch, as `git pull` does."""
    base = require_init()
    with workspace_write_lock(base, operation="pull.preflight"):
        require_settled(base)
        config, name, _snapshot = _state(base, args)
        branch, head = repo.current_branch(base), repo.head_revision(base)
    api, remote = _remote(base, args, config, name)
    name, followed = _followed(name, remote)
    tip = remote["refs"].get(branch)
    if tip is None:
        error("SNAPSHOT_NOT_FOUND", f"The remote has no history on {branch}.",
              suggested_fix="Run itt push to publish it." if head else "Check the project name with itt remote.")
    if args.dry_run:
        state = _relation(base, branch, head, tip)
        success("pull", {"dry_run": True, "changed": state in {"behind", "diverged"}, "state": state, "branch": branch})
        return
    moved = _fetch(base, api, remote, hub_auth_token(base, args, api))
    _require_valid(base, tip)
    with workspace_write_lock(base, operation="pull.apply"):
        require_settled(base)
        write_hub_config(base, _config(config, api, name, remote["project_id"], remote))
        result, warnings = merge_into(base, f"{repo.REMOTE}/{branch}")
    if getattr(args, "rebase", False):
        warnings = [*warnings, "pull merges now, so --rebase is no longer needed."]
    counts = {collection: len(objects) for collection, objects in repo.snapshot_at(base, result["head"]).items()}
    success("pull", {"project_name": name, **followed, "project_id": remote["project_id"], "branch": branch,
                     "revision": result["head"], "changed": result["state"] != "up_to_date", "state": result["state"],
                     "counts": counts, "fetched": [f"{repo.REMOTE}/{name}" for name in moved if name != branch]}, warnings)


def cmd_clone(args):
    """Start this folder's history from a project on IntHub."""
    if ensure_init() is not None:
        error("ALREADY_EXISTS", "Intent is already initialized here.", suggested_fix="Run itt pull to update it.")
    try:
        validate_project_ref(args.project)
    except ValueError as exc:
        error("INVALID_INPUT", str(exc))
    api, remote = _remote(None, args, {}, args.project)
    if not remote["refs"]:
        error("SNAPSHOT_NOT_FOUND", f"{args.project} has no shared semantic history, or you are not a member.")
    token = hub_auth_token(None, args, api)
    base, _setup, warnings = initialize(args.host)
    write_hub_config(base, _config({}, api, remote["project_name"], remote["project_id"]))
    _fetch(base, api, remote, token)
    with workspace_write_lock(base, operation="clone"):
        branch = repo.current_branch(base)
    if branch in remote["refs"]:
        _require_valid(base, remote["refs"][branch])
        with workspace_write_lock(base, operation="clone"):
            merge_into(base, f"{repo.REMOTE}/{branch}")
    success("clone", {"project_name": remote["project_name"], "project_id": remote["project_id"], "branch": branch,
                      "head": repo.head_revision(base), "branches": sorted(remote["refs"])}, warnings)
