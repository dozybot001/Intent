import base64
import hashlib
import time
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from authlib.jose import JsonWebKey, jwt

from apps.inthub_api.auth import create_account_access_token, account_for_access_token, create_web_session, upsert_github_account
from apps.inthub_api.common import APIError
from apps.inthub_api.db import connect
from apps.inthub_api.tenon import (
    ISSUER, PLATFORM_ROLE, TenonOIDCClient, account_for_identity, account_for_session,
    bind_existing_account, consume_attempt, create_attempt, create_session,
)


def identity(subject="central-1", role="user"):
    return {"sub": subject, "name": "Same name", "platform_role": role, "expires_at": time.time() + 900}


def test_explicit_mapping_preserves_business_id_projects_pat_and_role(tmp_path):
    target = str(tmp_path / "db")
    original = upsert_github_account(target, {"id": 1, "login": "original", "name": "Same name"})
    pat = create_account_access_token(target, original["id"])
    bind_existing_account(target, original["id"], "central-1")
    bind_existing_account(target, original["id"], "central-1")
    assert account_for_identity(target, identity())["id"] == original["id"]
    assert account_for_access_token(target, pat["token"])["id"] == original["id"]
    other = account_for_identity(target, identity("central-2"))
    assert other["id"] != original["id"]
    with pytest.raises(APIError, match="already bound"):
        bind_existing_account(target, other["id"], "central-1")
    with pytest.raises(APIError, match="already bound"):
        bind_existing_account(target, original["id"], "central-3")
    admin = create_session(target, original["id"], identity(role="admin"), ttl_seconds=604800)
    assert admin["ttl_seconds"] <= 900
    assert account_for_session(target, admin["token"])["role"] == "admin"
    assert account_for_access_token(target, pat["token"])["role"] == "member"
    ordinary = create_session(target, original["id"], identity())
    assert account_for_session(target, ordinary["token"])["role"] == "member"
    assert account_for_session(target, create_web_session(target, original["id"])["token"]) is None
    with connect(target) as conn:
        conn.execute("UPDATE web_sessions SET expires_at = '2000-01-01T00:00:00+00:00'")
    assert account_for_session(target, admin["token"]) is None


def test_attempt_nonce_pkce_single_use_and_expiration(tmp_path):
    target = str(tmp_path / "db")
    attempt = create_attempt(target, "//external.example")
    consumed = consume_attempt(target, attempt["state"])
    assert consumed["nonce"] == attempt["nonce"]
    assert consumed["code_verifier"] == attempt["code_verifier"]
    assert consumed["return_to"] == "/"
    with pytest.raises(APIError):
        consume_attempt(target, attempt["state"])
    expired = create_attempt(target, ttl_seconds=-1)
    with pytest.raises(APIError):
        consume_attempt(target, expired["state"])


def protocol_client(overrides=None, info_overrides=None, bad_signature=False):
    key = JsonWebKey.generate_key("OKP", "Ed25519", {"kid": "test", "alg": "EdDSA", "use": "sig"}, is_private=True)
    public = key.as_dict(is_private=False)
    attempt = {"state": "state", "nonce": "nonce", "code_verifier": "verifier" * 8}
    claims = {"iss": ISSUER, "sub": "central-1", "aud": "client", "iat": int(time.time()),
              "exp": int(time.time()) + 600, "nonce": "nonce", PLATFORM_ROLE: "admin"}
    claims.update(overrides or {})
    metadata = {"issuer": ISSUER, "authorization_endpoint": ISSUER + "/oauth2/authorize",
                "token_endpoint": ISSUER + "/oauth2/token", "userinfo_endpoint": ISSUER + "/oauth2/userinfo",
                "jwks_uri": ISSUER + "/jwks", "code_challenge_methods_supported": ["S256"],
                "id_token_signing_alg_values_supported": ["EdDSA"]}
    signed = jwt.encode({"alg": "EdDSA", "kid": "test"}, claims,
                        JsonWebKey.generate_key("OKP", "Ed25519", is_private=True) if bad_signature else key).decode()

    def handler(request):
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(200, json=metadata)
        if request.url.path.endswith("/token"):
            assert request.headers["authorization"] == "Basic " + base64.b64encode(b"client:secret").decode()
            assert parse_qs(request.content.decode())["code_verifier"] == [attempt["code_verifier"]]
            return httpx.Response(200, json={"access_token": "ephemeral", "token_type": "Bearer", "expires_in": 600, "id_token": signed})
        if request.url.path.endswith("/jwks"):
            return httpx.Response(200, json={"keys": [public]})
        assert request.headers["authorization"] == "Bearer ephemeral"
        info = {"sub": "central-1", "name": "Dozy", "email_verified": True, PLATFORM_ROLE: "admin"}
        info.update(info_overrides or {})
        return httpx.Response(200, json=info)

    client = TenonOIDCClient("client", "secret")
    client.app.client_kwargs["transport"] = httpx.MockTransport(handler)
    return client, attempt


def test_real_oidc_library_validates_signed_tokens_and_userinfo():
    client, attempt = protocol_client()
    url = client.authorization_url("https://inthub.example/callback", attempt)
    query = parse_qs(urlsplit(url).query)
    assert query["nonce"] == [attempt["nonce"]]
    assert query["state"] == [attempt["state"]]
    assert query["scope"] == ["openid profile email"]
    expected = base64.urlsafe_b64encode(hashlib.sha256(attempt["code_verifier"].encode()).digest()).rstrip(b"=").decode()
    assert query["code_challenge"] == [expected]
    result = client.complete_login("code", "https://inthub.example/callback", attempt)
    assert result["sub"] == "central-1"
    assert result["platform_role"] == "admin"
    assert "access_token" not in result and "id_token" not in result


@pytest.mark.parametrize("overrides", [
    {"iss": "https://other.example"}, {"aud": "other"}, {"nonce": "other"},
    {"exp": 1}, {"nonce": None, "nonce_supported": False}, {PLATFORM_ROLE: "user"},
])
def test_invalid_signed_claims_are_rejected(overrides):
    client, attempt = protocol_client(overrides=overrides)
    with pytest.raises(APIError):
        client.complete_login("code", "https://inthub.example/callback", attempt)


@pytest.mark.parametrize("overrides", [{"sub": "other"}, {"email_verified": False}, {PLATFORM_ROLE: "user"}])
def test_userinfo_must_match_verified_identity(overrides):
    client, attempt = protocol_client(info_overrides=overrides)
    with pytest.raises(APIError):
        client.complete_login("code", "https://inthub.example/callback", attempt)


def test_bad_signature_is_rejected():
    client, attempt = protocol_client(bad_signature=True)
    with pytest.raises(APIError):
        client.complete_login("code", "https://inthub.example/callback", attempt)
