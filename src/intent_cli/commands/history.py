"""The revision history: log, show, diff and migrate, read the way Git's are."""

from intent_cli import relations as relation_rules
from intent_cli import repo, repo_checkout
from intent_cli.commands.common import expand_ids, require_init
from intent_cli.hub.changes import semantic_changes, summarize
from intent_cli.output import error, success
from intent_cli.store import id_number, load_graph_once, validate_graph, validate_object_id, workspace_write_lock

OBJECT_KINDS = ("intent", "snap", "decision")


def _revision_entry(digest, revision):
    keys = ("parents", "author", "origin", "time", "summary", "changes")
    return {"revision": digest, **{key: revision.get(key) for key in keys}}


def _resolve(base, spec):
    try:
        return repo.resolve_revision(base, spec)
    except repo.UnknownRevisionError as exc:
        error("UNKNOWN_REVISION", str(exc), suggested_fix="itt log")


def _log_snaps(base, args):
    if args.intent is not None:
        validate_object_id("intent", args.intent)
    with workspace_write_lock(base, operation="log"):
        graph = load_graph_once(base)
    intents = graph["intent"]
    if args.intent is not None and args.intent not in intents:
        error("OBJECT_NOT_FOUND", f"Intent {args.intent} not found.")
    snaps = [snap for snap in graph["snap"].values() if args.intent in (None, snap.get("intent_id"))]
    snaps.sort(key=lambda snap: (snap.get("created_at", ""), id_number(snap["id"])), reverse=True)
    shown = snaps if args.all else snaps[:args.max_count]
    entries = []
    for snap in shown:
        intent = intents.get(snap.get("intent_id"))
        entries.append({**snap, "intent": {key: intent.get(key) for key in ("id", "what", "status")} if intent else None})
    success("log", {"snaps": entries, "total": len(snaps), "has_more": len(shown) < len(snaps)})


def _refs_by_revision(base, branch, head):
    """What points at each revision, as `git log --decorate` shows it."""
    refs = {head: [f"HEAD -> {branch}"]} if head else {}
    for name in repo.list_branches(base):
        if name != branch:
            refs.setdefault(repo.branch_revision(base, name), []).append(name)
    for name, tip in repo.remote_branches(base).items():
        refs.setdefault(tip, []).append(f"{repo.REMOTE}/{name}")
    return refs


def cmd_log(args):
    """List revisions newest first, like `git log`; --snaps or --intent lists checkpoints."""
    base = require_init()
    expand_ids(base, args)
    if args.max_count < 1:
        error("INVALID_INPUT", "-n must be a positive integer.")
    if args.snaps or args.intent is not None or not repo.is_repository(base):
        _log_snaps(base, args)
        return
    with workspace_write_lock(base, operation="log"):
        history = repo.walk(base)
        branch, head = repo.current_branch(base), repo.head_revision(base)
        refs = _refs_by_revision(base, branch, head)
    shown = history if args.all else history[:args.max_count]
    success("log", {"branch": branch, "head": head, "revisions": [_revision_entry(*item) for item in shown],
                    "refs": {digest: names for digest, names in refs.items() if digest in {item[0] for item in shown}},
                    "total": len(history), "has_more": len(shown) < len(history), "graph": args.graph})


def _show_revision(base, spec):
    digest = _resolve(base, spec)
    with workspace_write_lock(base, operation="show"):
        revision = repo.read_revision(base, digest)
        parent = revision["parents"][0] if revision["parents"] else None
        changes = semantic_changes(repo.snapshot_at(base, parent), repo.snapshot_at(base, digest))
    success("show", {**_revision_entry(digest, revision), "semantic_changes": changes})


def _show_object(base, args, kind):
    with workspace_write_lock(base, operation="show"):
        graph = load_graph_once(base)
    obj = graph[kind].get(args.id)
    if obj is None:
        error("OBJECT_NOT_FOUND", f"{args.id} not found.")
    summary = lambda item, *keys: {key: item.get(key) for key in ("id", *keys)}
    result = {"object": obj}
    if kind == "intent":
        result["snaps"] = [summary(graph["snap"][sid], "created_at", "what") for sid in obj.get("snap_ids", []) if sid in graph["snap"]]
        result["decisions"] = [summary(graph["decision"][did], "what", "status") for did in obj.get("decision_ids", []) if did in graph["decision"]]
        result["relations"] = relation_rules.view(graph["intent"], obj["id"])
    elif kind == "snap":
        intent = graph["intent"].get(obj.get("intent_id"))
        result["intent"] = summary(intent, "what", "status") if intent else None
    else:
        result["intents"] = [summary(graph["intent"][iid], "what", "status") for iid in obj.get("intent_ids", []) if iid in graph["intent"]]
        source = graph["intent"].get(obj.get("source_intent_id"))
        result["source_intent"] = summary(source, "what", "status") if source else None
    success("show", result)


def cmd_show(args):
    """Show one object with its relations, or one revision, like `git show`."""
    base = require_init()
    kind = args.id.split("-", 1)[0] if "-" in args.id else ""
    if kind in OBJECT_KINDS:
        expand_ids(base, args)
        _show_object(base, args, kind)
    elif repo.is_repository(base):
        _show_revision(base, args.id)
    else:
        error("INVALID_INPUT", f"{args.id!r} is not an object ID.", suggested_fix="Use an ID such as intent-001.")


def _diff_range(base, spec):
    if spec is None:
        head = _resolve(base, "HEAD")
        parents = repo.read_revision(base, head)["parents"]
        return (parents[0] if parents else None), head
    left, separator, right = spec.partition("..")
    return _resolve(base, left or "HEAD"), _resolve(base, right or "HEAD") if separator else _resolve(base, "HEAD")


def cmd_diff(args):
    """Compare two revisions in semantic terms, not lines of JSON."""
    base = require_init()
    if not repo.is_repository(base):
        error("REPOSITORY_NOT_MIGRATED", "This project has no revisions yet.", suggested_fix="itt migrate")
    before, after = _diff_range(base, args.range)
    with workspace_write_lock(base, operation="diff"):
        changes = semantic_changes(repo.snapshot_at(base, before), repo.snapshot_at(base, after))
    success("diff", {"from": before, "to": after, "changes": changes, "summary": summarize(changes)})


def cmd_migrate(args):
    """Turn a 7.x workspace into a repository and keep a backup. A damaged one needs --force."""
    base = require_init()
    with workspace_write_lock(base, operation="migrate"):
        if repo.is_repository(base):
            success("migrate", {"migrated": False, "branch": repo.current_branch(base), "head": repo.head_revision(base)})
            return
        graph = load_graph_once(base, tolerant=True)
        report = validate_graph(graph)
        if not report["healthy"] and not args.force:
            error("MIGRATION_BLOCKED", "This history has problems; nothing was changed.",
                  details={"issues": report["issues"]},
                  suggested_fix="Fix them, or run itt migrate --force to carry them over as they are.")
        revision, backup = repo_checkout.migrate(base)
        counts = {f"{kind}s": len(graph[kind]) for kind in OBJECT_KINDS}
        success("migrate", {"migrated": True, "branch": repo.current_branch(base), "head": revision,
                            "backup": str(backup), "counts": counts},
                [issue.get("message", "") for issue in report["issues"]])
