#!/usr/bin/env python3
"""Run one Intent CLI command from an RFC 3986 encoded JSON argv array.

This adapter exists for agent runtimes that expose only a shell-text command
runner.  Semantic text is decoded into an argv list and passed to ``itt`` with
``shell=False``; it is never evaluated as shell source.
"""

import json
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote


MAX_ENCODED_ARGV_BYTES = 256 * 1024
COMMAND_TIMEOUT_SECONDS = 60.0
SAFE_PAYLOAD = re.compile(r"[A-Za-z0-9._~%\-]+")
MUTATING_COMMANDS = {
    ("init",),
    ("push",),
    ("auth", "login"),
    ("auth", "logout"),
    ("hub", "link"),
    ("hub", "sync"),
    ("intent", "create"),
    ("intent", "activate"),
    ("intent", "suspend"),
    ("intent", "done"),
    ("intent", "cancel"),
    ("snap", "create"),
    ("decision", "create"),
    ("decision", "deprecate"),
}


def _error(code, message, details=None):
    print(
        json.dumps(
            {
                "ok": False,
                "error": {
                    "code": code,
                    "message": message,
                    "details": details or {},
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def decode_argv(encoded):
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("Encoded argv payload is required.")
    if len(encoded.encode("ascii", errors="ignore")) > MAX_ENCODED_ARGV_BYTES:
        raise ValueError("Encoded argv payload is too large.")
    if SAFE_PAYLOAD.fullmatch(encoded) is None:
        raise ValueError("Encoded argv payload contains shell-unsafe characters.")
    try:
        payload = json.loads(unquote(encoded, encoding="utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Encoded argv payload is not valid UTF-8 JSON.") from exc
    if not isinstance(payload, list) or not payload:
        raise ValueError("Decoded argv must be a non-empty JSON array.")
    if not all(isinstance(value, str) for value in payload):
        raise ValueError("Every decoded argv item must be a string.")
    return payload


def command_may_mutate(command_argv):
    """Classify timeout impact without reflecting semantic argv values."""
    return any(command_argv[:len(prefix)] == list(prefix) for prefix in MUTATING_COMMANDS)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        _error("INVALID_INPUT", "Usage: itt_argv.py <encoded-json-argv>")
        return 1
    try:
        command_argv = decode_argv(argv[0])
    except ValueError as exc:
        _error("INVALID_INPUT", str(exc))
        return 1

    executable = shutil.which("itt")
    if executable is None:
        _error("EXECUTABLE_NOT_FOUND", "The `itt` executable is not available on PATH.")
        return 1
    try:
        result = subprocess.run(
            [executable, *command_argv],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            shell=False,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        _error(
            "PROCESS_TIMEOUT",
            "The Intent CLI process exceeded the adapter safety timeout.",
            {
                "command": command_argv[:2],
                "timeout_seconds": COMMAND_TIMEOUT_SECONDS,
                "completion_unknown": command_may_mutate(command_argv),
            },
        )
        return 1
    except OSError:
        _error("EXECUTION_FAILED", "The `itt` process could not be started.")
        return 1

    try:
        output = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError):
        _error(
            "NON_JSON_OUTPUT",
            "The `itt` process did not return one valid JSON document.",
            {
                "command": command_argv[:2],
                "returncode": result.returncode,
                "stdout_length": len(result.stdout or ""),
                "stderr_length": len(result.stderr or ""),
            },
        )
        return 1

    if not isinstance(output, dict) or not isinstance(output.get("ok"), bool):
        _error(
            "INVALID_JSON_CONTRACT",
            "The `itt` process returned JSON without a boolean top-level `ok` field.",
            {
                "command": command_argv[:2],
                "returncode": result.returncode,
            },
        )
        return 1

    expected_returncode = 0 if output["ok"] else 1
    if result.returncode != expected_returncode:
        _error(
            "PROCESS_RESULT_MISMATCH",
            "The `itt` process exit status disagreed with its JSON result.",
            {
                "command": command_argv[:2],
                "returncode": result.returncode,
                "json_ok": output["ok"],
            },
        )
        return 1

    print(json.dumps(output, indent=2, ensure_ascii=False))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
