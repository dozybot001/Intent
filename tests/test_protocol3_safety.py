"""What a member, a server or bad luck must not be able to do to a shared project."""

import base64
import json
from types import SimpleNamespace
from urllib.request import Request, urlopen

import pytest

from apps.inthub_api.history import read_history
from apps.inthub_api.repository import fetch_blobs, read_refs, update_ref, upload_blobs
from apps.inthub_api.revisions import _view
from intent_cli import repo
from intent_cli.commands import shared, sync
from tests.protocol_support import _base, _blobs, _code, _copy, _local_commit, hub, itt, pushed  # noqa: F401


def _clone(tmp_path, url, name="desktop"):
    other = tmp_path / name
    other.mkdir()
    assert itt(other, "clone", "demo", "--api-base-url", url)["ok"]
    return other


def _on_new_branch(folder, goal, name):
    assert itt(folder, "switch", "-c", name)["ok"]
    return _local_commit(folder, goal, f"On {name}")


def test_branch_names_that_cannot_sit_together_are_refused(pushed):
    folder, goal, db, _url, project_id = pushed
    main = read_refs(db, "demo")["refs"]["main"]
    tip = _on_new_branch(folder, goal, "fix")
    assert itt(folder, "push")["ok"]
    for name in ("fix/deep", "FIX"):
        upload_blobs(db, {"project_id": project_id, "blobs": _blobs(_base(folder), tip, [main])})
        payload = {"project_name": "demo", "project_id": project_id, "ref": name, "old": None, "new": tip}
        assert _code(update_ref, db, payload) == "BRANCH_EXISTS"


def test_a_branch_name_too_long_for_a_file_is_refused(pushed):
    folder, *_rest = pushed
    assert itt(folder, "branch", "a" * 201)["error"]["code"] == "INVALID_INPUT"
    assert itt(folder, "branch", "长" * 67)["error"]["code"] == "INVALID_INPUT"
    assert itt(folder, "branch", "a" * 200)["ok"]


def test_a_deleted_branch_makes_way_for_a_folder_of_that_name(tmp_path, pushed):
    folder, goal, db, url, _pid = pushed
    other = _clone(tmp_path, url)
    _on_new_branch(folder, goal, "fix")
    assert itt(folder, "push")["ok"]
    assert itt(other, "fetch")["ok"]
    assert itt(folder, "push", "--delete", "fix")["ok"]
    assert itt(folder, "switch", "main")["ok"]
    assert itt(folder, "branch", "-D", "fix")["ok"]
    _on_new_branch(folder, goal, "fix/deep")
    assert itt(folder, "push")["ok"]
    assert itt(other, "fetch")["result"]["updated"] == ["fix/deep"]


def test_a_remote_listing_refs_that_cannot_sit_together_is_refused(pushed, monkeypatch, capsys):
    folder, _goal, _db, url, project_id = pushed
    refs = {"fix": "a" * 64, "fix/deep": "b" * 64}
    monkeypatch.chdir(folder)
    monkeypatch.setattr(shared, "http_json", lambda *a, **k: {
        "format_version": 3, "project_id": project_id, "project_name": "demo", "refs": refs})
    with pytest.raises(SystemExit):
        sync.cmd_fetch(SimpleNamespace(project=None, api_base_url=url, token=None))
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "INVALID_REMOTE_HISTORY"


def _forged(base, parent, node_for):
    """A revision on parent whose tree holds whatever node_for makes of the real one."""
    data = repo.read_revision(base, parent)
    nodes = []
    def keep(node):
        nodes.append(node)
        return repo._digest(repo._canonical(node))
    entries = repo.tree_at(base, parent)
    repo.tree_digest(entries, keep)
    top = node_for(nodes, entries)
    tree = repo._store(base, repo.TREES, top)
    revision = repo._store(base, repo.REVISIONS, {"parents": [parent], "tree": tree, "time": data["time"], "summary": "forged", "changes": []})
    return revision, nodes


def _upload_tree(db, project_id, base, nodes):
    bodies = [repo._canonical(node).decode() for node in nodes]
    upload_blobs(db, {"project_id": project_id, "blobs": [
        {"kind": "tree", "digest": repo._digest(body.encode()), "body": body} for body in bodies]})


def test_a_tree_that_names_an_object_twice_is_refused(pushed):
    folder, goal, db, _url, project_id = pushed
    base = _base(folder)
    main = read_refs(db, "demo")["refs"]["main"]

    def twice(nodes, entries):
        # The hub would read one version and a client the other.
        other_version = repo._store(base, repo.OBJECTS, {"id": goal, "object": "intent", "what": "Rewritten"})
        leaf = {goal: other_version}
        middle = {"z": repo._store(base, repo.TREES, leaf)}
        nodes[:0] = [leaf, middle]
        return {**nodes[-1], "z": repo._store(base, repo.TREES, middle)}

    revision, nodes = _forged(base, main, twice)
    upload_blobs(db, {"project_id": project_id, "blobs": _blobs(base, revision, [main])})
    payload = {"project_name": "demo", "project_id": project_id, "ref": "main", "old": main, "new": revision}
    assert _code(update_ref, db, payload) == "INVALID_HISTORY"
    assert read_refs(db, "demo")["refs"]["main"] == main


