"""Readable terminal output for people. Agents and pipes get JSON (see output.py)."""

import os
import re
import shutil
import sys
import unicodedata
from datetime import datetime

CHECKPOINT_LABELS = (
    ("next", "Next"),
    ("blocker", "Blocker"),
    ("boundary", "Boundary"),
    ("verified", "Verified"),
    ("constraints", "Constraints"),
)
STATUS_WORDS = {"active": "active", "suspend": "suspended", "done": "done", "cancelled": "cancelled", "deprecated": "deprecated"}
# How a relation reads from the intent being shown: (type, direction) -> label.
RELATION_LABELS = {
    ("part_of", "out"): "Part of", ("part_of", "in"): "Part",
    ("derived_from", "out"): "Derived from", ("derived_from", "in"): "Spawned",
    ("succeeds", "out"): "Succeeds", ("succeeds", "in"): "Succeeded by",
    ("depends_on", "out"): "Depends on", ("depends_on", "in"): "Needed by",
    ("conflicts_with", "out"): "Conflicts", ("conflicts_with", "in"): "Conflicts",
}
RELATION_STATES = {
    "in_progress": "in progress", "done": "done", "dropped": "dropped", "orphaned": "parent has ended",
    "pending": "handover pending", "handed_over": "handed over", "blocked": "blocked", "satisfied": "satisfied",
    "broken": "dependency cancelled", "unresolved": "unresolved", "resolved": "resolved",
}
ATTENTION_STATES = {"orphaned", "pending", "blocked", "broken", "unresolved"}


def _color():
    return sys.stdout.isatty() and not os.getenv("NO_COLOR") and os.getenv("TERM") != "dumb"


def _style(code, text):
    return f"\033[{code}m{text}\033[0m" if _color() else text


def bold(text):
    return _style("1", text)


def dim(text):
    return _style("2", text)


def yellow(text):
    return _style("33", text)


def green(text):
    return _style("32", text)


def _width():
    return max(60, min(shutil.get_terminal_size((100, 24)).columns, 110))


def _when(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value or "")


def _cells(text):
    """Terminal columns: CJK and other wide characters take two."""
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text)


def _one_line(text, limit):
    text = " ".join(str(text or "").split())
    if _cells(text) <= limit:
        return text
    out, used = [], 1
    for char in text:
        used += _cells(char)
        if used > limit:
            break
        out.append(char)
    return "".join(out).rstrip() + "…"


def _fill(text, first_indent, next_indent):
    """Wrap by display width; ASCII words stay whole, CJK text breaks between characters."""
    tokens = re.findall(r"\s*(?:[\x21-\x7e]+|\S)", " ".join(str(text or "").split()))
    width = _width()
    lines, current, used, has_content = [], first_indent, _cells(first_indent), False
    for token in tokens:
        size = _cells(token)
        if has_content and used + size > width:
            lines.append(current.rstrip())
            token = token.lstrip()
            current, used = next_indent + token, _cells(next_indent) + _cells(token)
        else:
            if not has_content:
                token = token.lstrip()
                size = _cells(token)
            current, used = current + token, used + size
        has_content = True
    lines.append(current.rstrip())
    return "\n".join(lines)


def _wrap(text, indent):
    return _fill(text, indent, indent)


def _plural(count, noun):
    return f"{count} {noun}" + ("" if count == 1 else "s")


def _counts(counts):
    counts = counts or {}
    return " · ".join(_plural(counts.get(key, 0), noun) for key, noun in
                      (("intents", "intent"), ("snaps", "snap"), ("decisions", "decision")))


def _labelled(label, text, indent, style=dim):
    """One labelled field, wrapped under a fixed label column."""
    head = f"{indent}{label:<13}"
    body = _fill(text, head, " " * len(head))
    return indent + style(f"{label:<13}") + body[len(head):]


