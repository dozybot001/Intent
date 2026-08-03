import pytest

from apps.inthub_api.auth import upsert_github_account
from apps.inthub_api.common import APIError, make_remote_object_id
from apps.inthub_api.ingest import link_project, store_sync_batch
from apps.inthub_api.queries import get_intent_detail, list_projects, project_handoff


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


def test_accounts_can_link_the_same_repo_without_seeing_each_others_projects(tmp_path):
    db_path = str(tmp_path / "inthub.db")
    first = upsert_github_account(db_path, {"id": 1, "login": "first"})
    second = upsert_github_account(db_path, {"id": 2, "login": "second"})
    repo = {
        "provider": "github",
        "repo_id": "example/shared-name",
        "owner": "example",
        "name": "shared-name",
    }

    first_project = link_project(
        db_path,
        "First copy",
        repo,
        "wks_first",
        account_id=first["id"],
    )
    second_project = link_project(
        db_path,
        "Second copy",
        repo,
        "wks_second",
        account_id=second["id"],
    )

    assert first_project["project_id"] != second_project["project_id"]
    assert [item["id"] for item in list_projects(db_path, first["id"])["projects"]] == [
        first_project["project_id"]
    ]
    assert [item["id"] for item in list_projects(db_path, second["id"])["projects"]] == [
        second_project["project_id"]
    ]
    with pytest.raises(APIError) as exc_info:
        project_handoff(
            db_path,
            first_project["project_id"],
            account_id=second["id"],
        )
    assert exc_info.value.code == "OBJECT_NOT_FOUND"


def test_repo_provider_is_part_of_the_project_identity(tmp_path):
    db_path = str(tmp_path / "inthub.db")
    account = upsert_github_account(db_path, {"id": 3, "login": "provider-user"})
    common = {
        "repo_id": "example/shared-name",
        "owner": "example",
        "name": "shared-name",
    }

    github_project = link_project(
        db_path,
        "GitHub copy",
        {"provider": "github", **common},
        "wks_github",
        account_id=account["id"],
    )
    gitee_project = link_project(
        db_path,
        "Gitee copy",
        {"provider": "gitee", **common},
        "wks_gitee",
        account_id=account["id"],
    )

    assert github_project["project_id"] != gitee_project["project_id"]
    projects = list_projects(db_path, account["id"])["projects"]
    assert {
        (item["repo"]["provider"], item["repo"]["repo_id"])
        for item in projects
    } == {
        ("github", "example/shared-name"),
        ("gitee", "example/shared-name"),
    }


def test_link_rejects_unknown_repo_provider(tmp_path):
    with pytest.raises(APIError) as exc_info:
        link_project(
            str(tmp_path / "inthub.db"),
            "Unsupported",
            {
                "provider": "bitbucket",
                "repo_id": "example/demo",
                "owner": "example",
                "name": "demo",
            },
            "wks_unsupported",
        )

    assert exc_info.value.code == "PROVIDER_UNSUPPORTED"
