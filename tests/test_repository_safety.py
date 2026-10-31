"""What a damaged or hostile repository must not be able to do."""

import pytest

from intent_cli import repo, repo_checkout
from intent_cli.hub.snapshots import SnapshotError, require_fast_forward
from intent_cli.merge import merge_objects
from intent_cli.store_errors import StoredObjectIntegrityError, UnsafeStoragePathError
from intent_cli.store_paths import is_linked, shared_root
from tests.cli_support import _init_git_repo, _run, inthub_server  # noqa: F401
from tests.repository_support import (  # noqa: F401
    _conflicted_merge, _diverged, _git, _linked, _snap, _snaps, _store_revision, goal, project,
)


def test_a_new_worktree_that_reuses_a_name_starts_clean(project, goal, tmp_path_factory):
    linked = _linked(project, tmp_path_factory.mktemp("linked"))
    left_behind = _snap(linked, goal, "Old worktree")
    _git(project, "worktree", "remove", "--force", str(linked))
    _git(project, "worktree", "add", "-b", "second", str(linked))
    assert _run(linked, "status", "--local")["result"]["branch"] == "second"
    assert left_behind not in _snaps(linked)


def test_a_worktree_keeps_its_work_across_commands(project, goal, tmp_path_factory):
    linked = _linked(project, tmp_path_factory.mktemp("linked"))
    work = _snap(linked, goal, "Keep me")
    assert work in _snaps(linked) and work in _snaps(linked / ".")


def test_branch_listing_stays_open_during_a_merge(project, goal):
    _conflicted_merge(project, goal)
    assert {item["name"] for item in _run(project, "branch")["result"]["branches"]} == {"main", "side"}
    assert _run(project, "switch", "side")["error"]["code"] == "MERGE_IN_PROGRESS"


def test_status_works_on_a_half_merged_copy(project, goal):
    _conflicted_merge(project, goal)
    (project / ".intent" / "intents" / f"{goal}.json").write_text("{broken")
    status = _run(project, "status", "--local")["result"]
    assert status["merging"]["branch"] == "side" and status["project_name"] == project.name


def test_resolving_a_status_takes_the_reason_of_that_side(project, goal):
    _conflicted_merge(project, goal)
    assert _run(project, "resolve", goal, "--theirs")["ok"]
    assert _run(project, "merge", "--continue")["ok"]
    resolved = _run(project, "show", goal)["result"]["object"]
    assert resolved["status"] == "cancelled" and resolved["reason"] == "dropped"


def test_resolve_takes_exactly_one_side(project, goal):
    _conflicted_merge(project, goal)
    assert _run(project, "resolve", goal, "--ours", "--theirs")["error"]["code"] == "INVALID_INPUT"


def test_a_merge_base_is_found_by_ancestry_not_by_clock(project):
    base = project / ".intent"
    root = _store_revision(base, [], "2030-01-01T00:00:00+00:00")
    middle = _store_revision(base, [root], "2020-01-01T00:00:00+00:00")
    one = _store_revision(base, [middle], "2020-01-02T00:00:00+00:00")
    other = _store_revision(base, [middle], "2020-01-03T00:00:00+00:00")
    assert repo.merge_base(base, one, other) == middle


def test_a_criss_cross_merge_starts_from_a_best_ancestor(project):
    base = project / ".intent"
    root = _store_revision(base, [], "2020-01-01T00:00:00+00:00")
    a = _store_revision(base, [root], "2020-01-02T00:00:00+00:00")
    b = _store_revision(base, [root], "2020-01-03T00:00:00+00:00")
    one = _store_revision(base, [a, b], "2020-01-04T00:00:00+00:00")
    other = _store_revision(base, [b, a], "2020-01-05T00:00:00+00:00")
    assert repo.merge_base(base, one, other) == b


