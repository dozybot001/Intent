"""Unit tests for snap origin environment detection."""

import pytest

from intent_cli.origin import detect_origin


@pytest.mark.parametrize(
    "environ, expected",
    [
        ({}, ""),
        ({"ITT_ORIGIN": "  my-tool  "}, "my-tool"),
        ({"INTENT_ORIGIN": "legacy-origin"}, "legacy-origin"),
        ({"ITT_ORIGIN": "a", "INTENT_ORIGIN": "b"}, "a"),
        ({"ITT_ORIGIN": "custom", "CURSOR_TRACE_ID": "x"}, "custom"),
        ({"CLAUDECODE": "1"}, "claude-code"),
        ({"CLAUDECODE": "1", "CURSOR_TRACE_ID": "x"}, "claude-code"),
        ({"CURSOR_TRACE_ID": "x"}, "cursor"),
        ({"CODEX_INTERNAL_ORIGINATOR_OVERRIDE": "Codex Desktop"}, "codex-desktop"),
        ({"CODEX_THREAD_ID": "abc"}, "codex"),
        ({"CODEX_SHELL": "1"}, "codex"),
        ({"CODEX_CI": "1"}, "codex"),
        ({"TERM_PROGRAM": "vscode"}, "vscode"),
        ({"TERM_PROGRAM": "VSCode"}, "vscode"),
        ({"CODESPACES": "true"}, "codespaces"),
        ({"GITHUB_ACTIONS": "true"}, "github-actions"),
        ({"GITPOD_WORKSPACE_ID": "ws1"}, "gitpod"),
    ],
)
def test_detect_origin(environ, expected):
    assert detect_origin(environ) == expected
