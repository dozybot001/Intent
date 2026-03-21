"""Infer snap origin (host / tool label) from the process environment.

The `itt` subprocess inherits env from its parent (IDE terminal, CI, etc.).
Override with ITT_ORIGIN or INTENT_ORIGIN.
"""

import os
import re


def _slugify_origin(value):
    """Normalize a host/tool label into a short stable slug."""
    text = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    return text.strip("-")


def detect_origin(environ=None):
    """Return a short stable label, or \"\" when unknown.

    Precedence:
    1. ITT_ORIGIN, then INTENT_ORIGIN (trimmed, non-empty)
    2. Built-in heuristics for common host environments
    """
    env = environ if environ is not None else os.environ

    for key in ("ITT_ORIGIN", "INTENT_ORIGIN"):
        raw = (env.get(key) or "").strip()
        if raw:
            return raw

    if env.get("CLAUDECODE"):
        return "claude-code"

    if env.get("CURSOR_TRACE_ID"):
        return "cursor"

    codex_originator = (env.get("CODEX_INTERNAL_ORIGINATOR_OVERRIDE") or "").strip()
    if codex_originator:
        return _slugify_origin(codex_originator)

    if env.get("CODEX_THREAD_ID") or env.get("CODEX_SHELL") or env.get("CODEX_CI"):
        return "codex"

    term = (env.get("TERM_PROGRAM") or "").lower()
    if term == "vscode":
        return "vscode"

    if env.get("CODESPACES") == "true":
        return "codespaces"

    if env.get("GITHUB_ACTIONS") == "true":
        return "github-actions"

    if env.get("GITPOD_WORKSPACE_ID"):
        return "gitpod"

    return ""
