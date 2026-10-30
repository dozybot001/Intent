"""Test path bootstrap and a hermetic environment for source-tree execution."""

import os
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
for path in (REPO_ROOT, REPO_ROOT / "src"):
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


@pytest.fixture(autouse=True)
def _hermetic_environment(monkeypatch, tmp_path_factory):
    """Ignore the developer's IntHub tokens, Intent config and git settings."""
    for name in list(os.environ):
        if name.startswith(("INTHUB_", "ITT_", "INTENT_")) and name != "INTHUB_TEST_POSTGRES_URL":
            monkeypatch.delenv(name)
        # The agent running the suite must not choose hosts or output formats for it.
        if name == "CLAUDECODE" or name.startswith("CODEX_"):
            monkeypatch.delenv(name)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path_factory.mktemp("home")))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
