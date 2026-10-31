"""Readable text for the revision history."""

from intent_cli.render_text import _one_line, _plural, _when, bold, dim, green, yellow

SHORT = 7
LABELS = {"intents": "Intent", "snaps": "Snap", "decisions": "Decision"}


def _author(revision):
    author = revision.get("author") or {}
    return author.get("name") or author.get("email")


def _heading(entry, marker=""):
    meta = [_when(entry.get("time")), _author(entry), entry.get("origin") or None]
    return f"{yellow(entry['revision'][:SHORT])}{marker}  {dim(' · '.join(part for part in meta if part))}"


def _graph(entries):
    """One line per revision with a lane per open line of history, like `git log --graph`."""
    lanes, lines = [], []
    for entry in entries:
        digest = entry["revision"]
        if digest not in lanes:
            lanes.append(digest)
        column = lanes.index(digest)
        row = " ".join("*" if index == column else "|" for index in range(len(lanes)))
        lines.append(f"{row}  {yellow(digest[:SHORT])}  {_one_line(entry.get('summary') or '', 72)}")
        parents = [parent for parent in entry["parents"] if parent not in lanes]
        lanes[column:column + 1] = parents
    return lines


def revisions(result):
    if result.get("graph") and result["revisions"]:
        return _graph(result["revisions"])
    lines = []
    for entry in result["revisions"]:
        marker = f" ({result['branch']})" if entry["revision"] == result.get("head") else ""
        lines += [_heading(entry, marker), f"    {_one_line(entry.get('summary') or '', 100)}", ""]
    if not result["revisions"]:
        lines.append(dim("No revisions yet."))
    elif result.get("has_more"):
        lines.append(dim(f"… {result['total'] - len(result['revisions'])} older revisions (use -n or --all)"))
    return lines


def _change_detail(change):
    if change["field"] == "status":
        reason = f" ({change['reason']})" if change.get("reason") else ""
        return f"{change['from']} → {change['to']}{reason}"
    return f"relation {change['action']}: {change['type']} {change['intent']}"


def semantic_lines(changes):
    lines = []
    for collection, label in LABELS.items():
        for obj in changes[collection]["added"]:
            lines.append(f"{green('+')} {obj['id']}  {_one_line(obj.get('what', ''), 80)}")
        for entry in changes[collection]["changed"]:
            lines.append(f"{yellow('~')} {entry['object']['id']}  {_one_line(entry['object'].get('what', ''), 60)}")
            lines += [f"    {_change_detail(change)}" for change in entry["changes"]]
    return lines or [dim("No semantic changes.")]


def show_revision(result):
    return [_heading(result), bold(result.get("summary") or ""), "", *semantic_lines(result["semantic_changes"])]


def diff(result):
    before = (result.get("from") or "start")[:SHORT]
    return [dim(f"{before}..{result['to'][:SHORT]}"), *semantic_lines(result["changes"])]


def migrate(result):
    if not result["migrated"]:
        return [f"Already a repository, on branch {bold(result['branch'])}."]
    counts = result["counts"]
    total = sum(counts.values())
    return [green(f"Migrated {_plural(total, 'object')} to branch {result['branch']}."),
            dim(f"Backup: {result['backup']}")]


def branch(result):
    if "created" in result:
        return [f"Created branch {bold(result['created'])} at {result['revision'][:SHORT]}"]
    if "deleted" in result:
        return [f"Deleted branch {bold(result['deleted'])}"]
    lines = []
    for entry in result["branches"]:
        revision = (entry["revision"] or "no revisions")[:SHORT]
        marker = "* " if entry["current"] else "  "
        place = f"  {dim('open in ' + entry['open_in'])}" if entry.get("open_in") else ""
        lines.append(f"{marker}{bold(entry['name']) if entry['current'] else entry['name']}  {dim(revision)}{place}")
    return lines


def place(result):
    if not result.get("branch"):
        return []
    lines = [f"On branch {bold(result['branch'])}"]
    merging = result.get("merging")
    if merging:
        lines.append(yellow(f"Merging {merging['branch']}: {_plural(len(merging['conflicts']), 'conflict')} left"))
        lines += [f"  {item['id']}  {item['field']}: ours {item.get('ours')}, theirs {item.get('theirs')}" for item in merging["conflicts"]]
    return lines


def merge(result):
    state = result["state"]
    if state == "up_to_date":
        return [f"Already up to date with {result['branch']}."]
    if state == "fast_forward":
        return [f"Fast-forwarded to {result['branch']} at {result['head'][:SHORT]}."]
    if state == "aborted":
        return [f"Gave up merging {result['branch']}."]
    return [green(f"Merged {result['branch']} at {result['head'][:SHORT]}.")]
