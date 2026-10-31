"""A command killed part way leaves the repository as if it never ran."""

import shutil
import sys

import pytest

from intent_cli import repo, repo_checkout
from intent_cli.cli import main
from intent_cli.commands import records
from intent_cli.store_errors import StoredObjectIntegrityError
from tests.cli_support import _run
from tests.repository_support import _conflicted_merge, _diverged, _linked, _snap, _snaps, goal, project  # noqa: F401


def test_a_merge_interrupted_while_writing_leaves_no_trace(project, goal, monkeypatch, capsys):
    _diverged(project, goal)
    _run(project, "switch", "side")
    _run(project, "intent", "create", "Only on side", "--why", "w")
    _run(project, "switch", "main")
    base = project / ".intent"
    head = repo.head_revision(base)
    write = repo_checkout.write_objects

    def die(target, objects):
        write(target, dict(list(objects.items())[:1]))
        raise KeyboardInterrupt

    monkeypatch.chdir(project)
    monkeypatch.setattr(repo_checkout, "write_objects", die)
    monkeypatch.setattr(sys, "argv", ["itt", "merge", "side"])
    with pytest.raises((KeyboardInterrupt, SystemExit)):
        main()
    capsys.readouterr()
    monkeypatch.undo()
    assert repo.uncommitted(base), "the interruption left a half-merged working copy"
    assert "merging" not in _run(project, "status", "--local")["result"]
    assert repo.uncommitted(base) == [] and repo.head_revision(base) == head
    assert _run(project, "merge", "side")["result"]["state"] == "merged"
    assert _run(project, "doctor")["result"]["healthy"] is True


def test_an_interrupted_abort_cannot_be_continued_into_a_revision(project, goal):
    _conflicted_merge(project, goal)
    assert _run(project, "resolve", goal, "--theirs")["ok"]
    base = project / ".intent"
    head = repo.head_revision(base)
    repo_checkout.begin_write(base)
    assert _run(project, "merge", "--continue")["error"]["code"] == "NO_MERGE_IN_PROGRESS"
    assert repo.head_revision(base) == head and repo.uncommitted(base) == []


