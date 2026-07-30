from apps.inthub_api.common import make_remote_object_id
from apps.inthub_api.ingest import link_project, store_sync_batch
from apps.inthub_api.queries import get_intent_detail, project_handoff


def test_handoff_and_intent_detail_include_decision_semantics(tmp_path):
    db_path = str(tmp_path / "inthub.db")
    repo = {
        "provider": "github",
        "repo_id": "example/demo",
        "owner": "example",
        "name": "demo",
    }
    linked = link_project(db_path, "Demo", repo, "wks_demo")
    intent = {
        "id": "intent-001",
        "object": "intent",
        "status": "active",
        "what": "Resume the work",
        "why": "The goal is unfinished",
        "snap_ids": ["snap-001"],
        "decision_ids": ["decision-001"],
    }
    snap = {
        "id": "snap-001",
        "object": "snap",
        "intent_id": "intent-001",
        "what": "Reached a stable boundary",
        "why": "The next session can continue here",
    }
    decision = {
        "id": "decision-001",
        "object": "decision",
        "status": "active",
        "what": "Keep the public API compatible",
        "why": "Existing clients depend on its response shape",
        "intent_ids": ["intent-001", "intent-002"],
    }
    suspended_intent = {
        "id": "intent-002",
        "object": "intent",
        "status": "suspend",
        "what": "Continue the paused migration",
        "why": "The external dependency was temporarily unavailable",
        "snap_ids": ["snap-002"],
        "decision_ids": ["decision-001"],
    }
    suspended_snap = {
        "id": "snap-002",
        "object": "snap",
        "intent_id": "intent-002",
        "what": "Isolated the remaining provider boundary",
        "why": "The next session can retry once the provider recovers",
    }
    store_sync_batch(db_path, {
        "sync_batch_id": "sync_demo",
        "generated_at": "2026-07-30T00:00:00+00:00",
        "project_id": linked["project_id"],
        "repo": repo,
        "workspace": {"workspace_id": linked["workspace_id"]},
        "git": {"branch": "main", "head_commit": "abc123", "dirty": False},
        "snapshot": {
            "intents": [intent, suspended_intent],
            "snaps": [snap, suspended_snap],
            "decisions": [decision],
        },
    })

    handoff = project_handoff(db_path, linked["project_id"])
    handoff_decision = handoff["active_decisions"][0]
    assert handoff_decision["id"] == "decision-001"
    assert handoff_decision["what"] == decision["what"]
    assert handoff_decision["why"] == decision["why"]
    assert handoff_decision["status"] == "active"
    assert handoff["intents"][0]["id"] == "intent-001"
    assert handoff["suspended_intents"][0]["id"] == "intent-002"
    assert handoff["suspended_intents"][0]["why"] == suspended_intent["why"]
    assert handoff["suspended_intents"][0]["latest_snap"] == suspended_snap

    detail = get_intent_detail(
        db_path,
        make_remote_object_id(linked["workspace_id"], intent["id"]),
    )
    assert detail["intent"] == intent
    assert detail["snaps"] == [snap]
    assert detail["decisions"] == [decision]
    assert detail["git"]["head_commit"] == "abc123"