# Older Snaps carry the checkpoint as labelled prose; parse it the way IntHub does.
_MARKER = re.compile(
    r"(?:^|[\n\r.。；;])\s*(Verified(?: state)?|Boundary|Current(?: work)? boundary|Next(?: step)?|Blockers?|Constraints?"
    r"|已验证(?:到)?(?:的?状态)?|验证结果|当前状态|当前(?:真正的)?工作边界|当前边界|工作边界|边界|下一步|阻塞(?:项)?"
    r"|必须遵守(?:的约束)?|约束)\s*[:：]\s*",
    re.IGNORECASE,
)


def _marker_key(label):
    label = label.strip().lower()
    for key, pattern in (("verified", r"verified|已验证|验证结果|当前状态"), ("boundary", r"boundary|边界"),
                         ("next", r"^next|下一步"), ("blocker", r"blocker|阻塞"), ("constraints", r"constraint|约束|必须遵守")):
        if re.search(pattern, label):
            return key
    return None


def _prose_checkpoint(text):
    matches = list(_MARKER.finditer(str(text or "")))
    fields = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = text[match.end():end].strip(" \t\r\n.。；;")
        key = _marker_key(match.group(1))
        if key and value and key not in fields:
            fields[key] = value
    return fields


def checkpoint_of(snap):
    """Structured fields when recorded; otherwise parsed from labelled prose."""
    if not snap:
        return {}
    if snap.get("checkpoint"):
        return snap["checkpoint"]
    fields = _prose_checkpoint(snap.get("what", ""))
    for key, value in _prose_checkpoint(snap.get("why", "")).items():
        fields.setdefault(key, value)
    return fields


def snap_title(snap, limit=110):
    source = checkpoint_of(snap).get("verified") or snap.get("what") or snap.get("id", "")
    source = " ".join(str(source).split())
    stop = re.search(r"[。！？!?；;]", source)
    if stop and 16 <= stop.start() <= limit:
        source = source[: stop.start() + 1]
    return _one_line(source, limit)


def _checkpoint_lines(snap, indent):
    checkpoint = dict(checkpoint_of(snap))
    if checkpoint and snap and not checkpoint.get("verified"):
        # A Snap's WHAT is its verified milestone, as IntHub shows it.
        checkpoint["verified"] = snap.get("what", "")
    lines = []
    for key, label in CHECKPOINT_LABELS:
        value = checkpoint.get(key)
        if value:
            blocked = key == "blocker" and value.strip().lower().rstrip(".。") not in {"none", "n/a", "no blocker", "无", "暂无", "没有"}
            lines.append(_labelled(label, value, indent, yellow if blocked else dim))
    if not checkpoint and snap:
        lines.append(_labelled("Latest", _one_line(snap.get("what"), 400), indent))
    return lines


# ---- Views ----

def _inspect(result):
    lines = []
    active, suspended, decisions = result["active_intents"], result["suspended"], result["active_decisions"]
    if not active:
        lines += [dim("No active intent."), dim('  Start one with: itt intent create "Goal" --why "Reason"')]
    else:
        lines.append(bold("Active"))
    for intent in active:
        lines += _intent_block(intent)
    if suspended:
        lines += ["", bold("Suspended")]
        for intent in suspended:
            lines += _intent_block(intent)
    if decisions:
        lines += ["", bold("Decisions")]
        for decision in decisions:
            lines.append(f"  {decision['id']}  {_one_line(decision['what'], _width() - 18)}")
    if result.get("warnings"):
        lines += ["", yellow(f"{_plural(len(result['warnings']), 'warning')} — run `itt doctor` for details")]
    return lines


def _relation_line(row, indent):
    label = RELATION_LABELS.get((row["type"], row["direction"]), row["type"])
    other = row["intent"]
    text = f"{other['id']}  {_one_line(other.get('what'), _width() - 48)}"
    if row.get("state"):
        text += f" · {RELATION_STATES.get(row['state'], row['state'])}"
    return _labelled(label, text, indent, yellow if row.get("state") in ATTENTION_STATES else dim)


