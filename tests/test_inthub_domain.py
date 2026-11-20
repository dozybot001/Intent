"""IntHub answers at inthub.tenonai.cn and trusts only the Tenon issuer that answers discovery."""

import re
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
    PLATFORM_ROLE, TenonOIDCClient, account_for_identity, account_for_session, configured_issuers, create_session,
)
from intent_cli import __version__
from intent_cli.hub import client
from intent_cli.hub.credentials import global_api_base_url, normalize_api_base_url

ROOT = Path(__file__).resolve().parents[1]
OTHER, NEW = "https://account.example/api/auth", "https://account.tenonai.cn/api/auth"
# The company's ICP filing for tenonai.cn.
FILING = "湘ICP备2026054319号-1"
# Its public-security filing, shown right after the ICP one and linked to the ministry's lookup.
PSB_FILING = "湘公网安备43010202002408号"


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


def test_only_the_moved_issuer_is_ever_asked():
    assert configured_issuers() == (NEW,)


def test_the_role_claim_has_the_account_services_name():
    assert PLATFORM_ROLE == "https://tenonai.cn/claims/platform_role"


def test_sign_in_uses_the_issuer_that_answers_and_keeps_the_same_account(tmp_path):
    answering = NEW
    target = str(tmp_path / "db")
    before = account_for_identity(target, {"sub": "central-1", "platform_role": "user", "expires_at": time.time() + 60})
    client, attempt, asked = tenon(answering)
    url = urlsplit(client.authorization_url("https://inthub.tenonai.cn/api/v1/auth/tenon/callback", attempt))
    assert f"{url.scheme}://{url.netloc}{url.path}" == answering + "/oauth2/authorize"
    assert client.issuer() == answering
    identity = client.complete_login("code", "https://inthub.tenonai.cn/api/v1/auth/tenon/callback", attempt)
    assert account_for_identity(target, identity)["id"] == before["id"], "the same sub is the same IntHub account"
    assert all(request.startswith(answering) for request in asked[1:]), "every call after discovery goes to one issuer"


def test_a_token_from_the_issuer_not_in_use_is_rejected():
    client, attempt, _ = tenon(NEW, token_issuer=OTHER)
    with pytest.raises(Exception, match="could not be verified"):
        client.complete_login("code", "https://inthub.tenonai.cn/api/v1/auth/tenon/callback", attempt)
    assert client.app.server_metadata == {}, "a failed sign-in discovers the issuer again"


def test_a_redirect_is_never_followed_with_or_without_credentials(monkeypatch):
    monkeypatch.setenv("INTHUB_TENON_ISSUERS", OTHER)
    client, attempt, asked = tenon(NEW)
    with pytest.raises(Exception, match="temporarily unavailable"):
        client.authorization_url("https://inthub.tenonai.cn/api/v1/auth/tenon/callback", attempt)
    assert asked == [OTHER + "/.well-known/openid-configuration"], "the 308 to tenonai.cn is not followed"


@pytest.mark.parametrize("field, endpoint", [
    ("jwks_uri", "https://account.tenonai.cn/other/jwks"), ("token_endpoint", OTHER + "/oauth2/token")])
def test_endpoints_must_sit_under_the_issuer_that_answered(field, endpoint):
    client, attempt, _ = tenon(NEW, metadata_overrides={field: endpoint})
    with pytest.raises(Exception, match="temporarily unavailable"):
        client.authorization_url("https://inthub.tenonai.cn/api/v1/auth/tenon/callback", attempt)


def test_an_operator_can_pin_the_issuer(monkeypatch):
    monkeypatch.setenv("INTHUB_TENON_ISSUERS", OTHER)
    client, attempt, asked = tenon(OTHER)
    client.authorization_url("https://inthub.tenonai.cn/api/v1/auth/tenon/callback", attempt)
    assert not any(request.startswith(NEW) for request in asked)
    monkeypatch.setenv("INTHUB_TENON_ISSUERS", "http://account.example/api/auth")
    with pytest.raises(ValueError):
        configured_issuers()


