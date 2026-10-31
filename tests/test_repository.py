"""The semantic repository: revisions, hash IDs, semantic diff and migration from Intent 7."""

import json
import os
import re
import shutil
import subprocess
import sys

import pytest

from intent_cli import repo
from intent_cli.store import AmbiguousObjectIdError, list_objects, resolve_object_id, validate_object_id
from tests.cli_support import SOURCE_PATHS, _init_git_repo, _run, inthub_server  # noqa: F401

HASHED = {"ITT_COUNTER_IDS": ""}
HASH_ID = re.compile(r"(intent|snap|decision)-[0-9a-f]{12}")


@pytest.fixture
def project(tmp_path):
    _init_git_repo(tmp_path)
    assert _run(tmp_path, "init", "--host", "codex")["ok"]
    return tmp_path


def _revisions(project):
    return _run(project, "log", "--all")["result"]["revisions"]


def _record(project, env=None):
    intent = _run(project, "intent", "create", "Ship it", "--why", "Users asked", extra_env=env)["result"]["id"]
    snap = _run(project, "snap", "create", "Tests pass", "--intent", intent, "--next", "Deploy", extra_env=env)["result"]["id"]
    decision = _run(project, "decision", "create", "One deploy path", "--why", "Simpler", extra_env=env)["result"]["id"]
    return intent, snap, decision


def _make_legacy(project):
    """Reduce a repository to what Intent 7 leaves on disk."""
    base = project / ".intent"
    (base / repo.HEAD_FILE).unlink()
    for name in (repo.OBJECTS, repo.TREES, repo.REVISIONS, repo.REFS):
        shutil.rmtree(base / name)


def test_init_starts_on_an_empty_main_branch(project):
    base = project / ".intent"
    assert (base / "HEAD").read_text() == "ref: refs/heads/main\n"
    assert repo.current_branch(base) == "main" and repo.head_revision(base) is None
    assert _revisions(project) == []


def test_every_write_is_one_revision_and_reads_add_none(project):
    intent, _snap, _decision = _record(project)
    history = _revisions(project)
    assert len(history) == 3
    assert [entry["parents"] for entry in history[:2]] == [[history[1]["revision"]], [history[2]["revision"]]]
    assert history[2]["parents"] == [] and history[2]["summary"].startswith(f"intent.create {intent}: Ship it")
    assert history[1]["author"]["name"] == "Intent Tests"
    assert {"id": "snap-001", "action": "added"} in history[1]["changes"]
    assert {"id": intent, "action": "changed"} in history[1]["changes"]
    _run(project, "inspect")
    _run(project, "status", "--local")
    assert len(_revisions(project)) == 3
    assert _run(project, "doctor")["result"]["healthy"] is True


def test_a_failed_write_records_nothing(project):
    _record(project)
    assert _run(project, "intent", "done", "intent-404")["ok"] is False
    assert len(_revisions(project)) == 3


def test_a_change_left_behind_goes_into_the_next_revision(project):
    intent, _snap, _decision = _record(project)
    path = project / ".intent" / "intents" / f"{intent}.json"
    edited = json.loads(path.read_text())
    edited["why"] = "Edited by hand"
    path.write_text(json.dumps(edited))
    assert any("differs from HEAD" in warning for warning in _run(project, "doctor")["warnings"])
    _run(project, "snap", "create", "More", "--intent", intent)
    assert {"id": intent, "action": "changed"} in _revisions(project)[0]["changes"]
    assert not _run(project, "doctor")["warnings"]


def test_new_objects_take_hash_ids_that_read_short_and_resolve_by_prefix(project):
    intent, snap, decision = _record(project, HASHED)
    assert HASH_ID.fullmatch(intent) and HASH_ID.fullmatch(snap) and HASH_ID.fullmatch(decision)
    assert validate_object_id("intent", intent) == intent
    assert _run(project, "show", intent[:11])["result"]["object"]["id"] == intent
    assert _run(project, "snap", "create", "Again", "--intent", intent[:12], extra_env=HASHED)["ok"]
    text = _run_text(project, "inspect")
    assert intent[:14] in text and intent not in text
    assert _run(project, "intent", "done", intent[:11])["result"]["id"] == intent


def _run_text(project, *args):
    environment = {**os.environ, "ITT_FORMAT": "text", "PYTHONPATH": os.pathsep.join(SOURCE_PATHS)}
    return subprocess.run([sys.executable, "-m", "intent_cli", *args], cwd=project,
                          capture_output=True, text=True, env=environment).stdout


def test_a_short_id_that_matches_two_objects_is_refused(project):
    base = project / ".intent"
    for suffix in ("abcd00000001", "abcd00000002"):
        (base / "intents" / f"intent-{suffix}.json").write_text("{}")
    with pytest.raises(AmbiguousObjectIdError, match="ambiguous"):
        resolve_object_id(base, "intent", "intent-abcd")
    assert _run(project, "show", "intent-abcd")["error"]["code"] == "INVALID_OBJECT_ID"