def test_a_tree_node_reused_at_another_level_is_refused(pushed):
    folder, _goal, db, _url, project_id = pushed
    base = _base(folder)
    main = read_refs(db, "demo")["refs"]["main"]
    # A top node that points straight at a leaf: valid at the top, not where it lands.
    revision, nodes = _forged(base, main, lambda nodes, entries: {"0": repo._digest(repo._canonical(nodes[0]))})
    _upload_tree(db, project_id, base, nodes)
    top = repo.read_revision(base, revision)["tree"]
    body = repo.read_blob(base, "tree", top).decode()
    raw = repo.read_blob(base, "revision", revision).decode()
    upload_blobs(db, {"project_id": project_id, "blobs": [
        {"kind": "tree", "digest": top, "body": body}, {"kind": "revision", "digest": revision, "body": raw}]})
    payload = {"project_name": "demo", "project_id": project_id, "ref": "feature", "old": None, "new": revision}
    assert _code(update_ref, db, payload) in {"INVALID_HISTORY", "INCOMPLETE_HISTORY"}


def test_a_blob_uploaded_as_another_kind_cannot_take_a_revisions_place(pushed):
    folder, goal, db, _url, project_id = pushed
    base = _base(folder)
    main = read_refs(db, "demo")["refs"]["main"]
    tip = _local_commit(folder, goal, "Next")
    body = repo.read_blob(base, "revision", tip).decode()
    upload_blobs(db, {"project_id": project_id, "blobs": [{"kind": "object", "digest": tip, "body": body}]})
    assert itt(folder, "push")["ok"]
    assert read_refs(db, "demo")["refs"]["main"] == tip and tip != main


def test_a_copy_that_last_saw_a_mirrored_push_merges_from_it(tmp_path, pushed):
    folder, goal, db, url, project_id = pushed
    old = _copy(tmp_path, url, "old")
    base = _base(old)
    head = read_history(db, "demo")
    for collection, objects in head["snapshot"].items():
        for obj in objects:
            (base / collection / f"{obj['id']}.json").write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    repo.commit_worktree(base, "as 8.0 left it")
    config = json.loads((base / "hub.json").read_text())
    (base / "hub.json").write_text(json.dumps({**config, "format_version": 2, "project_id": project_id, "revision": head["revision"]}))
    assert itt(old, "intent", "done", goal)["ok"]
    _local_commit(folder, goal, "Remote moved on")
    assert itt(folder, "push")["ok"]
    assert itt(old, "fetch")["ok"]
    assert itt(old, "merge", "origin/main")["result"]["state"] == "merged"
    assert itt(old, "show", goal)["result"]["object"]["status"] == "done"
    assert itt(old, "push")["ok"]


def test_a_relation_conflict_settled_either_way_still_pushes(tmp_path, pushed):
    folder, goal, _db, url, _pid = pushed
    one = itt(folder, "intent", "create", "Parent one", "--why", "w")["result"]["id"]
    two = itt(folder, "intent", "create", "Parent two", "--why", "w")["result"]["id"]
    assert itt(folder, "push")["ok"]
    other = _clone(tmp_path, url)
    assert itt(other, "intent", "relate", goal, "--part-of", two)["ok"]
    assert itt(other, "push")["ok"]
    assert itt(folder, "intent", "relate", goal, "--part-of", one)["ok"]
    assert itt(folder, "pull")["error"]["code"] == "MERGE_CONFLICT"
    assert itt(folder, "resolve", goal, "--ours")["ok"]
    assert itt(folder, "merge", "--continue")["ok"]
    assert itt(folder, "push")["ok"], "withdrawing keeps what was pushed"
    assert itt(other, "pull")["ok"] and itt(other, "doctor")["result"]["healthy"] is True


def test_a_damaged_file_long_since_repaired_does_not_block_a_push(tmp_path, pushed):
    folder, _goal, _db, url, _pid = pushed
    base = _base(folder)
    bad = base / "snaps" / "snap-999.json"
    for content in (b"\xff\xfe not text", b"nul\0inside"):
        bad.write_bytes(content)
        repo.commit_worktree(base, "damage")
        bad.unlink()
        repo.commit_worktree(base, "repair")
    assert itt(folder, "push")["ok"]
    other = _clone(tmp_path, url)
    assert itt(other, "doctor")["result"]["healthy"] is True
    assert repo.head_revision(_base(other)) == repo.head_revision(base)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "1e999"])