def _intent_block(intent):
    lines = [f"  {bold(intent['id'])}  {_one_line(intent['what'], _width() - 16)}"]
    snap = intent.get("latest_snap")
    # Where the goal sits, and only the relations someone has to act on.
    for row in intent.get("relations") or []:
        if (row["type"] in {"part_of", "derived_from"} and row["direction"] == "out") or row.get("state") in ATTENTION_STATES:
            lines.append(_relation_line(row, "              "))
    lines += _checkpoint_lines(snap, "              ")
    if snap:
        lines.append(dim(f"              {snap['id']} · {_when(snap.get('created_at'))} · {_plural(intent.get('snap_count', 0), 'snap')}"))
    else:
        lines.append(dim("              no snaps yet"))
    return lines


def _log(result):
    lines = []
    for snap in result["snaps"]:
        intent = snap.get("intent") or {}
        header = f"{yellow(snap['id'])}  {dim(_when(snap.get('created_at')))}  {intent.get('id', snap.get('intent_id', ''))}"
        if intent.get("what"):
            header += f"  {_one_line(intent['what'], 60)}"
        lines.append(header)
        lines.append(_wrap(snap_title(snap, 200), "    "))
        checkpoint = checkpoint_of(snap)
        if checkpoint.get("next"):
            lines.append(dim(_wrap(f"Next: {checkpoint['next']}", "    ")))
        lines.append("")
    if not result["snaps"]:
        lines.append(dim("No snaps recorded yet."))
    elif result.get("has_more"):
        lines.append(dim(f"… {result['total'] - len(result['snaps'])} older snaps (use -n or --all)"))
    return lines


def _show(result):
    obj = result["object"]
    kind = obj.get("object", "")
    meta = [STATUS_WORDS.get(obj.get("status"), obj.get("status")) if obj.get("status") else None,
            f"created {_when(obj.get('created_at'))}", obj.get("origin") or None]
    lines = [f"{bold(obj['id'])}  {dim(' · '.join(part for part in meta if part))}", _wrap(obj.get("what"), "")]
    if obj.get("why"):
        lines += ["", dim("Why"), _wrap(obj["why"], "  ")]
    if obj.get("reason"):
        lines += ["", dim("Reason"), _wrap(obj["reason"], "  ")]
    if kind == "snap":
        checkpoint_lines = _checkpoint_lines(obj, "  ") if checkpoint_of(obj) else []
        if checkpoint_lines:
            lines += ["", dim("Checkpoint")] + checkpoint_lines
        intent = result.get("intent")
        if intent:
            lines += ["", dim("Intent"), f"  {intent['id']}  {_one_line(intent['what'], _width() - 16)}"]
    if kind == "intent":
        lines += ["", dim(f"Snaps ({len(result.get('snaps', []))})")]
        lines += [f"  {snap['id']}  {dim(_when(snap.get('created_at')))}  {snap_title(snap, _width() - 32)}"
                  for snap in result.get("snaps", [])] or [dim("  none")]
        lines += ["", dim(f"Decisions ({len(result.get('decisions', []))})")]
        lines += [f"  {decision['id']}  {_one_line(decision.get('what'), _width() - 18)}"
                  for decision in result.get("decisions", [])] or [dim("  none")]
        relations = result.get("relations") or []
        if relations:
            lines += ["", dim(f"Relations ({len(relations)})")]
            lines += [_relation_line(row, "  ") for row in relations]
    if kind == "decision":
        source = result.get("source_intent")
        lines += ["", dim("From"), f"  {source['id']}  {_one_line(source.get('what'), _width() - 16)}" if source
                  else dim("  project level (no source intent)")]
        lines += ["", dim(f"Applies to ({len(result.get('intents', []))})")]
        lines += [f"  {intent['id']}  {_one_line(intent.get('what'), _width() - 16)}"
                  for intent in result.get("intents", [])] or [dim("  none")]
    return lines