def test_deletion_goes_to_the_issuer_in_use_and_accepts_only_its_proofs():
    calls = []

    def request(url, **kwargs):
        calls.append(url)
        return httpx.Response(200, json={"url": "https://account.tenonai.cn/account/delete/?request=" + "f" * 43,
                                         "expiresAt": time.time() * 1000 + 60000})
    client = ProductDeletionClient("client", "secret", request=request, issuer=lambda: NEW)
    client.start("central-1")
    assert calls == [NEW + "/product-deletion/start"]
    operation = "f8132b30-0471-4a4b-95d7-a9f2fe6f4df7"
    validate_proof({"issuer": NEW, "sub": "s", "productId": "inthub", "operationId": operation}, operation)
    for issuer in (OTHER, "https://account.tenon.example"):
        with pytest.raises(Exception):
            validate_proof({"issuer": issuer, "sub": "s", "productId": "inthub", "operationId": operation}, operation)


class CallbackRecorder:
    def __init__(self):
        self.redirect_uris = []

    def authorization_url(self, redirect_uri, attempt):
        self.redirect_uris.append(redirect_uri)
        return NEW + "/oauth2/authorize?state=" + attempt["state"]


def test_the_hub_serves_its_name_with_its_callback_and_filings(tmp_path):
    provider = CallbackRecorder()
    origins = "https://inthub.tenonai.cn"
    handler = make_handler(str(tmp_path / "db"), serve_web=True, tenon_client_id="c", tenon_client_secret="s",
                           oauth_client=provider, deletion_client=object(), public_api_base_url=origins,
                           allowed_origins=origins)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        for name in ("inthub.tenonai.cn",):
            origin = "https://" + name
            config = httpx.get(base + "/config.json", headers={"Host": name}).json()
            assert config["apiBaseUrl"] == origin
            response = httpx.post(base + "/api/v1/auth/tenon/prepare", json={"return_to": "/"},
                                  headers={"Host": name, "Origin": origin})
            assert response.status_code == 200 and response.headers["Access-Control-Allow-Origin"] == origin
            assert provider.redirect_uris[-1] == origin + "/api/v1/auth/tenon/callback"
            assert "Domain=" not in response.headers["Set-Cookie"], "cookies stay with the name that set them"
            page = httpx.get(base + "/", headers={"Host": name}).text
            assert re.findall(r"湘ICP备\d+号-\d+", page) == [FILING, FILING]
            footers = re.findall(r'>(湘ICP备[^<]+)</a>\s*<a href="([^"]+)" target="_blank" rel="noopener noreferrer">(湘公网安备[^<]+)</a>', page)
            assert footers == [(FILING, "https://beian.mps.gov.cn/#/query/webSearch?code=43010202002408", PSB_FILING)] * 2
        assert httpx.get(base + "/config.json", headers={"Host": "inthub.example"}).status_code == 403
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_the_cli_defaults_to_the_hosted_hub(monkeypatch, tmp_path):
    monkeypatch.setenv("INTENT_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "missing-gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    assert global_api_base_url() == "https://inthub.tenonai.cn"
    assert normalize_api_base_url("https://inthub.example/") == "https://inthub.example"


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


def test_the_release_proxies_its_one_site_to_the_candidate(tmp_path):
    out = tmp_path / "site.caddy"
    subprocess.run(["bash", "-c", shell_function("render_caddy") + 'render_caddy "$@"', "-",
                    str(ROOT / "deploy" / "inthub" / "inthub.caddy"), str(out), "7251"], check=True)
    site = out.read_text(encoding="utf-8")
    assert site.startswith("inthub.tenonai.cn {\n") and "reverse_proxy 127.0.0.1:7251" in site
    assert "7250" not in site and site.count("import access_log") == 1
    third = tmp_path / "third.caddy"
    third.write_text(site.replace("7251", "7250") + "\nextra.example {\n\treverse_proxy 127.0.0.1:7250\n}\n")
    refused = subprocess.run(["bash", "-c", shell_function("render_caddy") + 'render_caddy "$@"', "-",
                              str(third), str(out), "7251"], capture_output=True, text=True)
    assert refused.returncode != 0 and "exactly one upstream" in refused.stderr


def test_the_new_name_is_canonical_everywhere_the_release_and_monitors_look():
    deploy = ROOT / "deploy" / "inthub"
    compose = (deploy / "compose.yaml").read_text(encoding="utf-8")
    assert "INTHUB_API_BASE_URL: https://${INTHUB_DOMAIN:?set INTHUB_DOMAIN}\n" in compose and "EXTRA_ORIGINS" not in compose
    remote = (deploy / "remote-release.sh").read_text(encoding="utf-8")
    assert 'PUBLIC_URL="https://inthub.tenonai.cn"' in remote
    assert '"INTHUB_DOMAIN=${PUBLIC_URL#https://}"' in remote and "EXTRA_ORIGINS" not in remote
    assert remote.count('INTHUB_BASE_URL="${PUBLIC_URL}"') == 3
    smoke = (deploy / "smoke.sh").read_text(encoding="utf-8")
    assert 'BASE_URL="${INTHUB_BASE_URL:-https://inthub.tenonai.cn}"' in smoke
    assert 'target.netloc == "account.tenonai.cn"' in smoke
    assert 'PUBLIC_URL="https://inthub.tenonai.cn"' in (deploy / "release.sh").read_text(encoding="utf-8")
    assert 'BASE_URL="https://inthub.tenonai.cn"' in (deploy / "monitor.sh").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "monitor.yml").read_text(encoding="utf-8")
    assert "inthub.tenonai.cn/readyz" in workflow
    security = (ROOT / "apps" / "inthub_web" / "static" / "security.txt").read_text(encoding="utf-8")
    assert [line for line in security.splitlines() if line.startswith("Canonical:")] == [
        "Canonical: https://inthub.tenonai.cn/.well-known/security.txt"]


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


