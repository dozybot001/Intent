"""Semantic merge: unions by default, structured conflicts only where both sides disagree."""

import os
import subprocess
import sys

import pytest

from intent_cli.merge import merge_objects, possible_duplicates
from tests.cli_support import SOURCE_PATHS, _init_git_repo, _run


@pytest.fixture
def project(tmp_path):
    _init_git_repo(tmp_path)
    assert _run(tmp_path, "init", "--host", "codex")["ok"]
    intent = _run(tmp_path, "intent", "create", "Shared goal", "--why", "Both sides work on it")["result"]["id"]
    return tmp_path, intent


def _graph_of(project):
    environment = {**os.environ, "ITT_FORMAT": "text", "PYTHONPATH": os.pathsep.join(SOURCE_PATHS)}
    return subprocess.run([sys.executable, "-m", "intent_cli", "log", "--graph"], cwd=project,
                          capture_output=True, text=True, env=environment).stdout.splitlines()


def _head(project):
    return _run(project, "status", "--local")["result"]["head"]


def _intent(project, intent):
    return _run(project, "show", intent)["result"]["object"]


def _diverge(project, intent, ours, theirs):
    """Run commands on a new branch and on main, leaving the copy on main."""
    _run(project, "switch", "-c", "side")
    for command in theirs:
        assert _run(project, *command)["ok"], command
    _run(project, "switch", "main")
    for command in ours:
        assert _run(project, *command)["ok"], command


def test_a_branch_ahead_fast_forwards_and_a_branch_behind_changes_nothing(project):
    root, intent = project
    _run(root, "branch", "behind")
    _run(root, "switch", "-c", "ahead")
    _run(root, "snap", "create", "One", "--intent", intent)
    _run(root, "switch", "main")
    merged = _run(root, "merge", "ahead")["result"]
    assert merged["state"] == "fast_forward" and _head(root) == merged["head"]
    assert _intent(root, intent)["snap_ids"] == ["snap-001"]
    assert _run(root, "merge", "behind")["result"]["state"] == "up_to_date"
    assert _run(root, "branch", "-d", "ahead")["ok"]


def test_hash_ids_merge_into_one_history_with_two_parents(project):
    root, intent = project
    env = {"ITT_COUNTER_IDS": ""}
    before = _head(root)
    _run(root, "switch", "-c", "side")
    theirs = _run(root, "snap", "create", "From side", "--intent", intent, extra_env=env)["result"]["id"]
    side_head = _head(root)
    _run(root, "switch", "main")
    ours = _run(root, "snap", "create", "From main", "--intent", intent, extra_env=env)["result"]["id"]
    main_head = _head(root)
    merged = _run(root, "merge", "side")["result"]
    assert merged["state"] == "merged" and merged["parents"] == [main_head, side_head]
    assert _intent(root, intent)["snap_ids"] == [theirs, ours]
    log = _run(root, "log", "--all")["result"]["revisions"]
    assert log[0]["summary"] == "Merged side into main" and len(log[0]["parents"]) == 2 and len(log) == 4
    assert log[-1]["revision"] == before
    assert _run(root, "doctor")["result"]["healthy"] is True
    assert _run(root, "branch", "-d", "side")["ok"]
    assert _graph_of(root)[0].startswith("*") and any(line.startswith("| *") for line in _graph_of(root))


def test_a_status_changed_on_one_side_merges(project):
    root, intent = project
    env = {"ITT_COUNTER_IDS": ""}
    _run(root, "switch", "-c", "side")
    _run(root, "intent", "done", intent)
    _run(root, "switch", "main")
    _run(root, "decision", "create", "Rule", "--why", "w", extra_env=env)
    assert _run(root, "merge", "side")["result"]["state"] == "merged"
    assert _intent(root, intent)["status"] == "done"


def test_conflicting_status_stops_with_both_values_and_resolves(project):
    root, intent = project
    other = _run(root, "intent", "create", "Second", "--why", "w")["result"]["id"]
    _diverge(root, intent,
             ours=[("intent", "done", intent), ("intent", "done", other)],
             theirs=[("intent", "cancel", intent, "--reason", "dropped")])
    before = _head(root)
    stopped = _run(root, "merge", "side")
    assert stopped["error"]["code"] == "MERGE_CONFLICT"
    conflicts = stopped["error"]["details"]["conflicts"]
    assert {"id": intent, "field": "status", "ours": "done", "theirs": "cancelled", "base": "active"} in conflicts
    status = _run(root, "status", "--local")["result"]
    assert status["merging"]["branch"] == "side" and status["head"] == before
    assert _run(root, "snap", "create", "Blocked", "--intent", other)["error"]["code"] == "MERGE_IN_PROGRESS"
    assert _run(root, "merge", "--continue")["error"]["code"] == "MERGE_CONFLICT"
    assert _run(root, "merge", "other")["error"]["code"] == "MERGE_IN_PROGRESS"
    assert _run(root, "resolve", intent)["error"]["code"] == "INVALID_INPUT"
    assert _run(root, "resolve", intent, "--status", "bogus")["error"]["code"] == "INVALID_INPUT"
    assert _run(root, "resolve", intent, "--status", "cancelled")["ok"]
    assert _run(root, "merge", "--continue")["result"]["state"] == "merged"
    assert _intent(root, intent)["status"] == "cancelled" and _intent(root, intent)["reason"] == "dropped"
    assert "merging" not in _run(root, "status", "--local")["result"]
    assert _run(root, "doctor")["result"]["healthy"] is True