def _status(result):
    if not result.get("remote_checked"):
        lines = [f"Project {bold(result['project_name'])} · {_counts(result.get('counts'))}"]
        if not result.get("remote_configured", True):
            lines.append("No remote configured; history stays on this machine.")
            lines.append(dim("  Back it up on IntHub: itt auth login, then itt push"))
            lines.append(dim("  Or use another IntHub: itt remote add origin URL --project NAME"))
        else:
            lines.append("Changes since the last sync." if result.get("local_changes") else "No changes since the last sync.")
        return lines
    messages = {
        "up_to_date": green("Up to date with origin."),
        "ahead": "Ahead of origin. Run `itt push` to publish your history.",
        "behind": "Origin has newer history. Run `itt pull` to update.",
        "diverged": yellow("Local history and origin have diverged; neither was changed."),
        "empty": "Local history and origin are both empty.",
    }
    return [f"Project {bold(result['project_name'])} on {result['api_base_url']} · {_counts(result.get('counts'))}",
            messages.get(result.get("state"), result.get("state", ""))]


def _push(result):
    if result.get("dry_run"):
        return [f"Dry run: origin is {result['state'].replace('_', ' ')}; "
                + ("a push would publish new history." if result.get("changed") else "nothing to push.")]
    if not result.get("changed"):
        return ["Everything up to date."]
    return [f"Pushed {result['project_name']} → revision {result['revision'][:8]}"]


def _pull(result):
    if result.get("dry_run"):
        return [f"Dry run: origin is {result['state'].replace('_', ' ')}; "
                + ("a pull would update local history." if result.get("changed") else "nothing to pull.")]
    if not result.get("changed"):
        return ["Already up to date."]
    return [f"Pulled {result['project_name']} revision {result['revision'][:8]} · {_counts(result.get('counts'))}"]


def _remote(result):
    if result.get("configured") is False:
        return [f"origin  not configured {dim('(itt push would use ' + result['api_base_url'] + ', project ' + result['project_name'] + ')')}"]
    return [f"origin  {result['api_base_url']}  {dim('project ' + result['project_name'])}"]


def _auth(action):
    def render(result):
        url = result["api_base_url"]
        if action == "auth.logout":
            return [f"Removed the stored token for {url}." if result.get("credential_removed") else f"No stored token for {url}."]
        if not result.get("authenticated"):
            return [f"Not signed in to {url}.", dim("  Create a token on the IntHub website, then run: itt auth login")]
        return [f"Signed in to {url} · {_plural(result.get('project_count', 0), 'project')}"]
    return render


def _hooks_line(hooks):
    if not hooks:
        return []
    state = "configured" if hooks.get("configured") else "not configured"
    line = f"Hooks ({hooks.get('host')}): {state}"
    if hooks.get("path"):
        line += dim(f"  {hooks['path']}")
    return [line]


HOST_NAMES = {"codex": "Codex", "claude-code": "Claude Code"}
TRUST_STEPS = {
    "codex": "In Codex, open /hooks and trust this project's two Intent hooks.",
    "claude-code": "In Claude Code, trust this folder, then confirm the two Intent hooks in /hooks "
                   "(restart the session if they are missing).",
}


def _next_steps(hooks):
    host = (hooks or {}).get("host")
    if host not in TRUST_STEPS:
        return []
    other = "claude-code" if host == "codex" else "codex"
    return ["", bold("Next"),
            f"  1. {TRUST_STEPS[host]}",
            "  2. Work as usual. The agent records goals and verified checkpoints as it goes.",
            '  3. Next time, tell the agent: "Resume this project through Intent."',
            dim(f"Also using {HOST_NAMES[other]} here? Run: itt maintenance on --host {other}")]


def _maintenance(action):
    def render(result):
        if action == "maintenance.close":
            objects = ", ".join(result.get("objects") or [])
            return [f"Turn closed: {result.get('outcome')}" + (f" ({objects})" if objects else "")]
        if action == "maintenance.status" and not result.get("initialized"):
            return [f"Intent is not initialized in {result['root']}.", dim("  Run: itt init")]
        enabled = "on" if result.get("enabled") else "off"
        lines = [f"Continuous maintenance is {bold(enabled)} for {result['root']}"] + _hooks_line(result.get("hooks"))
        if action == "maintenance.on" and (result.get("hooks") or {}).get("configured"):
            lines += _next_steps(result.get("hooks"))
        return lines
    return render


