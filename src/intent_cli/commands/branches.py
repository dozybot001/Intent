"""Branches and switching between them, like `git branch` and `git switch`."""

from intent_cli import repo, repo_checkout
from intent_cli.commands.common import require_init, require_no_merge, require_repository
from intent_cli.output import error, success
from intent_cli.store import workspace_write_lock


def _require_valid(name):
    if not repo.valid_branch_name(name):
        error("INVALID_INPUT", f"{name!r} is not a valid branch name.")


def _require_new(base, name):
    if not repo.new_branch_name(name):
        error("INVALID_INPUT", f"{name!r} is not a valid branch name.")
    if repo.branch_revision(base, name) or name in repo_checkout.branches_in_use(base):
        error("BRANCH_EXISTS", f"Branch {name} already exists.", suggested_fix=f"itt switch {name}")
    blocker = repo.branch_conflict(base, name)
    if blocker:
        error("BRANCH_EXISTS", f"Branch {blocker} already exists, so {name} cannot.")


def _start_point(base, start):
    try:
        return repo.resolve_revision(base, start or "HEAD")
    except repo.UnknownRevisionError as exc:
        error("UNKNOWN_REVISION", str(exc), suggested_fix="Record something first, or name a revision.")


def _delete(base, name, force):
    _require_valid(name)
    if repo.branch_revision(base, name) is None:
        error("BRANCH_NOT_FOUND", f"Branch {name} does not exist.")
    used = repo_checkout.branches_in_use(base)
    if name in used:
        error("BRANCH_IN_USE", f"Branch {name} is open in {used[name]}.")
    reachable = {digest for digest, _revision in repo.walk(base)}
    if not force and repo.branch_revision(base, name) not in reachable:
        error("BRANCH_NOT_MERGED", f"Branch {name} has revisions that are not merged here.",
              suggested_fix=f"itt merge {name}, or itt branch -D {name} to drop them.")
    repo.delete_branch(base, name)
    success("branch", {"deleted": name})


def cmd_branch(args):
    """List branches, create one, or delete one."""
    base = require_init()
    require_repository(base)
    with workspace_write_lock(base, operation="branch"):
        if args.remotes:
            success("branch", {"remote": repo.REMOTE, "branches": [
                {"name": f"{repo.REMOTE}/{name}", "revision": tip} for name, tip in sorted(repo.remote_branches(base).items())]})
        elif args.delete or args.force_delete:
            _delete(base, args.delete or args.force_delete, bool(args.force_delete))
        elif args.name:
            _require_new(base, args.name)
            start = _start_point(base, args.start)
            repo.set_branch(base, args.name, start)
            success("branch", {"created": args.name, "revision": start})
        else:
            current, used = repo.current_branch(base), repo_checkout.branches_in_use(base)
            names = sorted({*repo.list_branches(base), current})
            success("branch", {"current": current, "branches": [
                {"name": name, "revision": repo.branch_revision(base, name), "current": name == current,
                 "open_in": None if name == current else used.get(name)} for name in names]})


def cmd_switch(args):
    """Move to a branch; the working copy follows. -c creates it first."""
    base = require_init()
    require_repository(base)
    with workspace_write_lock(base, operation="switch"):
        require_no_merge(base)
        _require_valid(args.branch)
        if args.create:
            _require_new(base, args.branch)
        elif repo.branch_revision(base, args.branch) is None and args.branch != repo.current_branch(base):
            error("BRANCH_NOT_FOUND", f"Branch {args.branch} does not exist.", suggested_fix=f"itt switch -c {args.branch}")
        used = repo_checkout.branches_in_use(base)
        if args.branch != repo.current_branch(base) and args.branch in used:
            error("BRANCH_IN_USE", f"Branch {args.branch} is open in {used[args.branch]}.")
        if repo.uncommitted(base) and not args.force:
            error("UNCOMMITTED_CHANGES", "The working copy has changes no revision holds.",
                  suggested_fix="Run a write to record them, or pass --force to discard them.")
        if args.create and repo.head_revision(base):
            repo.set_branch(base, args.branch, repo.head_revision(base))
        repo_checkout.switch(base, args.branch)
        success("switch", {"branch": args.branch, "head": repo.head_revision(base)})
