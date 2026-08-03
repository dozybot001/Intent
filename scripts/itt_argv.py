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
SAFE_PAYLOAD = re.compile(r"[A-Za-z0-9._~%\-]+")


def _error(code, message):
    print(
        json.dumps(
            {"ok": False, "error": {"code": code, "message": message, "details": {}}},
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
        )
    except OSError:
        _error("EXECUTION_FAILED", "The `itt` process could not be started.")
        return 1

    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.stdout:
        sys.stdout.write(result.stdout)
    else:
        _error("NON_JSON_OUTPUT", "The `itt` process returned no JSON output.")
    return result.returncode or (0 if result.stdout else 1)


if __name__ == "__main__":
    raise SystemExit(main())