def test_history_lists_children_before_parents_whatever_the_clocks_say(project):
    base = project / ".intent"
    parent = _store_revision(base, [], "2030-01-01T00:00:00+00:00")
    child = _store_revision(base, [parent], "2020-01-01T00:00:00+00:00")
    assert [digest for digest, _data in repo.walk(base, child)] == [child, parent]


@pytest.mark.parametrize("name", ["../evil", "a..b", ".hidden", "-flag", "a/.b", "x.lock", "dot.", "CON", "a/nul.txt", "a" * 64 + "/"])
def test_bad_branch_names_are_refused_everywhere(project, goal, name):
    for command in (("branch", name), ("switch", name), ("switch", "-c", name), ("branch", "-d", name), ("branch", "-D", name)):
        if name.startswith("-"):
            continue
        assert _run(project, *command)["error"]["code"] == "INVALID_INPUT", command


def test_a_branch_cannot_look_like_a_full_revision(project, goal):
    assert _run(project, "branch", "a" * 64)["error"]["code"] == "INVALID_INPUT"


def test_branch_names_may_use_any_language(project, goal):
    assert _run(project, "switch", "-c", "修复/登录")["ok"]
    _snap(project, goal, "Unicode branch")
    assert _run(project, "status", "--local")["result"]["branch"] == "修复/登录"
    assert _run(project, "show", "修复/登录")["ok"]


def test_a_branch_and_a_folder_of_branches_cannot_share_a_name(project, goal):
    assert _run(project, "branch", "a")["ok"]
    assert _run(project, "branch", "a/b")["error"]["code"] == "BRANCH_EXISTS"
    assert _run(project, "branch", "x/y")["ok"]
    assert _run(project, "branch", "x")["error"]["code"] == "BRANCH_EXISTS"
    assert _run(project, "branch", "-D", "x/y")["ok"]
    assert _run(project, "branch", "x")["ok"]


def test_a_refused_new_branch_leaves_nothing_behind(project, goal):
    path = project / ".intent" / "intents" / f"{goal}.json"
    path.write_text(path.read_text().replace('"w"', '"edited"'))
    assert _run(project, "switch", "-c", "fresh")["error"]["code"] == "UNCOMMITTED_CHANGES"
    assert "fresh" not in repo.list_branches(project / ".intent")


def test_merging_a_branch_into_itself_changes_nothing(project, goal):
    assert _run(project, "merge", "main")["result"]["state"] == "up_to_date"


def test_a_stored_head_or_ref_cannot_point_outside_the_repository(project, goal):
    base = project / ".intent"
    head = (base / "HEAD").read_text()
    (base / "HEAD").write_text("ref: refs/heads/../../../evil\n")
    with pytest.raises(StoredObjectIntegrityError):
        repo.current_branch(base)
    assert _run(project, "status", "--local")["ok"] is False
    (base / "HEAD").write_text(head)
    (base / "refs" / "heads" / "main").write_text("../../../../evil\n")
    with pytest.raises(StoredObjectIntegrityError):
        repo.head_revision(base)
    assert _run(project, "snap", "create", "No", "--intent", goal)["ok"] is False


def test_stored_content_must_match_its_digest(project, goal):
    base = project / ".intent"
    head = repo.head_revision(base)
    repo._content_path(base, repo.REVISIONS, head).write_text('{"parents": [], "tree": {}}')
    with pytest.raises(StoredObjectIntegrityError):
        repo.read_revision(base, head)


@pytest.mark.parametrize("revision", [
    [],
    {"parents": "x", "tree": "a" * 64},
    {"parents": ["../../evil"], "tree": "a" * 64},
    {"parents": [], "tree": "../../evil"},
    {"parents": [], "tree": {"intent-001": "a" * 64}},
])
def test_a_revision_of_the_wrong_shape_is_refused(project, revision):
    base = project / ".intent"
    with pytest.raises(StoredObjectIntegrityError):
        repo.read_revision(base, repo._store(base, repo.REVISIONS, revision))


