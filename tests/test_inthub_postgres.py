import os

import pytest

from apps.inthub_api.auth import (
    account_for_access_token,
    account_for_session,
    create_account_access_token,
    create_web_session,
    upsert_github_account,
)
from apps.inthub_api.ingest import link_project, store_sync_batch
from apps.inthub_api.public_profiles import configure_public_profile
from apps.inthub_api.queries import list_projects, project_overview, public_profile


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


@pytest.mark.skipif(not POSTGRES_URL, reason="INTHUB_TEST_POSTGRES_URL is not configured")
def test_postgresql_account_and_session_round_trip():
    suffix = os.urandom(6).hex()
    account = upsert_github_account(
        POSTGRES_URL,
        {
            "id": f"integration-{suffix}",
            "login": f"integration-{suffix}",
            "name": "Integration Account",
        },
    )
    session = create_web_session(POSTGRES_URL, account["id"], ttl_seconds=60)

    recovered = account_for_session(POSTGRES_URL, session["token"])
    assert recovered["id"] == account["id"]
    assert recovered["login"] == f"integration-{suffix}"

    access_token = create_account_access_token(
        POSTGRES_URL,
        account["id"],
        ttl_seconds=60,
    )
    recovered_for_cli = account_for_access_token(POSTGRES_URL, access_token["token"])
    assert recovered_for_cli["id"] == account["id"]


@pytest.mark.skipif(not POSTGRES_URL, reason="INTHUB_TEST_POSTGRES_URL is not configured")
def test_postgresql_public_profile_uses_explicit_project_grants():
    suffix = os.urandom(6).hex()
    account = upsert_github_account(
        POSTGRES_URL,
        {
            "id": f"public-{suffix}",
            "login": f"public-{suffix}",
            "name": "Public Integration Account",
        },
    )
    repo = {
        "provider": "github",
        "repo_id": f"public/{suffix}",
        "owner": "public",
        "name": suffix,
    }
    linked = link_project(
        POSTGRES_URL,
        f"Public {suffix}",
        repo,
        f"wks_public_{suffix}",
        account_id=account["id"],
    )
    slug = f"integration-{suffix}"

    configured = configure_public_profile(
        POSTGRES_URL,
        slug=slug,
        provider="github",
        provider_user_id=f"public-{suffix}",
        project_ids=[linked["project_id"]],
    )
    result = public_profile(POSTGRES_URL, slug)

    assert configured["project_count"] == 1
    assert [project["id"] for project in result["projects"]] == [linked["project_id"]]
