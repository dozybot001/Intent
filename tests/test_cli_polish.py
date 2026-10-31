"""What a person and an agent read: clear output, the next step, and refusals that keep their code."""

import json
import os
import subprocess
import sys

import pytest

from apps.inthub_api.repository import read_refs
from apps.inthub_api.revisions import project_revisions
from intent_cli import maintenance_hooks, repo
from tests.protocol_support import ROOT, _base, _local_commit, hub, itt, pushed  # noqa: F401


def text(directory, *args):
    env = dict(os.environ, PYTHONPATH=f"{ROOT / 'src'}{os.pathsep}{ROOT}", INTENT_CONFIG_HOME=str(directory.parent / "config"),
               ITT_FORMAT="text", ITT_COUNTER_IDS="", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    env.pop("CLAUDECODE", None)
    done = subprocess.run([sys.executable, "-m", "intent_cli", *args], cwd=directory, env=env, text=True, capture_output=True)
    return done.stdout + done.stderr


@pytest.fixture
def clones(tmp_path, pushed):
    folder, goal, db, url, project_id = pushed
    other = tmp_path / "desktop"
    other.mkdir()
    assert itt(other, "clone", "demo", "--api-base-url", url)["ok"]
    return folder, other, goal, db, project_id


def _conflict(folder, other, goal):
    assert itt(other, "intent", "cancel", goal, "--reason", "dropped")["ok"]
    assert itt(other, "push")["ok"]
    assert itt(folder, "intent", "done", goal)["ok"]
    return itt(folder, "pull")["error"]


def test_remote_branches_read_as_a_list(clones):
    folder, other, goal, *_rest = clones
    assert itt(folder, "switch", "-c", "feature")["ok"]
    _local_commit(folder, goal, "Side")
    assert itt(folder, "push")["ok"]
    assert itt(other, "fetch")["ok"]
    assert "origin/feature" in text(other, "branch", "-r") and "remote:" not in text(other, "branch", "-r")


def test_hub_commands_read_as_sentences(pushed):
    folder, *_rest = pushed
    output = text(folder, "hub", "status")
    assert "Linked to" in output and "api_base_url:" not in output


def test_status_during_a_merge_tells_the_truth(clones):
    folder, other, goal, *_rest = clones
    _conflict(folder, other, goal)
    output = text(folder, "status")
    assert "No remote configured" not in output and "0 intents" not in output and "Merging" in output


def test_a_conflict_names_what_to_decide_and_how(clones):
    folder, other, goal, *_rest = clones
    refused = _conflict(folder, other, goal)
    assert goal in refused["message"] and "ours done, theirs cancelled" in refused["message"]
    assert f"itt resolve {goal}" in refused["suggested_fix"]
    assert "itt merge --continue" in text(folder, "resolve", goal, "--theirs")
    assert "itt push" in text(folder, "merge", "--continue")


def test_a_branch_only_the_remote_has_is_one_word_away(clones):
    folder, other, goal, *_rest = clones
    assert itt(folder, "switch", "-c", "feature")["ok"]
    tip = _local_commit(folder, goal, "Side")
    assert itt(folder, "push")["ok"]
    assert itt(other, "merge", "feature")["error"]["code"] == "UNKNOWN_REVISION"
    assert itt(other, "fetch")["ok"]
    assert itt(other, "merge", "feature")["error"]["suggested_fix"] == "itt merge origin/feature"
    assert itt(other, "switch", "feature")["result"]["head"] == tip
    assert itt(other, "switch", "-c", "copy", "origin/main")["ok"]
    assert itt(other, "switch", "again", "HEAD")["error"]["code"] == "INVALID_INPUT"


def test_pull_says_what_else_arrived(clones):
    folder, other, goal, *_rest = clones
    assert itt(folder, "switch", "-c", "feature")["ok"]
    _local_commit(folder, goal, "Side")
    assert itt(folder, "push")["ok"]
    assert itt(other, "pull")["result"]["fetched"] == ["origin/feature"]


def test_deleting_the_branch_you_are_on_says_so(pushed):
    folder, *_rest = pushed
    refused = itt(folder, "branch", "-d", "main")["error"]
    assert refused["code"] == "BRANCH_IN_USE" and refused["message"] == "You are on main."


def test_a_mistyped_short_id_is_not_found_rather_than_invalid(pushed):
    folder, *_rest = pushed
    refused = itt(folder, "show", "intent-0000000")["error"]
    assert refused["code"] == "OBJECT_NOT_FOUND" and "intent-0000000 not found" in refused["message"]


def test_a_mistyped_command_gets_a_suggestion(pushed):
    folder, *_rest = pushed
    refused = itt(folder, "statu")["error"]
    assert refused["message"] == "Unknown command 'statu'." and "itt status" in refused["suggested_fix"]


def test_inspect_says_where_this_copy_stands(clones):
    folder, other, goal, *_rest = clones
    assert itt(folder, "inspect")["branch"] == "main"
    _conflict(folder, other, goal)
    assert itt(folder, "inspect")["merging"]["branch"] == "origin/main"
    assert "Merging origin/main" in text(folder, "inspect")


def test_the_hook_context_warns_of_an_open_merge(clones):
    folder, other, goal, *_rest = clones
    _conflict(folder, other, goal)
    assert maintenance_hooks._place(_base(folder))["merging"]["conflicts"] == 1
    assert itt(folder, "merge", "--abort")["ok"]
    assert itt(folder, "switch", "-c", "feature")["ok"]
    assert maintenance_hooks._place(_base(folder)) == {"branch": "feature"}


def test_the_log_shows_what_points_where(clones):
    folder, _other, goal, *_rest = clones
    _local_commit(folder, goal, "Ahead")
    log = itt(folder, "log")["result"]
    assert log["refs"][log["head"]] == ["HEAD -> main"]
    assert "origin/main" in text(folder, "log") and "HEAD -> main" in text(folder, "log", "--graph")


def test_a_summary_names_the_new_object_alone(pushed):
    folder, goal, *_rest = pushed
    _local_commit(folder, goal, "Next")
    assert "more" not in repo.read_revision(_base(folder), repo.head_revision(_base(folder)))["summary"]


def test_status_counts_each_side(clones):
    folder, other, goal, *_rest = clones
    _local_commit(folder, goal, "One")
    _local_commit(folder, goal, "Two")
    assert itt(folder, "status")["result"]["ahead"] == 2
    assert "by 2 revisions" in text(folder, "status")
    assert itt(folder, "push")["result"]["revisions_sent"] == 2
    assert itt(other, "fetch")["ok"]
    assert itt(other, "status")["result"]["behind"] == 2


def test_a_lost_race_keeps_its_code_and_next_step(clones):
    folder, other, goal, *_rest = clones
    _local_commit(other, goal, "First in")
    assert itt(other, "push")["ok"]
    _local_commit(folder, goal, "Second")
    refused = itt(folder, "push")["error"]
    assert refused["code"] == "NON_FAST_FORWARD" and "itt pull" in refused["suggested_fix"]


def test_the_history_page_lists_branches_beside_main(pushed):
    folder, goal, db, _url, project_id = pushed
    assert itt(folder, "switch", "-c", "feature")["ok"]
    tip = _local_commit(folder, goal, "Side")
    assert itt(folder, "push")["ok"]
    assert project_revisions(db, project_id)["branches"] == [{"name": "feature", "revision": tip, "ahead": 1}]
    assert read_refs(db, "demo")["refs"]["feature"] == tip
