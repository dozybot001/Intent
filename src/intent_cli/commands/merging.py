"""Merging branches, like `git merge`, with structured conflicts instead of text markers."""

from intent_cli import repo
from intent_cli.commands.common import expand_ids, require_init, require_repository
from intent_cli.merge import graph_conflicts, merge_objects, possible_duplicates
from intent_cli.output import error, success
from intent_cli.store import VALID_STATUSES, workspace_write_lock


def _resolve_revision(base, name):
    try:
        return repo.resolve_revision(base, name)
    except repo.UnknownRevisionError as exc:
        error("UNKNOWN_REVISION", str(exc), suggested_fix="itt branch")


def _finish(base, state, objects):
    head = repo.head_revision(base)
    summary = f"Merged {state['branch']} into {repo.current_branch(base)}"
    revision = repo.commit_worktree(base, "merge", summary=summary, merge_parent=state["theirs"])
    repo.clear_merge_state(base)
    duplicates = possible_duplicates(objects)
    success("merge", {"state": "merged", "branch": state["branch"], "head": revision, "parents": [head, state["theirs"]],
                      "possible_duplicates": duplicates},
            [f"These open goals read the same: {', '.join(ids)}. Close the extra with itt intent done ID --into OTHER."
             for ids in duplicates])


def _start(base, name):
    if repo.uncommitted(base):
        error("UNCOMMITTED_CHANGES", "The working copy has changes no revision holds.",
              suggested_fix="Run a write to record them first.")
    head, theirs = repo.head_revision(base), _resolve_revision(base, name)
    if head is None or repo.is_ancestor(base, head, theirs):
        repo.fast_forward(base, theirs)
        success("merge", {"state": "fast_forward", "branch": name, "head": theirs})
        return
    if repo.is_ancestor(base, theirs, head):
        success("merge", {"state": "up_to_date", "branch": name, "head": head})
        return
    ancestor = repo.merge_base(base, head, theirs)
    ours_objects = repo.objects_at(base, head)
    merged, conflicts = merge_objects(repo.objects_at(base, ancestor), ours_objects, repo.objects_at(base, theirs))
    repo.write_objects(base, {obj_id: obj for obj_id, obj in merged.items() if ours_objects.get(obj_id) != obj})
    state = {"branch": name, "theirs": theirs, "base": ancestor, "conflicts": conflicts}
    if not conflicts:
        _finish(base, state, merged)
        return
    repo.write_merge_state(base, state)
    error("MERGE_CONFLICT", f"Merging {name} needs a decision on {len(conflicts)} field(s). Nothing is recorded yet.",
          details={"branch": name, "conflicts": conflicts},
          suggested_fix="itt resolve ID --ours|--theirs|--status S for each, then itt merge --continue, or itt merge --abort.")


def cmd_merge(args):
    """Merge a branch into this one, or carry on with one that stopped."""
    base = require_init()
    if not repo.is_repository(base):
        require_repository(base)
    with workspace_write_lock(base, operation="merge"):
        state = repo.read_merge_state(base)
        if args.abort or args.continue_merge:
            if state is None:
                error("NO_MERGE_IN_PROGRESS", "No merge is in progress.")
            if args.abort:
                repo.checkout(base, repo.head_revision(base))
                repo.clear_merge_state(base)
                success("merge", {"state": "aborted", "branch": state["branch"], "head": repo.head_revision(base)})
                return
            objects = repo.working_objects(base)
            ours, theirs = repo.objects_at(base, repo.head_revision(base)), repo.objects_at(base, state["theirs"])
            state["conflicts"] = state["conflicts"] or graph_conflicts(objects, ours, theirs)
            if state["conflicts"]:
                repo.write_merge_state(base, state)
                error("MERGE_CONFLICT", f"{len(state['conflicts'])} field(s) still need a decision.",
                      details={"branch": state["branch"], "conflicts": state["conflicts"]},
                      suggested_fix="itt resolve ID --ours|--theirs|--status S")
            _finish(base, state, objects)
            return
        if state is not None:
            error("MERGE_IN_PROGRESS", f"A merge of {state['branch']} is in progress.",
                  suggested_fix="itt merge --continue or itt merge --abort")
        if not args.branch:
            error("INVALID_INPUT", "Name the branch to merge.", suggested_fix="itt merge BRANCH")
        _start(base, args.branch)


def _resolved_value(args, conflict, obj):
    if args.status:
        if conflict["field"] != "status":
            error("INVALID_INPUT", f"--status does not apply to {conflict['field']}.", suggested_fix="Use --ours or --theirs.")
        if args.status not in VALID_STATUSES[obj["object"]]:
            error("INVALID_INPUT", f"{args.status!r} is not a status of a {obj['object']}.")
        return args.status
    if not (args.ours or args.theirs):
        error("INVALID_INPUT", "Choose how to resolve it.", suggested_fix="Pass --ours, --theirs or --status S.")
    return conflict["ours" if args.ours else "theirs"]


def cmd_resolve(args):
    """Settle the conflicts on one object during a merge."""
    base = require_init()
    expand_ids(base, args)
    with workspace_write_lock(base, operation="resolve"):
        state = repo.read_merge_state(base)
        if state is None:
            error("NO_MERGE_IN_PROGRESS", "No merge is in progress.")
        settled = [conflict for conflict in state["conflicts"] if conflict["id"] == args.id]
        if not settled:
            error("OBJECT_NOT_FOUND", f"{args.id} has no conflict in this merge.")
        objects = repo.working_objects(base)
        obj = objects[args.id]
        for conflict in settled:
            obj[conflict["field"]] = _resolved_value(args, conflict, obj)
        repo.write_objects(base, {args.id: obj})
        state["conflicts"] = [conflict for conflict in state["conflicts"] if conflict["id"] != args.id]
        repo.write_merge_state(base, state)
        success("resolve", {"id": args.id, "fields": [conflict["field"] for conflict in settled],
                            "remaining": len(state["conflicts"])})