def test_migrations_10_and_11_move_identities_to_the_new_issuer(tmp_path):
    from apps.inthub_api import db_migrate
    from apps.inthub_api.db_schema import IDENTITY_ISSUER, PREVIOUS_IDENTITY_ISSUER
    target = str(tmp_path / "db")
    identity = {"sub": "central-1", "platform_role": "user", "expires_at": time.time() + 60}
    account = account_for_identity(target, identity)
    session = create_session(target, account["id"], identity)
    with connect(target) as conn:
        # Put the database back where 8.2.14 left it: everything under the old issuer.
        conn.execute("UPDATE account_identities SET issuer = ?", (PREVIOUS_IDENTITY_ISSUER,))
        conn.execute("UPDATE tenon_session_grants SET issuer = ?", (PREVIOUS_IDENTITY_ISSUER,))
        conn.execute("INSERT INTO product_deletion_receipts VALUES (?, ?, ?, ?)",
                     ("op-1", PREVIOUS_IDENTITY_ISSUER, "gone-1", days_ago(1)))
        conn.execute("DELETE FROM schema_migrations WHERE version IN (10, 11)")
    assert account_for_session(target, session["token"]) is None
    with connect(target) as conn:
        db_migrate.migrate_db(conn)
    with connect(target) as conn:
        issuers = {row["issuer"] for row in conn.execute("SELECT issuer FROM account_identities")}
        assert issuers == {IDENTITY_ISSUER}
        assert {row["issuer"] for row in conn.execute("SELECT issuer FROM product_deletion_receipts")} == {IDENTITY_ISSUER}
    assert account_for_identity(target, identity)["id"] == account["id"], "the same account signs in"
    assert account_for_session(target, session["token"])["id"] == account["id"], "signed-in sessions carry on"
    with pytest.raises(Exception, match="account deletion"):
        account_for_identity(target, {"sub": "gone-1", "platform_role": "user", "expires_at": time.time() + 60})
