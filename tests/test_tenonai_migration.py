"""IntHub and the CLI work under tenon.asia and tenonai.cn at once while both move."""

import json
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest
from authlib.jose import JsonWebKey, jwt

from apps.inthub_api import admin
from apps.inthub_api.auth import account_for_access_token, create_account_access_token
from apps.inthub_api.db import connect
from apps.inthub_api.product_deletion import ProductDeletionClient, validate_proof
from apps.inthub_api.server import make_handler
from apps.inthub_api.tenon import (
    ISSUER, PLATFORM_ROLE, TenonOIDCClient, account_for_identity, account_for_session, configured_issuers, create_session,
)
from intent_cli import __version__
from intent_cli.hub import client
from intent_cli.hub.credentials import (
    credentials_file, erase_access_token, global_api_base_url, load_access_token, normalize_api_base_url,
)

ROOT = Path(__file__).resolve().parents[1]
OLD, NEW = "https://account.tenon.asia/api/auth", "https://account.tenonai.cn/api/auth"
# The company's filing for tenonai.cn, then the one tenon.asia was filed under.
FILINGS = ("湘ICP备2026054319号-1", "湘ICP备2026031578号-1")


def tenon(answering, token_issuer=None, moved_reply=308, metadata_overrides=None):
    """A Tenon client whose discovery only `answering` serves; the other host fails or redirects."""
    key = JsonWebKey.generate_key("OKP", "Ed25519", {"kid": "k", "alg": "EdDSA", "use": "sig"}, is_private=True)
    attempt = {"state": "state", "nonce": "nonce", "code_verifier": "verifier" * 8}
    claims = {"iss": token_issuer or answering, "sub": "central-1", "aud": "client", "iat": int(time.time()),
              "exp": int(time.time()) + 600, "nonce": "nonce", PLATFORM_ROLE: "user"}
    asked = []

    def handler(request):
        asked.append(str(request.url))
        if not str(request.url).startswith(answering):
            if moved_reply is None:
                raise httpx.ConnectError("no such host", request=request)
            return httpx.Response(moved_reply, headers={"Location": answering + "/.well-known/openid-configuration"})
        path = request.url.path
        if path.endswith("openid-configuration"):
            return httpx.Response(200, json={
                "issuer": answering, "authorization_endpoint": answering + "/oauth2/authorize",
                "token_endpoint": answering + "/oauth2/token", "userinfo_endpoint": answering + "/oauth2/userinfo",
                "jwks_uri": answering + "/jwks", "code_challenge_methods_supported": ["S256"],
                "id_token_signing_alg_values_supported": ["EdDSA"], **(metadata_overrides or {})})
        if path.endswith("/token"):
            signed = jwt.encode({"alg": "EdDSA", "kid": "k"}, claims, key).decode()
            return httpx.Response(200, json={"access_token": "a", "token_type": "Bearer", "expires_in": 600, "id_token": signed})
        if path.endswith("/jwks"):
            return httpx.Response(200, json={"keys": [key.as_dict(is_private=False)]})
        return httpx.Response(200, json={"sub": "central-1", "email_verified": True, PLATFORM_ROLE: "user"})

    client = TenonOIDCClient("client", "secret")
    client.app.client_kwargs["transport"] = httpx.MockTransport(handler)
    return client, attempt, asked


@pytest.mark.parametrize("order, answering, moved_reply", [
    # Before the move tenonai.cn has no account host; after it, tenon.asia only redirects.
    (None, OLD, None), (None, NEW, 308), (f"{OLD} {NEW}", NEW, 308)])
def test_sign_in_follows_whichever_issuer_answers_and_keeps_the_same_account(
        tmp_path, monkeypatch, order, answering, moved_reply):
    if order:
        monkeypatch.setenv("INTHUB_TENON_ISSUERS", order)
    target = str(tmp_path / "db")
    before = account_for_identity(target, {"sub": "central-1", "platform_role": "user", "expires_at": time.time() + 60})
    client, attempt, asked = tenon(answering, moved_reply=moved_reply)
    url = urlsplit(client.authorization_url("https://inthub.tenonai.cn/api/v1/auth/tenon/callback", attempt))
    assert f"{url.scheme}://{url.netloc}{url.path}" == answering + "/oauth2/authorize"
    assert client.issuer() == answering
    identity = client.complete_login("code", "https://inthub.tenonai.cn/api/v1/auth/tenon/callback", attempt)
    assert account_for_identity(target, identity)["id"] == before["id"], "the same sub is the same IntHub account"
    assert all(request.startswith(answering) for request in asked[1:]), "every call after discovery goes to one issuer"


