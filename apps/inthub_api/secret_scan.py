"""Look for credentials before a project goes public.

History is append-only and a public page can be copied, so this is the last
cheap moment to notice one. It reports object IDs and kinds, never the value.
"""

import json
import re

PATTERNS = (
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})\b")),
    ("API key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("IntHub token", re.compile(r"\bith_(?:pat|ses|inv)_[A-Za-z0-9_-]{20,}\b")),
    ("password in a URL", re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@\"]+:[^/\s@\"]+@")),
)
REPORT_MAX = 20


def find_secrets(snapshot):
    found = []
    for collection in ("intents", "snaps", "decisions"):
        for obj in snapshot[collection]:
            text = json.dumps(obj, ensure_ascii=False)
            kinds = [name for name, pattern in PATTERNS if pattern.search(text)]
            if kinds:
                found.append({"id": obj["id"], "kinds": kinds})
    return found
