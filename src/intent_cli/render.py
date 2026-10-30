"""Readable terminal output for people. Agents and pipes get JSON (see output.py)."""

import os
from intent_cli.render_text import _checkpoint_lines, _counts, _labelled, _one_line, _plural, _when, _width, _wrap, bold, checkpoint_of, dim, green, snap_title, yellow

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


def _author(obj):
    author = obj.get("author") or {}
    return author.get("name") or author.get("email")


def _commit(obj):
    git = obj.get("git") or {}
    return git["commit"][:7] + ("-dirty" if git.get("dirty") else "") if git.get("commit") else None


def _show(result):
    obj = result["object"]
    kind = obj.get("object", "")
    meta = [STATUS_WORDS.get(obj.get("status"), obj.get("status")) if obj.get("status") else None,
            f"created {_when(obj.get('created_at'))}", _author(obj), obj.get("origin") or None, _commit(obj)]
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


def _renamed(result):
    old = result.get("renamed_from")
    return [dim(f"Renamed on IntHub: {old} → {result['project_name']}")] if old else []


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
        "diverged": yellow("Local history and origin have diverged; neither was changed. Run `itt pull --rebase`, then `itt push`."),
        "empty": "Local history and origin are both empty.",
    }
    return [f"Project {bold(result['project_name'])} on {result['api_base_url']} · {_counts(result.get('counts'))}",
            *_renamed(result), messages.get(result.get("state"), result.get("state", ""))]


DRY_RUN_STATES = {
    "ahead": "local history is ahead of origin",
    "behind": "origin has newer history",
    "up_to_date": "local history and origin match",
    "empty": "local history and origin are both empty",
    "diverged": "local history and origin have diverged",
}


def _push(result):
    if result.get("dry_run"):
        return [f"Dry run: {DRY_RUN_STATES[result['state']]}; "
                + ("a push would publish new history." if result.get("changed") else "nothing to push.")]
    if not result.get("changed"):
        return [*_renamed(result), "Everything up to date."]
    return [*_renamed(result), f"Pushed {result['project_name']} → revision {result['revision'][:8]}"]


def _rebased(result):
    renumbered = result.get("renumbered") or {}
    lines = [f"  {old} → {new}" for old, new in renumbered.items()]
    lines += [f"  {item['id']} stays {item['kept']} (this copy said {item['local']})" for item in result.get("conflicts") or []]
    return lines


def _pull(result):
    if result.get("dry_run"):
        if "renumbered" in result:
            return ["Dry run: a rebase would put local work on top of origin:", *_rebased(result)]
        return [f"Dry run: {DRY_RUN_STATES[result['state']]}; "
                + ("a pull would update local history." if result.get("changed") else "nothing to pull.")]
    if result.get("state") == "rebased":
        return [*_renamed(result), f"Rebased local work on revision {result['revision'][:8]} · {_counts(result.get('counts'))}",
                *_rebased(result), dim("  Run: itt push")]
    if not result.get("changed"):
        return [*_renamed(result), "Already up to date."]
    return [*_renamed(result), f"Pulled {result['project_name']} revision {result['revision'][:8]} · {_counts(result.get('counts'))}"]


def _remote(result):
    if result.get("configured") is False:
        return [f"origin  not configured {dim('(itt push would use ' + result['api_base_url'] + ', project ' + result['project_name'] + ')')}"]
    return [f"origin  {result['api_base_url']}  {dim('project ' + result['project_name'])}"]


def _auth(action):
    def render(result):
        url = result["api_base_url"]
        if action == "auth.logout":
            return [f"Removed the stored token for {url}." if result.get("credential_removed") else f"No stored token for {url}."]
        if action == "auth.login" and result.get("credential_store") == "file":
            return [f"Signed in to {url} · {_plural(result.get('project_count', 0), 'project')}",
                    dim(f"  No Git credential helper here, so the token is in {result['credential_path']}, readable only by you.")]
        if not result.get("authenticated"):
            return [f"Not signed in to {url}.", dim("  Sign in with: itt auth login")]
        return [f"Signed in to {url} · {_plural(result.get('project_count', 0), 'project')}"]
    return render


def _hooks_line(hooks, observations=None):
    if not hooks:
        return []
    state = "configured" if hooks.get("configured") else "not configured"
    if hooks.get("configured") and observations is not None:
        state += ", closure checked" if observations.get("stop_checked_receipt") else ", seen running" if observations.get("entry_seen") else ", not seen running yet"
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
        lines = [f"Continuous maintenance is {bold(enabled)} for {result['root']}"] + _hooks_line(result.get("hooks"), result.get("observations"))
        if action == "maintenance.on" and (result.get("hooks") or {}).get("configured"):
            lines += _next_steps(result.get("hooks"))
        return lines
    return render


def _init(result):
    hooks = (result.get("maintenance") or {}).get("hooks") or {}
    project = os.path.basename(os.path.dirname(result["path"]))
    lines = [f"Initialized Intent for {bold(project)} {dim('(' + result['path'] + ')')}"]
    author = result.get("author") or {}
    if author:
        who = f"{author['name']} <{author['email']}>" if len(author) > 1 else _author(result)
        lines.append(f"Recording as {who}.")
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