def test_a_token_from_the_issuer_not_in_use_is_rejected():
    client, attempt, _ = tenon(NEW, token_issuer=OLD)
    with pytest.raises(Exception, match="could not be verified"):
        client.complete_login("code", "https://inthub.tenon.asia/api/v1/auth/tenon/callback", attempt)
    assert client.app.server_metadata == {}, "a failed sign-in discovers the issuer again"


def test_a_redirect_is_never_followed_with_or_without_credentials(monkeypatch):
    monkeypatch.setenv("INTHUB_TENON_ISSUERS", OLD)
    client, attempt, asked = tenon(NEW)
    with pytest.raises(Exception, match="temporarily unavailable"):
        client.authorization_url("https://inthub.tenon.asia/api/v1/auth/tenon/callback", attempt)
    assert asked == [OLD + "/.well-known/openid-configuration"], "the 308 to tenonai.cn is not followed"


@pytest.mark.parametrize("field, endpoint", [
    ("jwks_uri", "https://account.tenonai.cn/other/jwks"), ("token_endpoint", OLD + "/oauth2/token")])
def test_endpoints_must_sit_under_the_issuer_that_answered(field, endpoint):
    client, attempt, _ = tenon(NEW, metadata_overrides={field: endpoint})
    with pytest.raises(Exception, match="temporarily unavailable"):
        client.authorization_url("https://inthub.tenon.asia/api/v1/auth/tenon/callback", attempt)


def test_an_operator_can_pin_the_issuer(monkeypatch):
    monkeypatch.setenv("INTHUB_TENON_ISSUERS", OLD)
    client, attempt, asked = tenon(OLD)
    client.authorization_url("https://inthub.tenon.asia/api/v1/auth/tenon/callback", attempt)
    assert not any(request.startswith(NEW) for request in asked)
    monkeypatch.setenv("INTHUB_TENON_ISSUERS", "http://account.example/api/auth")
    with pytest.raises(ValueError):
        configured_issuers()


def test_deletion_goes_to_the_issuer_in_use_and_accepts_its_proofs():
    calls = []

    def request(url, **kwargs):
        calls.append(url)
        return httpx.Response(200, json={"url": "https://account.tenonai.cn/account/delete/?request=" + "f" * 43,
                                         "expiresAt": time.time() * 1000 + 60000})
    client = ProductDeletionClient("client", "secret", request=request, issuer=lambda: NEW)
    client.start("central-1")
    assert calls == [NEW + "/product-deletion/start"]
    operation = "f8132b30-0471-4a4b-95d7-a9f2fe6f4df7"
    for issuer in (OLD, NEW):
        validate_proof({"issuer": issuer, "sub": "s", "productId": "inthub", "operationId": operation}, operation)
    with pytest.raises(Exception):
        validate_proof({"issuer": "https://account.example", "sub": "s", "productId": "inthub",
                        "operationId": operation}, operation)
    assert ISSUER == OLD, "receipts and identities stay under the issuer they were stored with"


class CallbackRecorder:
    def __init__(self):
        self.redirect_uris = []

    def authorization_url(self, redirect_uri, attempt):
        self.redirect_uris.append(redirect_uri)
        return NEW + "/oauth2/authorize?state=" + attempt["state"]