def test_a_revision_holding_a_number_json_cannot_carry_is_refused(pushed, value):
    _folder, _goal, db, _url, project_id = pushed
    body = '{"parents": [], "tree": "' + "a" * 64 + '", "time": ' + value + "}"
    blob = {"kind": "revision", "digest": repo._digest(body.encode()), "body": body}
    assert _code(upload_blobs, db, {"project_id": project_id, "blobs": [blob]}) == "INVALID_BLOB"


def test_fields_a_client_wrote_cannot_break_the_history_page():
    view = _view("a" * 64, {"parents": [], "time": {"x": 1}, "summary": 7, "author": {"name": 3, "email": "a@b.c", "evil": "x"},
                            "changes": [1, {"id": 2}]}, {})
    json.dumps(view, allow_nan=False)
    assert view["created_at"] is None and view["title"] is None and view["pusher"] == {"email": "a@b.c"}


def test_many_local_branches_fit_in_a_fetch_request(pushed):
    _folder, _goal, db, url, project_id = pushed
    main = read_refs(db, "demo")["refs"]["main"]
    body = json.dumps({"project_id": project_id, "want": [main], "have": ["a" * 64] * 2000}).encode()
    request = Request(f"{url}/api/v3/fetch", data=body, headers={"Content-Type": "application/json"})
    with urlopen(request) as response:
        assert json.load(response)["result"]["total"] > 0


def test_an_interrupted_upload_cannot_stop_a_fetch(pushed):
    folder, goal, db, _url, project_id = pushed
    base = _base(folder)
    main = read_refs(db, "demo")["refs"]["main"]
    tip = _local_commit(folder, goal, "Half uploaded")
    revision = [blob for blob in _blobs(base, tip, [main]) if blob["kind"] == "revision"]
    upload_blobs(db, {"project_id": project_id, "blobs": revision})
    assert fetch_blobs(db, {"project_id": project_id, "want": [main], "have": [tip]})["total"] > 0
    assert itt(folder, "push")["ok"]


def test_text_uploaded_as_binary_is_stored_as_text(pushed):
    folder, goal, db, _url, project_id = pushed
    base = _base(folder)
    main = read_refs(db, "demo")["refs"]["main"]
    tip = _local_commit(folder, goal, "Next")
    blobs = _blobs(base, tip, [main])
    disguised = [{**blob, "body": base64.b64encode(blob["body"].encode()).decode(), "binary": True}
                 if blob["kind"] == "object" else blob for blob in blobs]
    upload_blobs(db, {"project_id": project_id, "blobs": disguised})
    assert itt(folder, "push")["ok"]
    assert read_refs(db, "demo")["refs"]["main"] == tip


def test_a_long_branch_from_before_the_limit_keeps_working(pushed):
    folder, *_rest = pushed
    base = _base(folder)
    name = "a" * 240
    repo.set_branch(base, name, repo.head_revision(base))
    repo.set_head(base, name)
    assert itt(folder, "status", "--local")["result"]["branch"] == name
    assert itt(folder, "doctor")["result"]["healthy"] is True
    assert "200 bytes" in itt(folder, "push")["error"]["message"]
    assert itt(folder, "switch", "main")["ok"]


def test_a_side_that_keeps_a_relation_conflict_says_so(tmp_path, pushed):
    folder, goal, _db, url, _pid = pushed
    other_goal = itt(folder, "intent", "create", "Other", "--why", "w")["result"]["id"]
    assert itt(folder, "push")["ok"]
    other = _clone(tmp_path, url)
    assert itt(other, "intent", "relate", goal, "--depends-on", other_goal)["ok"]
    assert itt(other, "push")["ok"]
    assert itt(folder, "intent", "relate", other_goal, "--part-of", goal)["ok"]
    conflict = itt(folder, "pull")["error"]
    assert conflict["code"] == "MERGE_CONFLICT"
    target = next(item for item in conflict["details"]["conflicts"] if item["field"] == "relations")["id"]
    results = [itt(folder, "resolve", target, flag) for flag in ("--ours", "--theirs")]
    assert any(result["ok"] for result in results), results
    assert itt(folder, "merge", "--continue")["ok"]
    assert itt(folder, "doctor")["result"]["healthy"] is True
    assert itt(folder, "push")["ok"]


def test_a_page_that_does_not_move_forward_is_refused(tmp_path, pushed, monkeypatch, capsys):
    folder, goal, _db, url, _pid = pushed
    other = _clone(tmp_path, url)
    _local_commit(folder, goal, "Next")
    assert itt(folder, "push")["ok"]
    genuine = sync.http_json
    monkeypatch.chdir(other)
    monkeypatch.setattr(sync, "http_json", lambda method, target, *a, **k:
                        {"blobs": [], "next_offset": 1} if target.endswith("/api/v3/fetch") else genuine(method, target, *a, **k))
    with pytest.raises(SystemExit):
        sync.cmd_fetch(SimpleNamespace(project=None, api_base_url=url, token=None))
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "INVALID_REMOTE_HISTORY"
