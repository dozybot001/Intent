"""Protocol 3: the hub keeps the revision graph, and protocol 2 keeps working beside it."""

import json
import subprocess

import pytest

from apps.inthub_api import repository
from apps.inthub_api.auth import upsert_github_account
from apps.inthub_api.db import connect
from apps.inthub_api.history import link_history, push_history, read_history
from apps.inthub_api.projects import delete_project, export_project
from apps.inthub_api.repository import fetch_blobs, read_refs, update_ref, upload_blobs
from apps.inthub_api.revisions import project_revisions, revision_detail
from intent_cli import repo
from intent_cli.hub.versions import revision_id
from tests.protocol_support import _base, _blobs, _code, _copy, _local_commit, hub, itt, pushed  # noqa: F401


def test_clone_brings_every_branch_and_a_working_copy(tmp_path, pushed):
    folder, goal, _db, url, _pid = pushed
    assert itt(folder, "switch", "-c", "feature")["ok"]
    side = _local_commit(folder, goal, "Side work")
    assert itt(folder, "push")["result"]["ref"] == "feature"
    other = tmp_path / "desktop"
    other.mkdir()
    cloned = itt(other, "clone", "demo", "--api-base-url", url)
    assert cloned["ok"] and cloned["result"]["branches"] == ["feature", "main"]
    assert itt(other, "inspect")["active_intents"][0]["id"] == goal
    assert itt(other, "merge", "origin/feature")["result"]["head"] == side
    assert itt(other, "doctor")["result"]["healthy"] is True
    assert itt(other, "clone", "demo", "--api-base-url", url)["error"]["code"] == "ALREADY_EXISTS"


def test_clone_of_nothing_leaves_nothing_behind(tmp_path, hub):
    _db, url = hub
    other = tmp_path / "empty"
    other.mkdir()
    assert itt(other, "clone", "nothing-here", "--api-base-url", url)["error"]["code"] == "SNAPSHOT_NOT_FOUND"
    assert not (other / ".intent").exists()


def test_a_project_from_protocol_2_becomes_a_graph_on_first_use(hub):
    db, _url = hub
    linked = link_history(db, "demo")
    project_id = linked["project_id"]
    empty = {"intents": [], "snaps": [], "decisions": []}
    goal = {"id": "intent-001", "object": "intent", "created_at": "2026-10-01T00:00:00+00:00", "what": "Goal", "why": "",
            "origin": "t", "status": "active", "decision_ids": [], "snap_ids": []}
    first = push_history(db, {"project_name": "demo", "project_id": project_id, "parent": None,
                              "revision": revision_id(None, empty), "snapshot": empty, "pusher": {"name": "Ana"}})
    filled = {**empty, "intents": [goal]}
    second = push_history(db, {"project_name": "demo", "project_id": project_id, "parent": first["revision"],
                               "revision": revision_id(first["revision"], filled), "snapshot": filled})
    main = read_refs(db, "demo")["refs"]["main"]
    page = project_revisions(db, project_id)
    assert page["total"] == 2 and page["revisions"][0]["revision"] == main
    assert page["revisions"][0]["summary"]["intents_added"] == 1
    assert page["revisions"][1]["pusher"] == {"name": "Ana"} and page["revisions"][1]["parent"] is None
    # A link saved before the graph still opens.
    assert revision_detail(db, project_id, second["revision"])["revision"] == main
    assert read_refs(db, "demo")["refs"]["main"] == main, "converting again changes nothing"


def test_a_protocol_2_push_joins_the_graph(pushed):
    folder, _goal, db, _url, project_id = pushed
    head = read_history(db, "demo")
    snapshot = json.loads(json.dumps(head["snapshot"]))
    snapshot["intents"].append({**snapshot["intents"][0], "id": "intent-777", "what": "Older client", "snap_ids": []})
    push_history(db, {"project_name": "demo", "project_id": project_id, "parent": head["revision"],
                      "revision": revision_id(head["revision"], snapshot), "snapshot": snapshot})
    assert itt(folder, "status")["result"]["state"] == "behind"
    assert itt(folder, "pull")["result"]["state"] == "fast_forward"
    assert itt(folder, "show", "intent-777")["result"]["object"]["what"] == "Older client"
    assert repo.read_revision(_base(folder), repo.head_revision(_base(folder)))["origin"] == "inthub"
    assert itt(folder, "doctor")["result"]["healthy"] is True


def test_main_stays_readable_over_protocol_2(pushed):
    folder, goal, db, _url, _pid = pushed
    before = read_history(db, "demo")
    _local_commit(folder, goal, "Second step")
    assert itt(folder, "push")["ok"]
    after = read_history(db, "demo")
    assert after["parent"] == before["revision"] and after["revision"] == revision_id(before["revision"], after["snapshot"])
    assert {snap["what"] for snap in after["snapshot"]["snaps"]} == {"First step", "Second step"}


