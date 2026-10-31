"""Shared set-up for the protocol 3 tests: a local hub and copies that sync with it."""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from apps.inthub_api.common import APIError
from apps.inthub_api.server import build_server
from intent_cli import repo
from intent_cli.hub.pack import plan

ROOT = Path(__file__).resolve().parents[1]


def itt(directory, *args, **extra):
    env = dict(os.environ, PYTHONPATH=f"{ROOT / 'src'}{os.pathsep}{ROOT}", INTENT_CONFIG_HOME=str(directory.parent / "config"),
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", ITT_COUNTER_IDS="", **extra)
    env.pop("INTHUB_TOKEN", None)
    done = subprocess.run([sys.executable, "-m", "intent_cli", *args], cwd=directory, env=env, text=True, capture_output=True)
    return json.loads(done.stdout)


@pytest.fixture
def hub(tmp_path):
    db = str(tmp_path / "hub.db")
    server = build_server("127.0.0.1", 0, db)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield db, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def _copy(tmp_path, url, name):
    folder = tmp_path / name
    folder.mkdir()
    assert itt(folder, "init")["ok"]
    assert itt(folder, "remote", "add", "origin", url, "--project", "demo")["ok"]
    return folder


@pytest.fixture
def pushed(tmp_path, hub):
    """A copy that has pushed one goal with one Snap."""
    db, url = hub
    folder = _copy(tmp_path, url, "laptop")
    goal = itt(folder, "intent", "create", "Goal", "--why", "w")["result"]["id"]
    assert itt(folder, "snap", "create", "First step", "--intent", goal)["ok"]
    project_id = itt(folder, "push")["result"]["project_id"]
    return folder, goal, db, url, project_id


def _base(folder):
    return folder / ".intent"


def _blobs(base, tip, have=()):
    items = plan([tip], list(have), lambda digest: repo.read_revision(base, digest),
                 lambda digest, depth: repo.read_tree_node(base, digest, depth))
    return [{"kind": kind, "digest": digest, "body": repo.read_blob(base, kind, digest).decode()} for kind, digest in items]


def _code(call, *args, **kwargs):
    with pytest.raises(APIError) as failure:
        call(*args, **kwargs)
    return failure.value.code


def _local_commit(folder, goal, what):
    assert itt(folder, "snap", "create", what, "--intent", goal)["ok"]
    return repo.head_revision(_base(folder))