@pytest.mark.parametrize("node", [[], {"intent-../../../evil": "a" * 64}, {"intent-001": "../../evil"}])
def test_a_tree_of_the_wrong_shape_is_refused(project, node):
    base = project / ".intent"
    with pytest.raises(StoredObjectIntegrityError):
        repo._tree_node(base, repo._store(base, repo.TREES, node), repo.TREE_DEPTH)


def test_symlinks_cannot_redirect_a_ref_or_a_version(project, goal, tmp_path_factory):
    base = project / ".intent"
    outside = tmp_path_factory.mktemp("outside")
    (base / "refs" / "heads" / "evil").symlink_to(outside)
    with pytest.raises(UnsafeStoragePathError):
        repo.set_branch(base, "evil/x", "a" * 64)
    digest = repo.head_revision(base)
    folder = base / repo.REVISIONS / "zz"
    folder.symlink_to(outside)
    with pytest.raises(UnsafeStoragePathError):
        repo.contained(base, repo.REVISIONS, "zz", "x.json")
    assert digest


@pytest.mark.parametrize("name,content", [
    (repo_checkout.MERGE_STATE, "[]"),
    (repo_checkout.MERGE_STATE, '{"branch": "x", "theirs": "../evil", "conflicts": []}'),
])
def test_damaged_merge_state_is_reported(project, name, content):
    (project / ".intent" / name).write_text(content)
    with pytest.raises(StoredObjectIntegrityError):
        repo_checkout.read_merge_state(project / ".intent")


def test_merged_links_keep_ours_first_so_a_push_still_fast_forwards():
    base = {"intent-1": {"id": "intent-1", "object": "intent", "status": "active", "snap_ids": ["snap-0"]}}
    ours = {"intent-1": {**base["intent-1"], "snap_ids": ["snap-0", "snap-z"]}}
    theirs = {"intent-1": {**base["intent-1"], "snap_ids": ["snap-0", "snap-a"]}}
    assert merge_objects(base, ours, theirs)[0]["intent-1"]["snap_ids"] == ["snap-0", "snap-z", "snap-a"]


def _intent(**fields):
    return {"id": "intent-1", "object": "intent", "what": "g", "status": "active", "snap_ids": [], "decision_ids": [],
            "relations": [], **fields}


def _shared(*intents):
    return {"intents": list(intents), "snaps": [], "decisions": []}


WITHDRAWN = {"type": "blocks", "intent": "intent-2", "created_at": "t", "removed_at": "t2"}
LIVE = {"type": "blocks", "intent": "intent-2", "created_at": "t"}


@pytest.mark.parametrize("old,new", [
    (dict(snap_ids=["a"]), dict(snap_ids=["b", "a"])),
    (dict(relations=[LIVE, {**LIVE, "intent": "intent-3"}]), dict(relations=[{**LIVE, "intent": "intent-3"}, LIVE])),
    (dict(relations=[WITHDRAWN]), dict(relations=[{**WITHDRAWN, "removed_at": "t1"}])),
    (dict(status="done"), dict(status="cancelled", reason="dropped")),
    (dict(status="done", reason="a"), dict(status="done", reason="b")),
])
def test_what_a_merge_can_produce_is_a_fast_forward(old, new):
    require_fast_forward(_shared(_intent(**old)), _shared(_intent(**new)))


@pytest.mark.parametrize("old,new", [
    (dict(snap_ids=["a", "b"]), dict(snap_ids=["a"])),
    (dict(relations=[LIVE]), dict(relations=[])),
    (dict(relations=[WITHDRAWN]), dict(relations=[LIVE])),
    (dict(status="done"), dict(status="active")),
    (dict(what="old"), dict(what="new")),
])
def test_losing_something_or_reopening_is_still_a_rewrite(old, new):
    with pytest.raises(SnapshotError):
        require_fast_forward(_shared(_intent(**old)), _shared(_intent(**new)))


