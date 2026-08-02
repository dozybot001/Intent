from urllib.parse import parse_qs, urlparse

import pytest

from apps.inthub_api.auth import (
    GitHubOAuthClient,
    account_for_session,
    consume_login_attempt,
    create_login_attempt,
    create_web_session,
    delete_web_session,
    github_user_allowed,
    safe_return_to,
    upsert_github_account,
)
from apps.inthub_api.common import APIError
from apps.inthub_api.db import connect


def test_login_attempt_uses_pkce_is_single_use_and_rejects_external_return(tmp_path):
    db_path = str(tmp_path / "inthub.db")
    attempt = create_login_attempt(db_path, return_to="https://attacker.example/path")

    assert attempt["return_to"] == "/"
    assert len(attempt["code_challenge"]) == 43
    consumed = consume_login_attempt(db_path, attempt["state"])
    assert consumed["code_verifier"] == attempt["code_verifier"]
    assert consumed["return_to"] == "/"

    with pytest.raises(APIError) as exc_info:
        consume_login_attempt(db_path, attempt["state"])
    assert exc_info.value.code == "OAUTH_STATE_INVALID"


def test_github_account_and_hashed_database_session_lifecycle(tmp_path):
    db_path = str(tmp_path / "inthub.db")
    account = upsert_github_account(
        db_path,
        {
            "id": 12345,
            "login": "dozy",
            "name": "Dozy",
            "avatar_url": "https://avatars.example/dozy.png",
        },
    )
    session = create_web_session(db_path, account["id"], ttl_seconds=3600)

    assert account["role"] == "owner"
    assert account_for_session(db_path, session["token"])["login"] == "dozy"
    with connect(db_path) as conn:
        row = conn.execute("SELECT token_hash FROM web_sessions").fetchone()
    assert row["token_hash"] != session["token"]

    delete_web_session(db_path, session["token"])
    assert account_for_session(db_path, session["token"]) is None


def test_only_first_account_is_owner(tmp_path):
    db_path = str(tmp_path / "inthub.db")
    first = upsert_github_account(db_path, {"id": 1, "login": "first"})
    second = upsert_github_account(db_path, {"id": 2, "login": "second"})

    assert first["role"] == "owner"
    assert second["role"] == "member"


def test_github_allowlist_and_safe_return_to():
    user = {"id": 42, "login": "Dozy"}
    assert github_user_allowed(user, allowed_user_ids={"42"}) is True
    assert github_user_allowed(user, allowed_user_ids={"43"}) is False
    assert safe_return_to("/projects/demo?tab=snaps") == "/projects/demo?tab=snaps"
    assert safe_return_to("//attacker.example") == "/"
    assert safe_return_to("https://attacker.example") == "/"
    assert safe_return_to("/\\attacker.example") == "/"
    assert safe_return_to("/safe\r\nX-Injected: yes") == "/"


def test_github_authorization_url_requests_pkce_without_repository_scope():
    client = GitHubOAuthClient("client-id", "client-secret")
    location = client.authorization_url(
        "https://inthub.example/api/v1/auth/github/callback",
        "state-value",
        "challenge-value",
    )
    query = parse_qs(urlparse(location).query)

    assert query["client_id"] == ["client-id"]
    assert query["state"] == ["state-value"]
    assert query["code_challenge"] == ["challenge-value"]
    assert query["code_challenge_method"] == ["S256"]
    assert "scope" not in query