def test_a_copy_from_before_the_graph_merges_from_the_last_push_it_saw(tmp_path, hub):
    db, url = hub
    folder = _copy(tmp_path, url, "old")
    goal = itt(folder, "intent", "create", "Goal", "--why", "w")["result"]["id"]
    base = _base(folder)
    snapshot = repo.snapshot_at(base, repo.head_revision(base))
    project_id = link_history(db, "demo")["project_id"]
    first = push_history(db, {"project_name": "demo", "project_id": project_id, "parent": None,
                              "revision": revision_id(None, snapshot), "snapshot": snapshot})
    config = json.loads((base / "hub.json").read_text())
    (base / "hub.json").write_text(json.dumps({**config, "format_version": 2, "project_id": project_id, "revision": first["revision"]}))
    newer = {**snapshot, "intents": [*snapshot["intents"], {**snapshot["intents"][0], "id": "intent-777", "what": "Remote"}]}
    push_history(db, {"project_name": "demo", "project_id": project_id, "parent": first["revision"],
                      "revision": revision_id(first["revision"], newer), "snapshot": newer})
    assert itt(folder, "intent", "done", goal)["ok"]
    # With no shared base this would be a status conflict: done against active.
    assert itt(folder, "pull")["result"]["state"] == "merged"
    assert itt(folder, "show", goal)["result"]["object"]["status"] == "done"
    assert itt(folder, "push")["ok"]
    assert itt(folder, "status")["result"]["state"] == "up_to_date"


def test_blobs_must_match_their_digest_and_shape(pushed):
    _folder, _goal, db, _url, project_id = pushed
    payload = {"project_id": project_id}
    assert _code(upload_blobs, db, {**payload, "blobs": [{"kind": "object", "digest": "0" * 64, "body": "{}"}]}) == "INVALID_BLOB"
    assert _code(upload_blobs, db, {**payload, "blobs": [{"kind": "evil", "digest": "0" * 64, "body": "{}"}]}) == "INVALID_INPUT"
    raw = '{"parents": ["../evil"], "tree": "x"}'
    digest = repo._digest(raw.encode())
    assert _code(upload_blobs, db, {**payload, "blobs": [{"kind": "revision", "digest": digest, "body": raw}]}) == "INVALID_BLOB"


def test_a_ref_moves_only_when_everything_has_arrived(pushed):
    folder, goal, db, _url, project_id = pushed
    base = _base(folder)
    main = read_refs(db, "demo")["refs"]["main"]
    tip = _local_commit(folder, goal, "Not uploaded")
    payload = {"project_name": "demo", "project_id": project_id, "ref": "main", "old": main, "new": tip}
    assert _code(update_ref, db, payload) == "INCOMPLETE_HISTORY"
    blobs = _blobs(base, tip, [main])
    revision_only = [blob for blob in blobs if blob["kind"] == "revision"]
    upload_blobs(db, {"project_id": project_id, "blobs": revision_only})
    assert _code(update_ref, db, payload) == "INCOMPLETE_HISTORY"
    upload_blobs(db, {"project_id": project_id, "blobs": blobs})
    assert update_ref(db, payload)["changed"] is True
    assert read_refs(db, "demo")["refs"]["main"] == tip


def test_a_ref_moves_only_forward_from_where_the_pusher_saw_it(tmp_path, pushed):
    folder, goal, db, url, project_id = pushed
    other = tmp_path / "desktop"
    other.mkdir()
    assert itt(other, "clone", "demo", "--api-base-url", url)["ok"]
    main = read_refs(db, "demo")["refs"]["main"]
    ours = _local_commit(folder, goal, "Ours")
    theirs = _local_commit(other, goal, "Theirs")
    assert itt(folder, "push")["ok"]
    upload_blobs(db, {"project_id": project_id, "blobs": _blobs(_base(other), theirs, [main])})
    payload = {"project_name": "demo", "project_id": project_id, "ref": "main", "new": theirs}
    assert _code(update_ref, db, {**payload, "old": main}) == "NON_FAST_FORWARD"
    assert _code(update_ref, db, {**payload, "old": ours}) == "NON_FAST_FORWARD", "a sideways move loses revisions"
    assert read_refs(db, "demo")["refs"]["main"] == ours


def _tampered(folder, change):
    base = _base(folder)
    path = next((base / "snaps").glob("*.json"))
    change(path)
    return repo.commit_worktree(base, "tamper")