def test_merging_a_pushed_main_both_ways_still_pushes(project, goal, inthub_server):  # noqa: F811
    assert _run(project, "remote", "add", "origin", inthub_server, "--project", "shared")["ok"]
    _snap(project, goal, "Pushed")
    assert _run(project, "push")["ok"]
    _run(project, "switch", "-c", "side")
    _snap(project, goal, "On side")
    _run(project, "switch", "main")
    _snap(project, goal, "On main")
    assert _run(project, "push")["ok"]
    _run(project, "switch", "side")
    assert _run(project, "merge", "main")["result"]["state"] == "merged"
    _run(project, "switch", "main")
    assert _run(project, "merge", "side")["result"]["state"] == "fast_forward"
    assert _run(project, "push")["ok"]
    assert _run(project, "status")["ok"] and _run(project, "doctor")["result"]["healthy"] is True


def test_the_latest_snap_is_the_newest_not_the_last_listed(project, goal):
    ours, theirs = _diverged(project, goal)
    assert _run(project, "merge", "side")["result"]["state"] == "merged"
    assert _run(project, "show", goal)["result"]["object"]["snap_ids"][-1] == theirs
    assert _run(project, "inspect")["active_intents"][0]["latest_snap"]["id"] == ours


def test_doctor_checks_every_branch_not_only_the_current_one(project, goal):
    _run(project, "switch", "-c", "side")
    _snap(project, goal, "Only on side")
    base = project / ".intent"
    side = repo.branch_revision(base, "side")
    _run(project, "switch", "main")
    repo._content_path(base, repo.REVISIONS, side).write_text("{}")
    assert _run(project, "doctor")["result"]["issues"][0]["code"] == "REVISION_CORRUPT"


def test_a_folder_named_worktrees_is_not_a_linked_worktree(tmp_path):
    assert not is_linked(tmp_path / "worktrees" / "project")
    assert not is_linked(tmp_path / "worktrees" / ".intent")
    assert shared_root(tmp_path / ".intent" / "worktrees" / "x") == tmp_path / ".intent"


def test_a_project_inside_a_worktrees_folder_works(tmp_path):
    root = tmp_path / "worktrees" / "project"
    root.mkdir(parents=True)
    _init_git_repo(root)
    assert _run(root, "init", "--host", "codex")["ok"]
    assert _run(root, "status", "--local")["result"]["branch"] == "main"


def test_a_linked_worktree_cannot_sync_and_names_the_project_after_main(project, goal, tmp_path_factory):
    linked = _linked(project, tmp_path_factory.mktemp("linked"))
    assert _run(linked, "push")["error"]["code"] == "NOT_ON_MAIN"
    assert _run(linked, "pull")["error"]["code"] == "NOT_ON_MAIN"
    assert _run(linked, "status", "--local")["result"]["project_name"] == project.name


def test_a_subfolder_of_a_linked_worktree_finds_it(project, goal, tmp_path_factory):
    linked = _linked(project, tmp_path_factory.mktemp("linked"))
    inner = linked / "a" / "b"
    inner.mkdir(parents=True)
    assert _run(inner, "status", "--local")["result"]["branch"] == "agent/fix"


def test_a_worktree_folder_outside_the_repository_is_never_touched(project, goal, tmp_path_factory):
    linked = _linked(project, tmp_path_factory.mktemp("linked"))
    outside = tmp_path_factory.mktemp("outside")
    (outside / "wt" / "precious").mkdir(parents=True)
    (project / ".intent" / "worktrees").symlink_to(outside)
    assert _run(linked, "status", "--local")["ok"] is False
    assert (outside / "wt" / "precious").is_dir()


