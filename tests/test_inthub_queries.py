import pytest

from apps.inthub_api.auth import upsert_github_account
from apps.inthub_api.common import APIError, make_remote_object_id
from apps.inthub_api.history import link_history, push_history
from apps.inthub_api.queries import (
    get_intent_detail, get_snap_detail, get_decision_detail, list_projects,
    project_handoff, project_overview, search_project,
)
from intent_cli.hub.versions import revision_id


def test_shared_read_views_preserve_relations_and_decision_semantics(tmp_path):
    db = str(tmp_path / "hub.db")
    linked = link_history(db, "Demo")
    pid = linked["project_id"]
    common = {"created_at": "2026-10-04T00:00:00+00:00", "origin": "test", "why": "reason"}
    intents = [
        {**common, "id": f"intent-00{i}", "object": "intent", "status": status,
         "what": f"Goal {i}", "snap_ids": [f"snap-00{i}"], "decision_ids": ["decision-001"]}
        for i, status in [(1, "active"), (2, "suspend")]
    ]
    snaps = [{**common, "id": f"snap-00{i}", "object": "snap", "intent_id": f"intent-00{i}",
              "what": "Verified checkpoint"} for i in [1, 2]]
    decision = {**common, "id": "decision-001", "object": "decision", "status": "active",
                "what": "Preserve semantic boundaries", "intent_ids": [obj["id"] for obj in intents]}
    snapshot = {"intents": intents, "snaps": snaps, "decisions": [decision]}
    push_history(db, {"project_name": "Demo", "project_id": pid, "parent": None,
                     "snapshot": snapshot, "revision": revision_id(None, snapshot)})
    handoff = project_handoff(db, pid)
    assert handoff["intents"][0]["latest_snap"] == snaps[0]
    assert handoff["suspended_intents"][0]["latest_snap"] == snaps[1]
    assert handoff["active_decisions"][0]["why"] == decision["why"]
    detail = get_intent_detail(db, make_remote_object_id(pid, "intent-001"))
    assert detail["intent"] == intents[0]
    assert detail["snaps"] == [snaps[0]]
    assert detail["decisions"] == [decision]
    assert detail["project_id"] == pid
    assert get_snap_detail(db, make_remote_object_id(pid, "snap-001"))["intent"] == intents[0]
    assert get_decision_detail(db, make_remote_object_id(pid, "decision-001"))["intents"] == intents
    assert len(search_project(db, pid, "reason")["matches"]) == 5
    assert project_overview(db, pid)["total_snaps"] == 2


def test_accounts_share_names_but_not_histories(tmp_path):
    db = str(tmp_path / "hub.db")
    first = upsert_github_account(db, {"id": 1, "login": "first"})
    second = upsert_github_account(db, {"id": 2, "login": "second"})
    a = link_history(db, "Same project", first["id"])
    b = link_history(db, "Same project", second["id"])
    assert a["project_id"] != b["project_id"]
    assert a == link_history(db, "Same project", first["id"])
    assert [obj["id"] for obj in list_projects(db, first["id"])["projects"]] == [a["project_id"]]
    assert [obj["id"] for obj in list_projects(db, second["id"])["projects"]] == [b["project_id"]]
    with pytest.raises(APIError) as failure:
        project_handoff(db, a["project_id"], second["id"])
    assert failure.value.code == "OBJECT_NOT_FOUND"
    with pytest.raises(APIError):
        get_intent_detail(db, make_remote_object_id(a["project_id"], "intent-001"), second["id"])