def test_a_descendant_that_rewrites_main_is_still_refused(pushed):
    folder, _goal, db, _url, project_id = pushed
    base = _base(folder)
    main = read_refs(db, "demo")["refs"]["main"]
    tip = _tampered(folder, lambda path: path.write_text(path.read_text().replace("First step", "Rewritten")))
    upload_blobs(db, {"project_id": project_id, "blobs": _blobs(base, tip, [main])})
    payload = {"project_name": "demo", "project_id": project_id, "ref": "main", "old": main, "new": tip}
    assert _code(update_ref, db, payload) == "HISTORY_CONFLICT"
    assert read_refs(db, "demo")["refs"]["main"] == main


def test_a_tip_with_a_broken_object_is_refused(pushed):
    folder, _goal, db, _url, project_id = pushed
    base = _base(folder)
    main = read_refs(db, "demo")["refs"]["main"]
    tip = _tampered(folder, lambda path: path.write_text("{broken"))
    upload_blobs(db, {"project_id": project_id, "blobs": _blobs(base, tip, [main])})
    payload = {"project_name": "demo", "project_id": project_id, "ref": "feature", "old": None, "new": tip}
    assert _code(update_ref, db, payload) == "INVALID_SNAPSHOT"


def test_main_cannot_be_deleted_but_a_branch_can(pushed):
    folder, goal, db, _url, project_id = pushed
    main = read_refs(db, "demo")["refs"]["main"]
    assert _code(update_ref, db, {"project_id": project_id, "ref": "main", "old": main, "new": None}) == "INVALID_INPUT"
    assert itt(folder, "switch", "-c", "feature")["ok"]
    _local_commit(folder, goal, "Side")
    assert itt(folder, "push")["ok"]
    assert itt(folder, "branch", "-r")["result"]["branches"][0]["name"] == "origin/feature"
    assert itt(folder, "push", "--delete", "feature")["result"]["deleted"] == "feature"
    assert set(read_refs(db, "demo")["refs"]) == {"main"}
    assert [item["name"] for item in itt(folder, "branch", "-r")["result"]["branches"]] == ["origin/main"]


def test_a_branch_stays_out_of_the_main_history(pushed):
    folder, goal, db, _url, project_id = pushed
    assert itt(folder, "switch", "-c", "feature")["ok"]
    _local_commit(folder, goal, "Side")
    total = project_revisions(db, project_id)["total"]
    snapshot = read_history(db, "demo")["snapshot"]
    assert itt(folder, "push")["ok"]
    assert project_revisions(db, project_id)["total"] == total and read_history(db, "demo")["snapshot"] == snapshot


def test_the_history_page_shows_a_merge_and_what_it_joined(tmp_path, pushed):
    folder, goal, db, url, project_id = pushed
    other = tmp_path / "desktop"
    other.mkdir()
    assert itt(other, "clone", "demo", "--api-base-url", url)["ok"]
    _local_commit(other, goal, "From desktop")
    assert itt(other, "push")["ok"]
    _local_commit(folder, goal, "From laptop")
    assert itt(folder, "pull")["result"]["state"] == "merged"
    assert itt(folder, "push")["ok"]
    newest = project_revisions(db, project_id)["revisions"][0]
    assert newest["merge"] is True and len(newest["parents"]) == 2 and newest["title"].startswith("Merged origin/main")
    exported = export_project(db, project_id)
    assert exported["head"]["revision"] == newest["revision"] and exported["revisions"][0]["parents"] == newest["parents"]


def test_fetch_pages_carry_on_from_the_offset(pushed, monkeypatch):
    _folder, _goal, db, _url, project_id = pushed
    monkeypatch.setattr(repository, "PAGE_BYTES", 1)
    main = read_refs(db, "demo")["refs"]["main"]
    seen, offset = [], 0
    while offset is not None:
        page = fetch_blobs(db, {"project_id": project_id, "want": [main], "have": [], "offset": offset})
        assert len(page["blobs"]) == 1
        seen += [blob["digest"] for blob in page["blobs"]]
        offset = page["next_offset"]
    assert len(seen) == len(set(seen)) == page["total"]


def test_fetch_asks_only_for_what_is_new(pushed):
    folder, goal, db, _url, project_id = pushed
    main = read_refs(db, "demo")["refs"]["main"]
    _local_commit(folder, goal, "Next")
    assert itt(folder, "push")["ok"]
    tip = read_refs(db, "demo")["refs"]["main"]
    everything = fetch_blobs(db, {"project_id": project_id, "want": [tip], "have": []})["total"]
    assert fetch_blobs(db, {"project_id": project_id, "want": [tip], "have": [main]})["total"] < everything


