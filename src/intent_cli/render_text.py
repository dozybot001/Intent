"""Terminal text: colour, wrapping and how a checkpoint reads."""

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