def test_one_hub_serves_both_names_with_their_own_callbacks(tmp_path):
    provider = CallbackRecorder()
    origins = "https://inthub.tenon.asia,https://inthub.tenonai.cn"
    handler = make_handler(str(tmp_path / "db"), serve_web=True, tenon_client_id="c", tenon_client_secret="s",
                           oauth_client=provider, deletion_client=object(), public_api_base_url=origins,
                           allowed_origins=origins)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        for name in ("inthub.tenon.asia", "inthub.tenonai.cn"):
            origin = "https://" + name
            config = httpx.get(base + "/config.json", headers={"Host": name}).json()
            assert config["apiBaseUrl"] == origin
            response = httpx.post(base + "/api/v1/auth/tenon/prepare", json={"return_to": "/"},
                                  headers={"Host": name, "Origin": origin})
            assert response.status_code == 200 and response.headers["Access-Control-Allow-Origin"] == origin
            assert provider.redirect_uris[-1] == origin + "/api/v1/auth/tenon/callback"
            assert "Domain=" not in response.headers["Set-Cookie"], "cookies stay with the name that set them"
            # Only tenonai.cn serves pages now (Caddy moves the old name's), so they carry its ICP filing.
            page = httpx.get(base + "/", headers={"Host": name}).text
            assert page.count(FILINGS[0]) == 2 and FILINGS[1] not in page
        assert httpx.get(base + "/config.json", headers={"Host": "inthub.example"}).status_code == 403
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_the_cli_uses_the_new_name_and_keeps_the_old_one_only_as_an_alias(monkeypatch, tmp_path):
    monkeypatch.setenv("INTENT_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "missing-gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    assert global_api_base_url() == "https://inthub.tenonai.cn"
    # A remote or global config written before the move is read as the new name, so the old one is never contacted.
    assert normalize_api_base_url("https://inthub.tenon.asia/") == "https://inthub.tenonai.cn"
    assert normalize_api_base_url("https://inthub.example") == "https://inthub.example"
    # A token saved under the old name before the move still signs requests, so nobody signs in again.
    credentials_file().parent.mkdir(parents=True, exist_ok=True)
    credentials_file().write_text(json.dumps({"https://inthub.tenon.asia": "ith_pat_before"}), encoding="utf-8")
    assert load_access_token("https://inthub.tenonai.cn") == "ith_pat_before"
    erase_access_token("https://inthub.tenonai.cn")
    assert load_access_token("https://inthub.tenon.asia") is None


def test_every_hub_request_names_the_cli_and_its_version(monkeypatch):
    sent = []

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, limit):
            return b'{"ok": true, "result": {}}'

    monkeypatch.setattr(client, "_open_request", lambda request, timeout: sent.append(request) or Reply())
    client.http_json("GET", "https://inthub.tenonai.cn/api/v1/projects", token="ith_pat_x")
    assert sent[0].get_header("User-agent") == f"intent-cli/{__version__}"


def shell_function(name):
    script = (ROOT / "deploy" / "inthub" / "remote-release.sh").read_text(encoding="utf-8")
    start = script.index(f"{name}() {{")
    return script[start:script.index("\n}\n", start) + 3]


def test_the_release_serves_both_names_from_the_candidate(tmp_path):
    out = tmp_path / "site.caddy"
    subprocess.run(["bash", "-c", shell_function("render_caddy") + 'render_caddy "$@"', "-",
                    str(ROOT / "deploy" / "inthub" / "inthub.caddy"), str(out), "7251"], check=True)
    site = out.read_text(encoding="utf-8")
    new, old = site.split("\ninthub.tenon.asia {\n")
    assert new.startswith("inthub.tenonai.cn {\n") and "reverse_proxy 127.0.0.1:7251" in new
    assert "7250" not in site and site.count("import access_log") == 2
    # The old name answers older CLIs and moves everything else, so it never starts a web session.
    route = old[old.index("route {"):]
    steps = ["respond @trace 405", "redir @web_sign_in https://inthub.tenonai.cn{uri} 301",
             "reverse_proxy @cli 127.0.0.1:7251", "redir https://inthub.tenonai.cn{uri} 301"]
    assert [route.index(step) for step in steps] == sorted(route.index(step) for step in steps)
    assert "@web_sign_in path /api/v1/auth/tenon/*" in old and "@cli path /api/* /healthz /readyz" in old
    third = tmp_path / "third.caddy"
    third.write_text(site.replace("7251", "7250") + "\nextra.example {\n\treverse_proxy 127.0.0.1:7250\n}\n")
    refused = subprocess.run(["bash", "-c", shell_function("render_caddy") + 'render_caddy "$@"', "-",
                              str(third), str(out), "7251"], capture_output=True, text=True)
    assert refused.returncode != 0 and "one upstream in each site" in refused.stderr