def test_a_fetch_cut_off_part_way_is_fetched_again(tmp_path, pushed):
    folder, goal, db, url, project_id = pushed
    other = tmp_path / "desktop"
    other.mkdir()
    assert itt(other, "clone", "demo", "--api-base-url", url)["ok"]
    main = read_refs(db, "demo")["refs"]["main"]
    _local_commit(folder, goal, "Next")
    assert itt(folder, "push")["ok"]
    tip = read_refs(db, "demo")["refs"]["main"]
    revision = next(blob for blob in fetch_blobs(db, {"project_id": project_id, "want": [tip], "have": [main]})["blobs"]
                    if blob["kind"] == "revision")
    repo.install_blob(_base(other), "revision", tip, revision["body"].encode())  # the rest never arrived
    assert itt(other, "status")["result"]["state"] == "behind"
    assert itt(other, "pull")["result"]["state"] == "fast_forward"
    assert itt(other, "doctor")["result"]["healthy"] is True


def test_a_tampered_page_is_refused_before_any_ref_moves(tmp_path, pushed, monkeypatch, capsys):
    from intent_cli.commands import shared, sync
    folder, goal, _db, url, _pid = pushed
    other = tmp_path / "desktop"
    other.mkdir()
    assert itt(other, "clone", "demo", "--api-base-url", url)["ok"]
    seen = repo.remote_revision(_base(other), "main")
    _local_commit(folder, goal, "Next")
    assert itt(folder, "push")["ok"]
    genuine = sync.http_json

    def tamper(method, target, *args, **kwargs):
        reply = genuine(method, target, *args, **kwargs)
        if target.endswith("/api/v3/fetch"):
            reply["blobs"][-1]["body"] += " "
        return reply

    from types import SimpleNamespace
    monkeypatch.chdir(other)
    monkeypatch.setattr(sync, "http_json", tamper)
    with pytest.raises(BaseException):
        sync.cmd_fetch(SimpleNamespace(project=None, api_base_url=url, token=None))
    capsys.readouterr()
    assert repo.remote_revision(_base(other), "main") == seen


def test_members_alone_can_fetch(hub):
    db, _url = hub
    owner = upsert_github_account(db, {"id": 1, "login": "owner"})
    stranger = upsert_github_account(db, {"id": 2, "login": "stranger"})
    project_id = link_history(db, "private", owner["id"])["project_id"]
    payload = {"project_id": project_id, "want": [], "have": []}
    assert fetch_blobs(db, payload, owner["id"])["total"] == 0
    assert _code(fetch_blobs, db, payload, stranger["id"]) == "PROJECT_NOT_FOUND"
    assert read_refs(db, "private", stranger["id"])["project_id"] is None
    assert _code(upload_blobs, db, {"project_id": project_id, "blobs": []}, stranger["id"]) == "NOT_LINKED"
    assert _code(update_ref, db, {"project_id": project_id, "ref": "main", "old": None, "new": None}, stranger["id"]) == "NOT_LINKED"


def test_uploads_count_against_storage_and_a_deleted_project_takes_them_along(pushed):
    folder, goal, db, _url, project_id = pushed
    with connect(db) as conn:
        before = conn.execute("SELECT stored_bytes FROM projects WHERE id = ?", (project_id,)).fetchone()["stored_bytes"]
        assert conn.execute("SELECT count(*) AS n FROM repo_blobs WHERE project_id = ?", (project_id,)).fetchone()["n"] > 0
    _local_commit(folder, goal, "More")
    assert itt(folder, "push")["ok"]
    with connect(db) as conn:
        assert conn.execute("SELECT stored_bytes FROM projects WHERE id = ?", (project_id,)).fetchone()["stored_bytes"] > before
    delete_project(db, project_id, "demo")
    with connect(db) as conn:
        for table in ("repo_blobs", "repo_refs"):
            assert conn.execute(f"SELECT count(*) AS n FROM {table} WHERE project_id = ?", (project_id,)).fetchone()["n"] == 0


def test_a_linked_worktree_pushes_its_own_branch(tmp_path, hub):
    db, url = hub
    root = tmp_path / "code"
    root.mkdir()
    git = lambda *args: subprocess.run(["git", "-c", "user.email=a@b.c", "-c", "user.name=a", *args], cwd=root, capture_output=True, check=True)
    git("init", "-q", "-b", "main")
    git("commit", "-q", "--allow-empty", "-m", "first")
    assert itt(root, "init")["ok"]
    assert itt(root, "remote", "add", "origin", url, "--project", "demo")["ok"]
    goal = itt(root, "intent", "create", "Goal", "--why", "w")["result"]["id"]
    assert itt(root, "push")["ok"]
    linked = tmp_path / "wt"
    git("worktree", "add", "-q", "-b", "agent/fix", str(linked))
    assert itt(linked, "snap", "create", "From the worktree", "--intent", goal)["ok"]
    assert itt(linked, "push")["result"]["ref"] == "agent/fix"
    assert set(read_refs(db, "demo")["refs"]) == {"main", "agent/fix"}
    assert itt(root, "status")["result"]["state"] == "up_to_date", "main did not move"