def test_a_branch_open_but_unborn_in_a_worktree_cannot_be_taken(project, tmp_path_factory):
    linked = _linked(project, tmp_path_factory.mktemp("linked"), branch="wtb")
    assert _run(linked, "status", "--local")["result"]["branch"] == "wtb"
    _run(project, "intent", "create", "On main", "--why", "w")
    assert _run(project, "branch", "wtb")["error"]["code"] == "BRANCH_EXISTS"


def test_one_damaged_worktree_does_not_stop_the_others(project, goal, tmp_path_factory):
    linked = _linked(project, tmp_path_factory.mktemp("linked"))
    assert _run(linked, "status", "--local")["ok"]
    private = project / ".intent" / "worktrees" / "wt"
    (private / "HEAD").unlink()
    assert _run(project, "branch")["ok"]
    (private / repo_checkout.WORKTREE_TOKEN).write_bytes(b"\xff\xfe")
    assert _run(project, "branch")["ok"]


def test_hub_status_names_the_project_from_a_worktree(project, goal, tmp_path_factory):
    linked = _linked(project, tmp_path_factory.mktemp("linked"))
    assert _run(linked, "hub", "status")["result"]["project_name"] == project.name


def test_a_worktree_of_a_separate_git_dir_stands_alone(tmp_path):
    root = tmp_path / "main"
    _git(tmp_path, "init", "--separate-git-dir", str(tmp_path / "store.git"), str(root))
    _git(root, "commit", "--allow-empty", "-m", "first")
    linked = tmp_path / "wt"
    _git(root, "worktree", "add", "-b", "side", str(linked))
    assert _run(root, "init", "--host", "codex")["ok"]
    assert _run(linked, "init", "--host", "codex")["ok"]
    assert (linked / ".intent" / "HEAD").is_file()
    assert not (tmp_path / "store.git" / ".intent").exists()


@pytest.mark.parametrize("content", ["{broken", "[]", '{"what": "no id"}'])
def test_a_bad_file_carried_by_force_does_not_stop_a_merge(project, goal, content):
    base = project / ".intent"
    (base / "HEAD").unlink()
    bad = base / "snaps" / "snap-999.json"
    bad.write_text(content)
    assert _run(project, "migrate", "--force")["ok"]
    bad.unlink()
    assert _run(project, "intent", "create", "After the fix", "--why", "w")["ok"]
    _diverged(project, goal)
    assert _run(project, "merge", "side")["result"]["state"] == "merged"
    assert _run(project, "doctor")["result"]["healthy"] is True


def test_one_change_rewrites_only_its_path_through_the_tree(project):
    base = project / ".intent"
    for number in range(300):
        (base / "intents" / f"intent-{number:03d}.json").write_text("{}")
    repo.commit_worktree(base, "seed")
    trees = len(list((base / repo.TREES).rglob("*.json")))
    (base / "intents" / "intent-007.json").write_text('{"changed": true}')
    revision = repo.commit_worktree(base, "one")
    assert len(list((base / repo.TREES).rglob("*.json"))) - trees <= repo.TREE_DEPTH + 1
    assert repo._content_path(base, repo.REVISIONS, revision).stat().st_size < 1024
    assert len(repo.tree_at(base, revision)) == 300 and repo.verify(base) == []


def test_a_damaged_tree_is_found(project, goal):
    base = project / ".intent"
    repo._content_path(base, repo.TREES, repo.read_revision(base, repo.head_revision(base))["tree"]).write_text("{}")
    assert _run(project, "doctor")["result"]["issues"][0]["code"] == "TREE_CORRUPT"


def test_a_damaged_history_migrates_with_force(project):
    _run(project, "intent", "create", "One", "--why", "w")
    base = project / ".intent"
    (base / "HEAD").unlink()
    (base / "snaps" / "snap-999.json").write_text("{broken")
    assert _run(project, "migrate")["error"]["code"] == "MIGRATION_BLOCKED"
    forced = _run(project, "migrate", "--force")
    assert forced["ok"] and forced["warnings"] and repo.is_repository(base)
