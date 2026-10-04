import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

from apps.inthub_api.auth import create_account_access_token, upsert_github_account
from apps.inthub_api.common import APIError
from apps.inthub_api.ingest import link_project, store_sync_batch
from apps.inthub_api.server import make_handler
from apps.inthub_api.snapshots import export_snapshot


def _repo(repo_id="example/demo"):
    owner, name = repo_id.split("/")
    return {
        "provider": "github",
        "repo_id": repo_id,
        "owner": owner,
        "name": name,
    }


def _snapshot(label, *, terminal=False):
    intent = {
        "id": "intent-001",
        "object": "intent",
        "created_at": "2026-10-04T00:00:00+00:00",
        "status": "done" if terminal else "active",
        "what": label,
        "why": "Preserve the complete semantic history.",
        "origin": "test",
        "snap_ids": ["snap-001"],
        "decision_ids": ["decision-001"],
        "future_field": {"preserve": True},
    }
    snap = {
        "id": "snap-001",
        "object": "snap",
        "created_at": "2026-10-04T00:01:00+00:00",
        "intent_id": "intent-001",
        "what": f"{label} checkpoint",
        "why": "Verified boundary.",
        "origin": "test",
    }
    decision = {
        "id": "decision-001",
        "object": "decision",
        "created_at": "2026-10-04T00:02:00+00:00",
        "status": "deprecated" if terminal else "active",
        "what": f"{label} constraint",
        "why": "Retain historical decisions.",
        "origin": "test",
        "intent_ids": ["intent-001"],
        "reason": "Superseded after verification." if terminal else "",
    }
    return {"intents": [intent], "snaps": [snap], "decisions": [decision]}


def _store(db_path, linked, repo, workspace_id, batch_id, generated_at, snapshot):
    return store_sync_batch(
        db_path,
        {
            "sync_batch_id": batch_id,
            "generated_at": generated_at,
            "client": {"name": "intent-cli", "version": "test"},
            "project_id": linked["project_id"],
            "repo": repo,
            "workspace": {"workspace_id": workspace_id},
            "git": {
                "branch": "main",
                "head_commit": batch_id,
                "dirty": False,
                "remote_url": "https://secret@example.invalid/repo.git",
            },
            "snapshot": snapshot,
        },
    )


