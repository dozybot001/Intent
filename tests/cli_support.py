"""Tests for Intent CLI — covers the command surface, state machines, and error codes."""

import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen

import pytest

from apps.inthub_api.server import make_handler as make_inthub_api_handler
from apps.inthub_web.server import make_handler as make_inthub_web_handler
from intent_cli import store as intent_store

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATHS = [str(REPO_ROOT), str(REPO_ROOT / "src")]


def _stored_intent(obj_id="intent-001"):
    return {
        "id": obj_id,
        "object": "intent",
        "created_at": "2026-08-02T00:00:00+00:00",
        "what": "Atomic fixture",
        "why": "Verify write semantics",
        "origin": "pytest",
        "status": "active",
        "decision_ids": [],
        "snap_ids": [],
    }


def _stored_snap(obj_id="snap-001", intent_id="intent-001"):
    return {
        "id": obj_id,
        "object": "snap",
        "created_at": "2026-08-02T00:01:00+00:00",
        "what": "Consistent checkpoint",
        "why": "Reader must see both sides of the relation",
        "origin": "pytest",
        "intent_id": intent_id,
    }


@pytest.fixture
def workspace(tmp_path):
    """Create a git repo with .intent/ initialized."""
    _init_git_repo(tmp_path)
    result = _run(tmp_path, "init")
    assert result["ok"] is True
    return tmp_path


@pytest.fixture
def inthub_server(tmp_path):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_inthub_api_handler(str(tmp_path / "inthub.db")),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


@pytest.fixture
def inthub_web_server(inthub_server):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_inthub_web_handler(api_base_url=inthub_server),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def _run(cwd, *args, extra_env=None):
    """Run itt command and return parsed JSON."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        SOURCE_PATHS + ([existing] if existing else [])
    )
    if extra_env:
        env.update(extra_env)
    r = subprocess.run(
        [sys.executable, "-m", "intent_cli", *args],
        cwd=cwd, capture_output=True, text=True, env=env,
    )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            "itt did not return JSON.\n"
            f"args={args}\n"
            f"returncode={r.returncode}\n"
            f"stdout={r.stdout!r}\n"
            f"stderr={r.stderr!r}"
        ) from exc


def _init_git_repo(cwd):
    """Create a hermetic test repository with repository-local author identity."""
    subprocess.run(["git", "init"], cwd=cwd, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Intent Tests"],
        cwd=cwd, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "intent-tests@example.invalid"],
        cwd=cwd, capture_output=True, check=True,
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=cwd, capture_output=True, check=True,
    )


def _add_github_remote(cwd, remote_url="git@github.com:example/demo.git"):
    subprocess.run(
        ["git", "remote", "add", "origin", remote_url],
        cwd=cwd, capture_output=True, check=True,
    )


def _get_json(url):
    with urlopen(url) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _global_auth_env(tmp_path):
    git_config = tmp_path / "auth-gitconfig"
    credential_file = tmp_path / "auth-credentials"
    subprocess.run(
        [
            "git",
            "config",
            "--file",
            str(git_config),
            "credential.helper",
            f"store --file={credential_file}",
        ],
        capture_output=True,
        check=True,
    )
    return {
        "GIT_CONFIG_GLOBAL": str(git_config),
        "GIT_CONFIG_NOSYSTEM": "1",
        "INTENT_CONFIG_HOME": str(tmp_path / "global-intent-config"),
    }


def _expected_cli_version():
    from importlib.metadata import version
    try:
        return version("intent-history")
    except Exception:
        from intent_cli import __version__
        return __version__
