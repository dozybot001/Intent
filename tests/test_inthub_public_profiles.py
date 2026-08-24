import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

from apps.inthub_api.auth import upsert_github_account
from apps.inthub_api.common import APIError, make_remote_object_id
from apps.inthub_api.ingest import link_project, store_sync_batch
from apps.inthub_api.public_profiles import (
    PublicProfileConfigurationError,
    configure_public_profile,
    remove_public_profile,
)
from apps.inthub_api.queries import (
    public_intent_detail,
    public_profile,
    public_project_overview,
)
from apps.inthub_api.server import make_handler


def _link(db_path, account, name, workspace_id):
    repo_name = name.lower().replace(" ", "-")
    repo = {
        "provider": "github",
        "repo_id": f"example/{repo_name}",
        "owner": "example",
        "name": repo_name,
    }
    linked = link_project(
        db_path,
        name,
        repo,
        workspace_id,
        account_id=account["id"],
    )
    intent = {
        "id": "intent-001",
        "object": "intent",
        "status": "active",
        "what": f"Continue {name}",
        "why": "This is the current objective",
        "snap_ids": [],
        "decision_ids": [],
    }
    store_sync_batch(
        db_path,
        {
            "sync_batch_id": f"sync_{workspace_id}",
            "generated_at": "2026-08-24T00:00:00+00:00",
            "project_id": linked["project_id"],
            "repo": repo,
            "workspace": {"workspace_id": linked["workspace_id"]},
            "git": {
                "branch": "main",
                "head_commit": "abc123",
                "dirty": False,
                "remote_url": "https://embedded-credential@example.invalid/repo.git",
            },
            "snapshot": {"intents": [intent], "snaps": [], "decisions": []},
        },
        account_id=account["id"],
    )
    return linked, intent


def _get_json(url):
    try:
        response = urlopen(url)
    except HTTPError as exc:
        response = exc
    with response:
        return response.status, json.loads(response.read().decode("utf-8"))


def test_public_profile_requires_explicit_project_grants(tmp_path):
    db_path = str(tmp_path / "inthub.db")
    owner = upsert_github_account(
        db_path,
        {"id": 101, "login": "owner", "name": "Profile Owner"},
    )
    other = upsert_github_account(db_path, {"id": 202, "login": "other"})
    published, published_intent = _link(db_path, owner, "Published", "wks_published")
    private, _ = _link(db_path, owner, "Private", "wks_private")
    foreign, _ = _link(db_path, other, "Foreign", "wks_foreign")

    configured = configure_public_profile(
        db_path,
        slug="showcase",
        provider="github",
        provider_user_id="101",
        title="Owner's IntHub",
        description="Selected public semantic history.",
        project_ids=[published["project_id"]],
    )

    assert configured["project_ids"] == [published["project_id"]]
    result = public_profile(db_path, "showcase")
    assert result["profile"]["account"] == {
        "provider": "github",
        "login": "owner",
        "display_name": "Profile Owner",
        "avatar_url": None,
    }
    assert "account_id" not in result["profile"]
    assert [project["id"] for project in result["projects"]] == [
        published["project_id"]
    ]
    assert public_project_overview(
        db_path,
        "showcase",
        published["project_id"],
    )["project"]["name"] == "Published"
    detail = public_intent_detail(
        db_path,
        "showcase",
        make_remote_object_id("wks_published", published_intent["id"]),
    )
    assert detail["intent"]["what"] == "Continue Published"
    assert detail["git"] == {
        "branch": "main",
        "head_commit": "abc123",
        "dirty": False,
    }
    assert "remote_url" not in detail["git"]

    with pytest.raises(APIError) as private_error:
        public_project_overview(db_path, "showcase", private["project_id"])
    assert private_error.value.code == "OBJECT_NOT_FOUND"
    with pytest.raises(APIError) as foreign_error:
        public_intent_detail(
            db_path,
            "showcase",
            make_remote_object_id("wks_foreign", "intent-001"),
        )
    assert foreign_error.value.code == "OBJECT_NOT_FOUND"

    future, _ = _link(db_path, owner, "Future", "wks_future")
    assert future["project_id"] not in {
        project["id"] for project in public_profile(db_path, "showcase")["projects"]
    }
    assert foreign["project_id"] not in configured["project_ids"]


def test_public_profile_configuration_is_reversible_and_account_bound(tmp_path):
    db_path = str(tmp_path / "inthub.db")
    owner = upsert_github_account(db_path, {"id": 101, "login": "owner"})
    other = upsert_github_account(db_path, {"id": 202, "login": "other"})
    project, _ = _link(db_path, owner, "Published", "wks_published")

    configure_public_profile(
        db_path,
        slug="showcase",
        provider="github",
        provider_user_id="101",
        project_ids=[project["project_id"]],
    )
    with pytest.raises(PublicProfileConfigurationError, match="another account"):
        configure_public_profile(
            db_path,
            slug="showcase",
            provider="github",
            provider_user_id="202",
            include_all_current_projects=True,
        )

    assert remove_public_profile(db_path, slug="showcase")["removed"] is True
    with pytest.raises(APIError) as missing:
        public_profile(db_path, "showcase")
    assert missing.value.code == "PUBLIC_PROFILE_NOT_FOUND"
    assert other["id"] != owner["id"]


def test_showcase_is_anonymous_read_only_without_weakening_private_api(tmp_path):
    db_path = str(tmp_path / "inthub.db")
    owner = upsert_github_account(db_path, {"id": 101, "login": "owner"})
    project, _ = _link(db_path, owner, "Published", "wks_published")
    configure_public_profile(
        db_path,
        slug="showcase",
        provider="github",
        provider_user_id="101",
        project_ids=[project["project_id"]],
    )

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_handler(
            db_path,
            serve_web=True,
            github_client_id="github-client-id",
            github_client_secret="github-client-secret",
        ),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        status, config = _get_json(f"{base}/showcase/config.json")
        assert status == 200
        assert config["publicMode"] is True
        assert config["authRequired"] is False
        assert config["publicProfileSlug"] == "showcase"
        assert urlopen(f"{base}/showcase").status == 200

        status, body = _get_json(f"{base}/api/v1/public-profiles/showcase/projects")
        assert status == 200
        assert [item["id"] for item in body["result"]["projects"]] == [
            project["project_id"]
        ]
        status, body = _get_json(f"{base}/api/v1/projects")
        assert status == 401
        assert body["error"]["code"] == "AUTH_REQUIRED"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