def test_abort_restores_the_branch_exactly(project):
    root, intent = project
    _diverge(root, intent, ours=[("intent", "done", intent)], theirs=[("intent", "cancel", intent, "--reason", "no")])
    head = _head(root)
    assert _run(root, "merge", "side")["error"]["code"] == "MERGE_CONFLICT"
    assert _run(root, "merge", "--abort")["result"]["state"] == "aborted"
    assert _head(root) == head and _intent(root, intent)["status"] == "done"
    assert _run(root, "merge", "--abort")["error"]["code"] == "NO_MERGE_IN_PROGRESS"
    assert not _run(root, "doctor")["warnings"]


@pytest.mark.parametrize(("flag", "expected"), [("--ours", "done"), ("--theirs", "cancelled")])
def test_ours_and_theirs_take_a_side(project, flag, expected):
    root, intent = project
    _diverge(root, intent, ours=[("intent", "done", intent)], theirs=[("intent", "cancel", intent, "--reason", "no")])
    _run(root, "merge", "side")
    assert _run(root, "resolve", intent[:11], flag)["result"]["remaining"] >= 0
    assert _run(root, "merge", "--continue")["ok"]
    assert _intent(root, intent)["status"] == expected


def test_a_merge_that_would_give_two_parents_is_a_conflict(project):
    root, intent = project
    one = _run(root, "intent", "create", "Parent one", "--why", "w")["result"]["id"]
    two = _run(root, "intent", "create", "Parent two", "--why", "w")["result"]["id"]
    _diverge(root, intent,
             ours=[("intent", "relate", intent, "--part-of", one)],
             theirs=[("intent", "relate", intent, "--part-of", two)])
    stopped = _run(root, "merge", "side")
    assert stopped["error"]["code"] == "MERGE_CONFLICT"
    conflict = next(item for item in stopped["error"]["details"]["conflicts"] if item["field"] == "relations")
    assert "more than one parent" in conflict["message"]
    assert _run(root, "resolve", conflict["id"], "--ours")["ok"]
    assert _run(root, "merge", "--continue")["result"]["state"] == "merged"
    assert [entry["intent"] for entry in _intent(root, intent)["relations"]] == [one]
    assert _run(root, "doctor")["result"]["healthy"] is True


def test_work_in_a_git_worktree_merges_back(project, tmp_path_factory):
    root, intent = project
    env = {"ITT_COUNTER_IDS": ""}
    (root / "f").write_text("x")
    subprocess.run(["git", "add", "f"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "f"], cwd=root, check=True, capture_output=True)
    linked = tmp_path_factory.mktemp("wt") / "agent"
    subprocess.run(["git", "worktree", "add", "-b", "agent/one", str(linked)], cwd=root, check=True, capture_output=True)
    snap = _run(linked, "snap", "create", "Done in the worktree", "--intent", intent, extra_env=env)["result"]["id"]
    assert snap not in _intent(root, intent)["snap_ids"]
    assert _run(root, "merge", "agent/one")["ok"]
    assert snap in _intent(root, intent)["snap_ids"]


def _object(obj_id, **fields):
    kind = obj_id.split("-")[0]
    links = {"intent": {"snap_ids": [], "decision_ids": []}, "decision": {"intent_ids": []}, "snap": {}}[kind]
    return {"id": obj_id, "object": kind, "created_at": "2026-10-01T00:00:00+00:00", "what": "w", "why": "y", **links, **fields}


def test_reason_conflicts_only_when_both_sides_set_it_differently():
    base = {"intent-1": _object("intent-1", status="active")}
    ours = {"intent-1": _object("intent-1", status="done", reason="a")}
    same = {"intent-1": _object("intent-1", status="done", reason="a")}
    assert merge_objects(base, ours, same)[1] == []
    other = {"intent-1": _object("intent-1", status="done", reason="b")}
    assert [item["field"] for item in merge_objects(base, ours, other)[1]] == ["reason"]


def test_a_withdrawal_on_either_side_wins():
    entry = {"type": "depends_on", "intent": "intent-2", "created_at": "t"}
    base = {"intent-1": _object("intent-1", status="active", relations=[entry]), "intent-2": _object("intent-2", status="active")}
    ours = {**base, "intent-1": _object("intent-1", status="active", relations=[{**entry, "removed_at": "t2"}])}
    theirs = {**base, "intent-1": _object("intent-1", status="active", relations=[entry], why="changed")}
    merged, conflicts = merge_objects(base, ours, theirs)
    assert conflicts == [] and merged["intent-1"]["relations"][0]["removed_at"] == "t2" and merged["intent-1"]["why"] == "changed"


def test_links_from_both_sides_read_oldest_first():
    snap = lambda obj_id, when: {"id": obj_id, "object": "snap", "created_at": when, "intent_id": "intent-1"}
    base = {"intent-1": _object("intent-1", status="active")}
    ours = {"intent-1": _object("intent-1", status="active", snap_ids=["snap-b"]), "snap-b": snap("snap-b", "2")}
    theirs = {"intent-1": _object("intent-1", status="active", snap_ids=["snap-a"]), "snap-a": snap("snap-a", "1")}
    assert merge_objects(base, ours, theirs)[0]["intent-1"]["snap_ids"] == ["snap-a", "snap-b"]


def test_same_goal_recorded_twice_is_flagged_only_while_open():
    objects = {"a": _object("intent-1", status="active", what="Add  Apple Pay"), "b": _object("intent-2", status="suspend", what="add apple pay"),
               "c": _object("intent-3", status="done", what="add apple pay")}
    objects = {obj["id"]: obj for obj in objects.values()}
    assert possible_duplicates(objects) == [["intent-1", "intent-2"]]