def _init(result):
    hooks = (result.get("maintenance") or {}).get("hooks") or {}
    project = os.path.basename(os.path.dirname(result["path"]))
    lines = [f"Initialized Intent for {bold(project)} {dim('(' + result['path'] + ')')}"]
    if hooks.get("configured"):
        lines.append(f"Recording is on for {HOST_NAMES.get(hooks.get('host'), hooks.get('host'))}; "
                     f"its hooks are in {os.path.relpath(hooks['path'], os.path.dirname(result['path'])) if hooks.get('path') else 'this project'}.")
        lines += _next_steps(hooks)
    else:
        lines += _hooks_line(hooks)
    return lines


def _created(result):
    return [f"Created {bold(result['id'])}: {_one_line(result.get('what'), _width() - 24)}"]


def _lifecycle(word):
    def render(result):
        line = f"{bold(result['id'])} is now {word}."
        if result.get("successor"):
            line += f" {bold(result['successor'])} carries it on."
        return [line]
    return render


def _related(result):
    relation = result["relation"]
    label = RELATION_LABELS.get((relation["type"], "out"), relation["type"]).lower()
    state = RELATION_STATES.get(relation.get("state"), relation.get("state"))
    return [f"{bold(result['id'])} {label} {bold(relation['intent'])}" + (f" ({state})." if state else ".")]


def _unrelated(result):
    relation = result["relation"]
    return [f"Withdrew {result['id']} {RELATION_LABELS.get((relation['type'], 'out'), relation['type']).lower()} {relation['intent']}."]


def _snap_created(result):
    return [f"Recorded {bold(result['id'])} on {result.get('intent_id')}: {_one_line(result.get('what'), _width() - 32)}"]


def _doctor(result):
    issues = result.get("issues") or []
    if result.get("healthy", not issues):
        return [green("History is healthy.")]
    return [yellow(f"{_plural(len(issues), 'problem')} found:")] + [
        f"  {issue.get('code')}  {issue.get('object', '')} {issue.get('id', '')}: {issue.get('message', '')}" for issue in issues
    ]


RENDERERS = {
    "version": lambda result: [f"itt {result['version']}"],
    "inspect": _inspect,
    "log": _log,
    "show": _show,
    "status": _status,
    "push": _push,
    "pull": _pull,
    "remote": _remote,
    "remote.add": lambda result: [f"origin → {result['api_base_url']}  {dim('project ' + result['project_name'])}"],
    "init": _init,
    "doctor": _doctor,
    "intent.create": _created,
    "decision.create": _created,
    "snap.create": _snap_created,
    "intent.activate": _lifecycle("active"),
    "intent.suspend": _lifecycle("suspended"),
    "intent.done": _lifecycle("done"),
    "intent.cancel": _lifecycle("cancelled"),
    "intent.relate": _related,
    "intent.unrelate": _unrelated,
    "decision.deprecate": _lifecycle("deprecated"),
    "auth.login": _auth("auth.login"),
    "auth.status": _auth("auth.status"),
    "auth.logout": _auth("auth.logout"),
    "maintenance.status": _maintenance("maintenance.status"),
    "maintenance.on": _maintenance("maintenance.on"),
    "maintenance.off": _maintenance("maintenance.off"),
    "maintenance.close": _maintenance("maintenance.close"),
}


def _generic(action, result):
    lines = [f"{action}: ok"]
    if isinstance(result, dict):
        for key, value in result.items():
            if isinstance(value, (str, int, float, bool)) or value is None:
                lines.append(f"  {key}: {value}")
    return lines


def render_success(action, result):
    renderer = RENDERERS.get(action)
    try:
        lines = renderer(result) if renderer else _generic(action, result)
    except (KeyError, TypeError, AttributeError):
        lines = _generic(action, result)
    return "\n".join(lines).rstrip()
