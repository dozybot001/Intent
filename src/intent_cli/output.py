"""JSON output formatting for Intent CLI."""

import json
import sys


def success(action, result, warnings=None):
    """Print standard success JSON and return."""
    print(json.dumps({
        "ok": True,
        "action": action,
        "result": result,
        "warnings": warnings or [],
    }, indent=2, ensure_ascii=False))


def error(code, message, details=None, suggested_fix=None):
    """Print error JSON and exit with code 1."""
    err = {"code": code, "message": message, "details": details or {}}
    if suggested_fix:
        err["suggested_fix"] = suggested_fix
    print(json.dumps({"ok": False, "error": err}, indent=2, ensure_ascii=False))
    sys.exit(1)
