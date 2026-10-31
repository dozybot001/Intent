"""Shared set-up for the repository tests."""

import subprocess

import pytest

from intent_cli import repo
from tests.cli_support import _init_git_repo, _run


@pytest.fixture
def project(tmp_path):
    _init_git_repo(tmp_path)
    assert _run(tmp_path, "init", "--host", "codex")["ok"]
    return tmp_path


@pytest.fixture
def goal(project):
    return _run(project, "intent", "create", "Shared goal", "--why", "w")["result"]["id"]


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=a@b.c", "-c", "user.name=a", *args], cwd=cwd, capture_output=True, check=True)


def _snap(project, goal, what):
    return _run(project, "snap", "create", what, "--intent", goal, extra_env={"ITT_COUNTER_IDS": ""})["result"]["id"]


def _snaps(project):
    return [item["id"] for item in _run(project, "log", "--snaps")["result"]["snaps"]]


def _linked(project, parent, branch="agent/fix"):
    (project / "file.txt").write_text("x")
    _git(project, "add", "file.txt")
    _git(project, "commit", "-m", "first")
    path = parent / "wt"
    _git(project, "worktree", "add", "-b", branch, str(path))
    return path


def _conflicted_merge(project, goal):
    other = _run(project, "intent", "create", "Second", "--why", "w")["result"]["id"]
    _run(project, "switch", "-c", "side")
    _run(project, "intent", "cancel", goal, "--reason", "dropped")
    _run(project, "switch", "main")
    _run(project, "intent", "done", goal)
    assert _run(project, "merge", "side")["error"]["code"] == "MERGE_CONFLICT"
    return other


def _diverged(project, goal):
    _run(project, "switch", "-c", "side")
    theirs = _snap(project, goal, "Theirs")
    _run(project, "switch", "main")
    return _snap(project, goal, "Ours"), theirs


def _store_revision(base, parents, when):
    return repo._store(base, repo.REVISIONS, {"parents": parents, "tree": repo._write_tree(base, {}), "time": when,
                                              "summary": when, "changes": []})
