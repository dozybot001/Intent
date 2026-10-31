"""Merging branches, like `git merge`, with structured conflicts instead of text markers."""

from intent_cli import repo, repo_checkout
from intent_cli.commands.common import expand_ids, now_utc, require_init, require_repository
from intent_cli.merge import choose_relations, graph_conflicts, merge_objects, possible_duplicates
from intent_cli.output import error, success
from intent_cli.relations import graph_issues
from intent_cli.store import VALID_STATUSES, read_hub_config, workspace_write_lock


def _resolve_revision(base, name):
    try:
        return repo.resolve_revision(base, name)
    except repo.UnknownRevisionError as exc:
        error("UNKNOWN_REVISION", str(exc), suggested_fix="itt branch")


def _finish(base, state, objects):
    head = repo.head_revision(base)
    summary = f"Merged {state['branch']} into {repo.current_branch(base)}"
    revision = repo.commit_worktree(base, "merge", summary=summary, merge_parent=state["theirs"])
    repo_checkout.clear_merge_state(base)
    repo_checkout.end_write(base)
    duplicates = possible_duplicates(objects)
    return ({"state": "merged", "branch": state["branch"], "head": revision, "parents": [head, state["theirs"]],
             "possible_duplicates": duplicates},
            [f"These open goals read the same: {', '.join(ids)}. Close the extra with itt intent done ID --into OTHER."
             for ids in duplicates])


def _base_from_before_the_graph(base, theirs):
    """A copy from before the graph shares no revision with the remote, but IntHub told it where it last stood."""
    tip = (read_hub_config(base) or {}).get("last_seen_tip")
    return tip if tip and tip in repo.reachable_from(base, [theirs]) else None


def merge_into(base, name):
    """Merge a branch into this one. Returns (result, warnings); a conflict stops here with MERGE_CONFLICT."""
    if repo.uncommitted(base):
        error("UNCOMMITTED_CHANGES", "The working copy has changes no revision holds.",
              suggested_fix="Run a write to record them first.")
    head, theirs = repo.head_revision(base), _resolve_revision(base, name)
    if head is not None and repo.is_ancestor(base, theirs, head):
        return {"state": "up_to_date", "branch": name, "head": head}, []
    if head is None or repo.is_ancestor(base, head, theirs):
        repo_checkout.fast_forward(base, theirs)
        return {"state": "fast_forward", "branch": name, "head": theirs}, []
    ancestor = repo.merge_base(base, head, theirs) or _base_from_before_the_graph(base, theirs)
    ours_objects = repo.objects_at(base, head)
    merged, conflicts = merge_objects(repo.objects_at(base, ancestor), ours_objects, repo.objects_at(base, theirs))
    # Until the merge is recorded or stopped for a decision, an interruption goes back to HEAD,
    # so no half-merged working copy can reach a revision.
    state = {"branch": name, "theirs": theirs, "base": ancestor, "conflicts": conflicts}
    repo_checkout.begin_write(base)
    repo_checkout.write_objects(base, {obj_id: obj for obj_id, obj in merged.items() if ours_objects.get(obj_id) != obj})
    if not conflicts:
        return _finish(base, state, merged)
    repo_checkout.write_merge_state(base, state)
    repo_checkout.end_write(base)
    error("MERGE_CONFLICT", f"Merging {name} needs a decision on {len(conflicts)} field(s). Nothing is recorded yet.",
          details={"branch": name, "conflicts": conflicts},
          suggested_fix="itt resolve ID --ours|--theirs|--status S for each, then itt merge --continue, or itt merge --abort.")


