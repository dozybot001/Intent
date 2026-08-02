import os

import pytest

from apps.inthub_api.ingest import link_project, store_sync_batch
from apps.inthub_api.queries import list_projects, project_overview


POSTGRES_URL = os.getenv("INTHUB_TEST_POSTGRES_URL")


@pytest.mark.skipif(not POSTGRES_URL, reason="INTHUB_TEST_POSTGRES_URL is not configured")
def test_postgresql_link_sync_and_read_round_trip():
    suffix = os.urandom(6).hex()
    repo = {
        "provider": "github",
        "repo_id": f"integration/{suffix}",
        "owner": "integration",
        "name": suffix,
    }
    workspace_id = f"wks_{suffix}"
    linked = link_project(POSTGRES_URL, f"Postgres {suffix}", repo, workspace_id)
    batch = store_sync_batch(
        POSTGRES_URL,
        {
            "sync_batch_id": f"sync_{suffix}",
            "generated_at": "2026-08-02T00:00:00+00:00",
            "project_id": linked["project_id"],
            "repo": repo,
            "workspace": {"workspace_id": workspace_id},
            "git": {"branch": "main", "head_commit": suffix, "dirty": False},
            "snapshot": {
                "intents": [
                    {
                        "id": "intent-001",
                        "object": "intent",
                        "status": "active",
                        "what": "Verify PostgreSQL",
                        "why": "Production uses the PostgreSQL adapter",
                        "snap_ids": [],
                        "decision_ids": [],
                    }
                ],
                "snaps": [],
                "decisions": [],
            },
        },
    )

    assert batch["duplicate"] is False
    overview = project_overview(POSTGRES_URL, linked["project_id"])
    assert overview["active_intents"][0]["what"] == "Verify PostgreSQL"
    projects = list_projects(POSTGRES_URL)["projects"]
    assert any(project["id"] == linked["project_id"] for project in projects)
