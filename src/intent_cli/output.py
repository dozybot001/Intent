"""Output for Intent CLI: the JSON contract for agents and pipes, readable text for people.

JSON is used when stdout is not a terminal, when an agent host is detected
(agent shells may still allocate a terminal), or when `--json` or
ITT_FORMAT=json is given. ITT_FORMAT=text forces the readable format.
"""

import json
import os
import sys

# Host environments whose shells run agents, not people (see origin.py).
AGENT_ENVIRONMENT = (
    "CLAUDECODE",
    "CODEX_THREAD_ID",
    "CODEX_SHELL",
    "CODEX_CI",
    "CODEX_INTERNAL_ORIGINATOR_OVERRIDE",
)

_forced_format = None


def set_format(value):
    """Force "json" or "text" for this process (None restores detection)."""
    global _forced_format
    _forced_format = value


def json_mode():
    requested = _forced_format or os.getenv("ITT_FORMAT", "").strip().lower()
    if requested in {"json", "text"}:
        return requested == "json"
    if any(os.getenv(name) for name in AGENT_ENVIRONMENT):
        return True
    return not sys.stdout.isatty()


def emit_json(payload):
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def success(action, result, warnings=None):
    """Report a successful command."""
    warnings = warnings or []
    if json_mode():
        emit_json({"ok": True, "action": action, "result": result, "warnings": warnings})
        return
    from intent_cli.render import render_success

    text = render_success(action, result)
    if text:
        print(text)
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)


def error(code, message, details=None, suggested_fix=None):
    """Report an error and exit with status 1."""
    err = {"code": code, "message": message, "details": details or {}}
    if suggested_fix:
        err["suggested_fix"] = suggested_fix
    if json_mode():
        emit_json({"ok": False, "error": err})
    else:
        print(f"error: {message}", file=sys.stderr)
        usage = err["details"].get("usage") if isinstance(err["details"], dict) else None
        if usage:
            print(usage, file=sys.stderr)
        if suggested_fix:
            print(f"hint: {suggested_fix}", file=sys.stderr)
    sys.exit(1)