def _request_json(url, *, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    request = Request(url, headers=headers)
    try:
        response = urlopen(request)
    except HTTPError as exc:
        response = exc
    with response:
        return response.status, json.loads(response.read().decode("utf-8"))


def test_export_requires_explicit_workspace_and_keeps_same_local_ids_separate(tmp_path):
    db_path = str(tmp_path / "inthub.db")
    account = upsert_github_account(db_path, {"id": 1, "login": "owner"})
    repo = _repo()
    first = link_project(db_path, "Demo", repo, "wks_first", account_id=account["id"])
    second = link_project(db_path, "Demo", repo, "wks_second", account_id=account["id"])
    _store(
        db_path,
        first,
        repo,
        "wks_first",
        "sync_first",
        "2026-10-04T01:00:00Z",
        _snapshot("First"),
    )
    _store(
        db_path,
        second,
        repo,
        "wks_second",
        "sync_second",
        "2026-10-04T02:00:00Z",
        _snapshot("Second"),
    )

    with pytest.raises(APIError) as exc_info:
        export_snapshot(db_path, "github", repo["repo_id"], account_id=account["id"])
    assert exc_info.value.code == "WORKSPACE_REQUIRED"
    assert exc_info.value.status == 409
    assert {
        candidate["source_workspace_id"]
        for candidate in exc_info.value.details["candidates"]
    } == {"wks_first", "wks_second"}
    assert all(
        candidate["last_accepted_at"]
        for candidate in exc_info.value.details["candidates"]
    )

    first_export = export_snapshot(
        db_path,
        "github",
        repo["repo_id"],
        account_id=account["id"],
        workspace_id="wks_first",
    )
    second_export = export_snapshot(
        db_path,
        "github",
        repo["repo_id"],
        account_id=account["id"],
        workspace_id="wks_second",
    )
    assert first_export["snapshot"]["intents"][0]["id"] == "intent-001"
    assert second_export["snapshot"]["intents"][0]["id"] == "intent-001"
    assert first_export["snapshot"]["intents"][0]["what"] == "First"
    assert second_export["snapshot"]["intents"][0]["what"] == "Second"


def test_export_is_account_scoped_and_missing_snapshot_is_404(tmp_path):
    db_path = str(tmp_path / "inthub.db")
    first_account = upsert_github_account(db_path, {"id": 1, "login": "first"})
    second_account = upsert_github_account(db_path, {"id": 2, "login": "second"})
    repo = _repo()
    first = link_project(
        db_path, "First", repo, "wks_private", account_id=first_account["id"]
    )
    link_project(
        db_path, "Second", repo, "wks_empty", account_id=second_account["id"]
    )
    _store(
        db_path,
        first,
        repo,
        "wks_private",
        "sync_private",
        "2026-10-04T00:00:00Z",
        _snapshot("Private"),
    )

    with pytest.raises(APIError) as exc_info:
        export_snapshot(
            db_path,
            "github",
            repo["repo_id"],
            account_id=second_account["id"],
            workspace_id="wks_private",
        )
    assert exc_info.value.code == "SNAPSHOT_NOT_FOUND"
    assert exc_info.value.status == 404

    with pytest.raises(APIError) as exc_info:
        export_snapshot(
            db_path,
            "github",
            repo["repo_id"],
            account_id=second_account["id"],
        )
    assert exc_info.value.code == "SNAPSHOT_NOT_FOUND"


def test_export_rejects_noncanonical_repository_identity(tmp_path):
    db_path = str(tmp_path / "inthub.db")

    with pytest.raises(APIError) as exc_info:
        export_snapshot(db_path, "bitbucket", "example/demo", account_id="acct")
    assert exc_info.value.code == "INVALID_INPUT"
    assert exc_info.value.status == 400

    with pytest.raises(APIError) as exc_info:
        export_snapshot(db_path, "github", "example/demo/extra", account_id="acct")
    assert exc_info.value.code == "INVALID_INPUT"
    assert exc_info.value.status == 400


def test_export_uses_server_sequence_and_preserves_complete_raw_snapshot(tmp_path):
    db_path = str(tmp_path / "inthub.db")
    account = upsert_github_account(db_path, {"id": 1, "login": "owner"})
    repo = _repo()
    linked = link_project(db_path, "Demo", repo, "wks_latest", account_id=account["id"])
    link_project(db_path, "Demo", repo, "wks_unsynced", account_id=account["id"])
    _store(
        db_path,
        linked,
        repo,
        "wks_latest",
        "sync_older",
        "2099-01-01T00:00:00Z",
        _snapshot("Old"),
    )
    expected = _snapshot("Newest by server sequence", terminal=True)
    _store(
        db_path,
        linked,
        repo,
        "wks_latest",
        "sync_newer",
        "2000-01-01T00:00:00Z",
        expected,
    )

    result = export_snapshot(
        db_path,
        "github",
        repo["repo_id"],
        account_id=account["id"],
    )

    assert set(result) == {
        "format_version",
        "project_id",
        "repo_binding",
        "source_workspace_id",
        "batch",
        "snapshot",
    }
    assert result["format_version"] == 1
    assert result["project_id"] == linked["project_id"]
    assert result["repo_binding"] == repo
    assert result["source_workspace_id"] == "wks_latest"
    assert result["batch"]["sync_batch_id"] == "sync_newer"
    assert result["batch"]["sequence_id"] > 0
    assert result["batch"]["generated_at"] == "2000-01-01T00:00:00Z"
    assert result["batch"]["accepted_at"]
    assert result["snapshot"] == expected
    assert "git" not in result
    assert "client" not in result


def test_snapshot_endpoint_requires_auth_and_returns_private_export(tmp_path):
    db_path = str(tmp_path / "inthub.db")
    account = upsert_github_account(db_path, {"id": 1, "login": "owner"})
    token = create_account_access_token(db_path, account["id"], ttl_seconds=3600)["token"]
    repo = _repo()
    linked = link_project(db_path, "Demo", repo, "wks_http", account_id=account["id"])
    expected = _snapshot("HTTP")
    _store(
        db_path,
        linked,
        repo,
        "wks_http",
        "sync_http",
        "2026-10-04T00:00:00Z",
        expected,
    )

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_handler(
            db_path,
            tenon_client_id="test-client",
            tenon_client_secret="test-secret",
            oauth_client=object(),
            public_api_base_url="https://inthub.example",
        ),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        query = urlencode(
            {
                "provider": "github",
                "repo_id": repo["repo_id"],
                "workspace_id": "wks_http",
            }
        )
        url = f"http://127.0.0.1:{server.server_port}/api/v1/hub/snapshot?{query}"

        status, body = _request_json(url)
        assert status == 401
        assert body["error"]["code"] == "AUTH_REQUIRED"

        status, body = _request_json(url, token=token)
        assert status == 200
        assert body["ok"] is True
        assert body["result"]["snapshot"] == expected
        assert body["result"]["source_workspace_id"] == "wks_http"

        request = Request(url, headers={"Authorization": f"Bearer {token}"})
        with urlopen(request) as response:
            raw_body = response.read()
        assert b"\n" not in raw_body
        assert json.loads(raw_body.decode("utf-8"))["result"]["snapshot"] == expected
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