def cmd_merge(args):
    """Merge a branch into this one, or carry on with one that stopped."""
    base = require_init()
    if not repo.is_repository(base):
        require_repository(base)
    with workspace_write_lock(base, operation="merge"):
        state = repo_checkout.read_merge_state(base)
        if args.abort or args.continue_merge:
            if state is None:
                error("NO_MERGE_IN_PROGRESS", "No merge is in progress.")
            if args.abort:
                repo_checkout.abort_merge(base)
                success("merge", {"state": "aborted", "branch": state["branch"], "head": repo.head_revision(base)})
                return
            objects = repo.working_objects(base)
            ours, theirs = repo.objects_at(base, repo.head_revision(base)), repo.objects_at(base, state["theirs"])
            state["conflicts"] = state["conflicts"] or graph_conflicts(objects, ours, theirs)
            if state["conflicts"]:
                repo_checkout.write_merge_state(base, state)
                error("MERGE_CONFLICT", f"{len(state['conflicts'])} field(s) still need a decision.",
                      details={"branch": state["branch"], "conflicts": state["conflicts"]},
                      suggested_fix="itt resolve ID --ours|--theirs|--status S")
            success("merge", *_finish(base, state, objects))
            return
        if state is not None:
            error("MERGE_IN_PROGRESS", f"A merge of {state['branch']} is in progress.",
                  suggested_fix="itt merge --continue or itt merge --abort")
        if not args.branch:
            error("INVALID_INPUT", "Name the branch to merge.", suggested_fix="itt merge BRANCH")
        success("merge", *merge_into(base, args.branch))


def _resolved_side(args, conflict, obj):
    """Which side's value settles a conflict, and the value itself."""
    if sum(map(bool, (args.ours, args.theirs, args.status))) != 1:
        error("INVALID_INPUT", "Choose exactly one way to resolve it.", suggested_fix="Pass --ours, --theirs or --status S.")
    if args.status:
        if conflict["field"] != "status":
            error("INVALID_INPUT", f"--status does not apply to {conflict['field']}.", suggested_fix="Use --ours or --theirs.")
        if args.status not in VALID_STATUSES[obj["object"]]:
            error("INVALID_INPUT", f"{args.status!r} is not a status of a {obj['object']}.")
        side = next((name for name in ("ours", "theirs") if conflict[name] == args.status), None)
        return side, args.status
    side = "ours" if args.ours else "theirs"
    return side, conflict[side]


def _settle(args, conflict, obj):
    side, value = _resolved_side(args, conflict, obj)
    if conflict["field"] == "relations":
        obj["relations"] = choose_relations(obj.get("relations") or [], value, now_utc())
        return
    obj[conflict["field"]] = value
    if "reasons" in conflict:
        reason = conflict["reasons"].get(side) if side else None
        obj.pop("reason", None)
        if reason is not None:
            obj["reason"] = reason


def cmd_resolve(args):
    """Settle the conflicts on one object during a merge."""
    base = require_init()
    expand_ids(base, args)
    with workspace_write_lock(base, operation="resolve"):
        state = repo_checkout.read_merge_state(base)
        if state is None:
            error("NO_MERGE_IN_PROGRESS", "No merge is in progress.")
        settled = [conflict for conflict in state["conflicts"] if conflict["id"] == args.id]
        if not settled:
            error("OBJECT_NOT_FOUND", f"{args.id} has no conflict in this merge.")
        objects = repo.working_objects(base)
        obj = objects.get(args.id)
        if obj is None:
            error("OBJECT_NOT_FOUND", f"{args.id} cannot be read from the working copy.", suggested_fix="itt merge --abort")
        for conflict in settled:
            _settle(args, conflict, obj)
        if any(conflict["field"] == "relations" for conflict in settled):
            intents = {obj_id: item for obj_id, item in objects.items() if obj_id.startswith("intent-")}
            remaining = next((message for obj_id, message in graph_issues(intents) if obj_id == args.id), None)
            if remaining:
                error("MERGE_CONFLICT", f"That side keeps the conflict: {remaining}", suggested_fix="Pick the other side.")
        repo_checkout.write_objects(base, {args.id: obj})
        state["conflicts"] = [conflict for conflict in state["conflicts"] if conflict["id"] != args.id]
        repo_checkout.write_merge_state(base, state)
        success("resolve", {"id": args.id, "fields": [conflict["field"] for conflict in settled],
                            "remaining": len(state["conflicts"])})