def test_a_write_killed_part_way_records_nothing(project, goal, monkeypatch, capsys):
    base = project / ".intent"
    head = repo.head_revision(base)

    def die(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.chdir(project)
    monkeypatch.setattr(records, "update_object", die)
    monkeypatch.setattr(sys, "argv", ["itt", "snap", "create", "Half", "--intent", goal])
    with pytest.raises(SystemExit):
        main()
    capsys.readouterr()
    monkeypatch.undo()
    assert _run(project, "intent", "create", "Next", "--why", "w")["ok"]
    assert repo.read_revision(base, repo.head_revision(base))["parents"] == [head]
    assert _snaps(project) == [] and _run(project, "doctor")["result"]["healthy"] is True


def _kill_snap_create(project, goal, monkeypatch, capsys):
    def die(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.chdir(project)
    monkeypatch.setattr(records, "update_object", die)
    monkeypatch.setattr(sys, "argv", ["itt", "snap", "create", "Half", "--intent", goal])
    with pytest.raises(SystemExit):
        main()
    capsys.readouterr()
    monkeypatch.undo()


def test_a_second_kill_after_an_interrupted_migrate_loses_nothing(project, goal, monkeypatch, capsys):
    base = project / ".intent"
    for name in (repo.OBJECTS, repo.TREES, repo.REVISIONS, repo.REFS):
        shutil.rmtree(base / name)
    repo.create_repository(base)
    assert repo.head_revision(base) is None
    _kill_snap_create(project, goal, monkeypatch, capsys)
    assert _run(project, "show", goal)["ok"] and list((base / "snaps").glob("*.json")) == []


def test_a_kill_keeps_a_change_it_did_not_make(project, goal, monkeypatch, capsys):
    path = project / ".intent" / "intents" / f"{goal}.json"
    path.write_text(path.read_text().replace('"w"', '"edited"'))
    _kill_snap_create(project, goal, monkeypatch, capsys)
    assert _run(project, "status", "--local")["ok"] and '"edited"' in path.read_text()
    assert list((project / ".intent" / "snaps").glob("*.json")) == []


def test_a_write_refused_late_takes_back_what_it_wrote(project, goal):
    base = project / ".intent"
    path = base / "intents" / f"{goal}.json"
    edited = path.read_text().replace('"object": "intent"', '"object": "snap"')
    path.write_text(edited)
    assert _run(project, "snap", "create", "No", "--intent", goal)["ok"] is False
    assert list((base / "snaps").glob("*.json")) == [] and path.read_text() == edited


def test_a_refused_write_keeps_a_change_left_behind(project, goal):
    base = project / ".intent"
    path = base / "intents" / f"{goal}.json"
    path.write_text(path.read_text().replace('"w"', '"edited"'))
    assert _run(project, "snap", "create", "No", "--intent", "intent-999")["ok"] is False
    assert not (base / repo_checkout.WRITE_MARKER).exists() and '"edited"' in path.read_text()


def test_doctor_runs_even_when_recovery_cannot(project, goal):
    base = project / ".intent"
    version = next(iter(repo.tree_at(base, repo.head_revision(base)).values()))
    repo._content_path(base, repo.OBJECTS, version).write_text("{}")
    repo_checkout.begin_write(base)
    assert _run(project, "doctor")["result"]["healthy"] is False


def test_a_missing_head_is_reported_as_damage(project, goal):
    private = project / ".intent" / "worktrees" / "x"
    private.mkdir(parents=True)
    with pytest.raises(StoredObjectIntegrityError):
        repo.current_branch(private)


def test_an_interrupted_switch_goes_back_to_head(project, goal):
    _run(project, "branch", "other")
    only_main = _snap(project, goal, "Only on main")
    base = project / ".intent"
    repo_checkout.begin_write(base)
    repo_checkout.checkout(base, repo.branch_revision(base, "other"))
    after = _snap(project, goal, "After the move")
    assert repo.current_branch(base) == "main" and not (base / repo_checkout.WRITE_MARKER).exists()
    assert {only_main, after} <= set(_snaps(project))


def test_a_switch_interrupted_after_head_moved_stays_moved(project, goal):
    _run(project, "branch", "other")
    _snap(project, goal, "Only on main")
    base = project / ".intent"
    repo_checkout.begin_write(base)
    repo.set_head(base, "other")
    assert _run(project, "status", "--local")["result"]["branch"] == "other"
    assert repo.uncommitted(base) == []


def test_an_interrupted_fast_forward_keeps_one_branch_consistent(project, goal):
    _run(project, "switch", "-c", "ahead")
    _snap(project, goal, "Ahead")
    _run(project, "switch", "main")
    base = project / ".intent"
    head = repo.head_revision(base)
    repo_checkout.begin_write(base)
    repo_checkout.checkout(base, repo.branch_revision(base, "ahead"))
    assert _run(project, "status", "--local")["result"]["head"] == head
    assert repo.uncommitted(base) == []


def test_recovery_leaves_a_branch_another_worktree_moved_alone(project, goal, tmp_path_factory):
    linked = _linked(project, tmp_path_factory.mktemp("linked"), branch="other")
    base = project / ".intent"
    _snap(linked, goal, "Moved on")
    moved = repo.branch_revision(base, "other")
    repo_checkout.begin_write(base)
    assert _run(project, "status", "--local")["result"]["branch"] == "main"
    assert repo.branch_revision(base, "other") == moved


def test_a_damaged_branch_refuses_the_switch_and_stops_nothing_else(project, goal):
    _run(project, "switch", "-c", "side")
    _snap(project, goal, "Only on side")
    _run(project, "switch", "main")
    base = project / ".intent"
    ours, theirs = repo.tree_at(base, repo.head_revision(base)), repo.tree_at(base, repo.branch_revision(base, "side"))
    version = next(digest for obj_id, digest in theirs.items() if ours.get(obj_id) != digest)
    repo._content_path(base, repo.OBJECTS, version).write_text("{}")
    assert _run(project, "switch", "side")["ok"] is False
    assert not (base / repo_checkout.WRITE_MARKER).exists()
    assert _run(project, "status", "--local")["result"]["branch"] == "main"
    assert _run(project, "doctor")["result"]["healthy"] is False
    assert _snap(project, goal, "Still working")


def test_a_merge_recorded_before_its_cleanup_counts_as_finished(project, goal):
    _diverged(project, goal)
    assert _run(project, "merge", "side")["ok"]
    base = project / ".intent"
    head, theirs = repo.head_revision(base), repo.branch_revision(base, "side")
    repo_checkout.write_merge_state(base, {"branch": "side", "theirs": theirs, "base": None, "conflicts": []})
    assert _run(project, "merge", "--abort")["error"]["code"] == "NO_MERGE_IN_PROGRESS"
    assert repo.head_revision(base) == head and not (base / repo_checkout.MERGE_STATE).exists()