def test_hash_and_counter_ids_keep_their_order(project):
    _record(project)
    _record(project, HASHED)
    ids = [obj["id"] for obj in list_objects(project / ".intent", "intent")]
    assert ids[0] == "intent-001" and HASH_ID.fullmatch(ids[1])


def test_show_and_diff_speak_in_semantic_changes(project):
    intent, snap, decision = _record(project)
    _run(project, "intent", "done", intent)
    last = _run(project, "diff")["result"]
    assert last["changes"]["intents"]["changed"][0]["changes"][0] == {"field": "status", "from": "active", "to": "done"}
    assert last["summary"]["intents_changed"] == 1 and last["summary"]["snaps_added"] == 0
    whole = _run(project, "diff", "HEAD~3..HEAD")["result"]
    assert [obj["id"] for obj in whole["changes"]["snaps"]["added"]] == [snap]
    assert [obj["id"] for obj in whole["changes"]["decisions"]["added"]] == [decision]
    assert _run(project, "diff", "HEAD~1")["result"]["summary"] == last["summary"]
    head = _revisions(project)[0]["revision"]
    assert _run(project, "show", head[:8])["result"]["revision"] == head
    assert _run(project, "show", "main")["result"]["summary"].startswith("intent.done")
    first = _run(project, "show", "HEAD~3")["result"]
    assert first["parents"] == [] and [o["id"] for o in first["semantic_changes"]["intents"]["added"]] == [intent]


@pytest.mark.parametrize("spec", ["HEAD~9", "nonsense", "0000", "HEAD..nonsense"])
def test_unknown_revisions_are_refused(project, spec):
    _record(project)
    assert _run(project, "diff", spec)["error"]["code"] == "UNKNOWN_REVISION"


def test_doctor_finds_a_damaged_revision_or_object_version(project):
    _record(project)
    base = project / ".intent"
    head = repo.head_revision(base)
    version = next(iter(repo.tree_at(base, head).values()))
    repo._content_path(base, repo.OBJECTS, version).write_text("{}")
    report = _run(project, "doctor")["result"]
    assert report["healthy"] is False and report["issues"][0]["code"] == "OBJECT_VERSION_CORRUPT"
    repo._content_path(base, repo.REVISIONS, head).unlink()
    assert _run(project, "doctor")["result"]["issues"][0]["code"] == "REVISION_MISSING"


def test_an_intent_7_project_reads_but_must_migrate_before_writing(project):
    intent, snap, _decision = _record(project)
    _make_legacy(project)
    assert _run(project, "inspect")["ok"] and _run(project, "log")["result"]["snaps"][0]["id"] == snap
    refused = _run(project, "snap", "create", "No", "--intent", intent)
    assert refused["error"]["code"] == "REPOSITORY_NOT_MIGRATED" and refused["error"]["suggested_fix"] == "itt migrate"
    assert any("Intent 7" in warning for warning in _run(project, "doctor")["warnings"])


def test_migrate_keeps_every_object_and_backs_up_first(project):
    intent, snap, decision = _record(project)
    _make_legacy(project)
    before = {path.name: path.read_bytes() for path in (project / ".intent").rglob("*.json") if path.parent.name in ("intents", "snaps", "decisions")}
    migrated = _run(project, "migrate")["result"]
    assert migrated["migrated"] is True and migrated["counts"] == {"intents": 1, "snaps": 1, "decisions": 1}
    assert subprocess.run(["tar", "-tzf", migrated["backup"]], capture_output=True, text=True).stdout.count("intents/") >= 1
    after = {path.name: path.read_bytes() for path in (project / ".intent").rglob("*.json") if path.parent.name in ("intents", "snaps", "decisions")}
    assert after == before
    history = _revisions(project)
    assert len(history) == 1 and history[0]["summary"] == "Migrated from Intent 7"
    assert _run(project, "show", intent)["ok"]
    assert _run(project, "snap", "create", "After", "--intent", intent)["ok"]
    assert _run(project, "migrate")["result"]["migrated"] is False


def test_migrate_refuses_a_damaged_history_and_changes_nothing(project):
    _record(project)
    _make_legacy(project)
    (project / ".intent" / "snaps" / "snap-001.json").write_text("{broken")
    refused = _run(project, "migrate")
    assert refused["error"]["code"] == "MIGRATION_BLOCKED" and refused["error"]["details"]["issues"]
    assert not (project / ".intent" / "HEAD").exists()


def test_status_says_where_this_copy_stands(project):
    _record(project)
    status = _run(project, "status", "--local")["result"]
    assert status["branch"] == "main" and status["head"] == _revisions(project)[0]["revision"]