def test_the_new_name_is_canonical_everywhere_the_release_and_monitors_look():
    deploy = ROOT / "deploy" / "inthub"
    compose = (deploy / "compose.yaml").read_text(encoding="utf-8")
    assert "INTHUB_API_BASE_URL: https://${INTHUB_DOMAIN:?set INTHUB_DOMAIN}${INTHUB_EXTRA_ORIGINS:-}" in compose
    remote = (deploy / "remote-release.sh").read_text(encoding="utf-8")
    assert 'PUBLIC_URL="https://inthub.tenonai.cn"' in remote and 'OLD_URL="https://inthub.tenon.asia"' in remote
    assert '"INTHUB_DOMAIN=${PUBLIC_URL#https://}"' in remote and '"INTHUB_EXTRA_ORIGINS=,${OLD_URL}"' in remote
    # Every public smoke run also checks what the old name still answers and what it moves.
    assert remote.count('INTHUB_BASE_URL="${PUBLIC_URL}"') == remote.count('INTHUB_OLD_URL="${OLD_URL}"') == 3
    smoke = (deploy / "smoke.sh").read_text(encoding="utf-8")
    assert 'BASE_URL="${INTHUB_BASE_URL:-https://inthub.tenonai.cn}"' in smoke and "check_old_name" in smoke
    assert 'target.netloc == "account.tenonai.cn"' in smoke
    assert 'PUBLIC_URL="https://inthub.tenonai.cn"' in (deploy / "release.sh").read_text(encoding="utf-8")
    assert 'BASE_URL="https://inthub.tenonai.cn"' in (deploy / "monitor.sh").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "monitor.yml").read_text(encoding="utf-8")
    assert "inthub.tenonai.cn/readyz" in workflow and "tenon.asia" not in workflow


def days_ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def test_s2_retires_every_cli_token_issued_before_it(tmp_path, capsys):
    target = str(tmp_path / "db")
    account = account_for_identity(target, {"sub": "central-1", "platform_role": "user", "expires_at": time.time() + 60})
    old, older, revoked, fresh = (create_account_access_token(target, account["id"]) for _ in range(4))
    with connect(target) as conn:
        for token, age in ((old, 3), (older, 40), (revoked, 5)):
            conn.execute("UPDATE account_access_tokens SET created_at = ? WHERE id = ?", (days_ago(age), token["id"]))
        conn.execute("UPDATE account_access_tokens SET revoked_at = ? WHERE id = ?", (days_ago(1), revoked["id"]))
    cutoff = days_ago(1)
    admin.main(["retire-tokens", cutoff, "--dry-run", "--database-url", target])
    assert '"would_retire": 2' in capsys.readouterr().out
    assert account_for_access_token(target, old["token"]) is not None, "a dry run changes nothing"
    assert admin.retire_tokens(target, cutoff)["retired"] == 2
    assert account_for_access_token(target, old["token"]) is None and account_for_access_token(target, older["token"]) is None
    assert account_for_access_token(target, fresh["token"])["id"] == account["id"], "tokens issued after S2 stay"
    with pytest.raises(SystemExit):
        admin.retire_tokens(target, "2027-01-15T00:00:00")


def test_web_sessions_never_outlive_thirty_days_from_sign_in(tmp_path):
    target = str(tmp_path / "db")
    identity = {"sub": "central-1", "platform_role": "user", "expires_at": time.time() + 60}
    account = account_for_identity(target, identity)
    session = create_session(target, account["id"], identity, ttl_seconds=90 * 24 * 60 * 60)
    assert session["ttl_seconds"] == 30 * 24 * 60 * 60
    with connect(target) as conn:
        # Even a session row pushed past 30 days ends 30 days after its sign-in: there is no renewal.
        conn.execute("UPDATE web_sessions SET expires_at = ?", ((datetime.now(timezone.utc) + timedelta(days=60)).isoformat(),))
        conn.execute("UPDATE tenon_session_grants SET verified_at = ?", (days_ago(31),))
    assert account_for_session(target, session["token"]) is None
