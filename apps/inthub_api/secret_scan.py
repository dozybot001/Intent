"""Look for credentials before a project goes public.

History is append-only and a public page can be copied, so this is the last
cheap moment to notice one. It reports object IDs and kinds, never the value.

An object can hold 16 MB of text chosen by whoever pushed it, and matching holds
the interpreter, so every repeat here is bounded: an unbounded one can freeze the
whole service for hours.
"""

import re

PATTERNS = (
    ("private key", re.compile(r"-----BEGIN [A-Z ]{0,32}PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{40,255})\b")),
    ("API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,255}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,255}\b")),
    ("IntHub token", re.compile(r"\bith_(?:pat|ses|inv)_[A-Za-z0-9_-]{20,255}\b")),
    ("password in a URL", re.compile(r"\b[a-z][a-z0-9+.-]{0,31}://[^/\s:@\"]{1,255}:[^/\s@\"]{1,255}@")),
)
REPORT_MAX = 20


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def find_secrets(snapshot):
    found = []
    for collection in ("intents", "snaps", "decisions"):
        for obj in snapshot[collection]:
            kinds = [name for name, pattern in PATTERNS if any(pattern.search(text) for text in _strings(obj))]
            if kinds:
                found.append({"id": obj["id"], "kinds": kinds})
    return found