def test_hash_ids_travel_through_a_hub_and_a_pull_is_one_revision(project, tmp_path, inthub_server):  # noqa: F811
    intent, snap, _decision = _record(project, HASHED)
    assert _run(project, "remote", "add", "origin", inthub_server, "--project", "shared")["ok"]
    assert _run(project, "push")["ok"]
    other = tmp_path / "other"
    other.mkdir()
    _init_git_repo(other)
    assert _run(other, "init", "--host", "codex")["ok"]
    assert _run(other, "remote", "add", "origin", inthub_server, "--project", "shared")["ok"]
    pulled = _run(other, "pull")
    assert pulled["ok"] and pulled["result"]["state"] == "fast_forward"
    history = _revisions(other)
    assert history == _revisions(project), "a pull brings the revisions themselves"
    assert _run(other, "doctor")["result"]["healthy"] is True
    assert _run(other, "show", snap)["result"]["object"]["intent_id"] == intent
    assert _run(other, "snap", "create", "Next step", "--intent", intent[:11], extra_env=HASHED)["ok"]
    assert len(_revisions(other)) == len(history) + 1


def test_branches_keep_their_own_history_and_the_working_copy_follows(project):
    intent, _snap, _decision = _record(project)
    base_revision = _revisions(project)[0]["revision"]
    assert _run(project, "switch", "-c", "feature")["result"]["branch"] == "feature"
    extra = _run(project, "snap", "create", "On the branch", "--intent", intent)["result"]["id"]
    assert (project / ".intent" / "snaps" / f"{extra}.json").exists()
    listing = _run(project, "branch")["result"]
    assert listing["current"] == "feature" and [b["name"] for b in listing["branches"]] == ["feature", "main"]
    assert _run(project, "switch", "main")["result"]["head"] == base_revision
    assert not (project / ".intent" / "snaps" / f"{extra}.json").exists()
    assert extra not in [snap["id"] for snap in _run(project, "log", "--snaps")["result"]["snaps"]]
    assert _run(project, "branch", "-d", "feature")["error"]["code"] == "BRANCH_NOT_MERGED"
    assert _run(project, "branch", "-D", "feature")["result"]["deleted"] == "feature"
    assert _run(project, "switch", "feature")["error"]["code"] == "BRANCH_NOT_FOUND"


def test_branch_names_and_starts_are_checked(project):
    _record(project)
    assert _run(project, "branch", "../evil")["error"]["code"] == "INVALID_INPUT"
    assert _run(project, "branch", "older", "HEAD~1")["result"]["created"] == "older"
    assert _run(project, "branch", "older")["error"]["code"] == "BRANCH_EXISTS"
    assert _run(project, "show", "older")["result"]["summary"].startswith("snap.create")
    assert _run(project, "branch", "a/b")["ok"] and _run(project, "show", "a/b")["ok"]
    assert _run(project, "branch", "-d", "main")["error"]["code"] == "BRANCH_IN_USE"


def test_switching_refuses_to_lose_unrecorded_changes(project):
    intent, _snap, _decision = _record(project)
    _run(project, "branch", "other")
    path = project / ".intent" / "intents" / f"{intent}.json"
    path.write_text(path.read_text().replace("Users asked", "Edited"))
    assert _run(project, "switch", "other")["error"]["code"] == "UNCOMMITTED_CHANGES"
    assert _run(project, "switch", "other", "--force")["ok"]
    assert "Users asked" in path.read_text()


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, check=True)


def test_a_git_worktree_shares_the_history_with_its_own_branch_and_copy(project, tmp_path_factory):
    intent, snap, _decision = _record(project)
    (project / "file.txt").write_text("x")
    _git(project, "add", "file.txt")
    _git(project, "commit", "-m", "first")
    linked = tmp_path_factory.mktemp("linked") / "wt"
    _git(project, "worktree", "add", "-b", "agent/fix", str(linked))

    assert not (linked / ".intent").exists()
    assert _run(linked, "inspect")["active_intents"][0]["id"] == intent
    assert _run(linked, "status", "--local")["result"]["branch"] == "agent/fix"
    extra = _run(linked, "snap", "create", "From the worktree", "--intent", intent)["result"]["id"]

    main_view = _run(project, "log", "--snaps")["result"]["snaps"]
    assert extra not in [item["id"] for item in main_view] and snap in [item["id"] for item in main_view]
    assert _run(project, "status", "--local")["result"]["branch"] == "main"
    listing = {b["name"]: b for b in _run(project, "branch")["result"]["branches"]}
    assert listing["agent/fix"]["open_in"] == "wt" and listing["agent/fix"]["revision"]
    assert _run(project, "switch", "agent/fix")["error"]["code"] == "BRANCH_IN_USE"
    assert _run(linked, "switch", "main")["error"]["code"] == "BRANCH_IN_USE"
    assert _run(linked, "init")["error"]["code"] == "ALREADY_EXISTS"
    assert _run(linked, "doctor")["result"]["healthy"] is True

    _git(project, "worktree", "remove", "--force", str(linked))
    assert _run(project, "switch", "agent/fix")["ok"], "a removed worktree no longer holds its branch"
    assert extra in [item["id"] for item in _run(project, "log", "--snaps")["result"]["snaps"]]
