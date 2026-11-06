"""IntHub and the CLI work under tenon.asia and tenonai.cn at once while both move."""

import subprocess
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest
from authlib.jose import JsonWebKey, jwt

from apps.inthub_api.product_deletion import ProductDeletionClient, validate_proof
from apps.inthub_api.server import make_handler
from apps.inthub_api.tenon import ISSUER, PLATFORM_ROLE, TenonOIDCClient, account_for_identity, configured_issuers
from intent_cli.hub.credentials import erase_access_token, load_access_token, normalize_api_base_url, store_access_token

ROOT = Path(__file__).resolve().parents[1]
OLD, NEW = "https://account.tenon.asia/api/auth", "https://account.tenonai.cn/api/auth"


def tenon(answering, token_issuer=None, moved_reply=308):
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
                "id_token_signing_alg_values_supported": ["EdDSA"]})
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
        assert httpx.get(base + "/config.json", headers={"Host": "inthub.example"}).status_code == 403
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_the_cli_treats_both_hosted_names_as_one_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("INTENT_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "missing-gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    assert normalize_api_base_url("https://inthub.tenonai.cn/") == "https://inthub.tenon.asia"
    assert normalize_api_base_url("https://inthub.example") == "https://inthub.example"
    store_access_token("https://inthub.tenonai.cn", "ith_pat_hosted")
    assert load_access_token("https://inthub.tenon.asia") == "ith_pat_hosted"
    erase_access_token("https://inthub.tenonai.cn")
    assert load_access_token("https://inthub.tenon.asia") is None


def shell_function(name):
    script = (ROOT / "deploy" / "inthub" / "remote-release.sh").read_text(encoding="utf-8")
    start = script.index(f"{name}() {{")
    return script[start:script.index("\n}\n", start) + 3]


def test_the_release_merges_the_new_name_into_the_one_site_block(tmp_path):
    out = tmp_path / "site.caddy"
    for extra, address in (("", "inthub.tenon.asia {\n"), ("inthub.tenonai.cn", "inthub.tenon.asia, inthub.tenonai.cn {\n")):
        subprocess.run(["bash", "-c", shell_function("render_caddy") + 'render_caddy "$@"', "-",
                        str(ROOT / "deploy" / "inthub" / "inthub.caddy"), str(out), "7251", extra], check=True)
        site = out.read_text(encoding="utf-8")
        assert site.startswith(address) and "import access_log" in site and "reverse_proxy 127.0.0.1:7251" in site


@pytest.mark.parametrize("new_address, redirect, ready", [
    ("", "", False), ("10.0.0.9", "", False),
    ("122.51.14.35", "https://dnspod.qcloud.com/static/webblock.html", False), ("122.51.14.35", "", True)])
def test_the_new_name_joins_only_once_it_resolves_here_and_is_unblocked(tmp_path, new_address, redirect, ready):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "getent").write_text(
        '#!/bin/sh\ncase "$2" in inthub.tenon.asia) echo "122.51.14.35 STREAM";; '
        f'inthub.tenonai.cn) [ -n "{new_address}" ] && echo "{new_address} STREAM" || exit 2;; esac\n')
    (bin_dir / "curl").write_text(f'#!/bin/sh\nprintf %s "{redirect}"\n')
    for tool in bin_dir.iterdir():
        tool.chmod(0o755)
    result = subprocess.run(["bash", "-c", 'PUBLIC_URL=https://inthub.tenon.asia NEW_DOMAIN=inthub.tenonai.cn; '
                             + shell_function("new_domain_ready") + "new_domain_ready"],
                            env={"PATH": f"{bin_dir}:/usr/bin:/bin"})
    assert (result.returncode == 0) is ready


def test_compose_and_smoke_accept_the_second_name():
    deploy = ROOT / "deploy" / "inthub"
    compose = (deploy / "compose.yaml").read_text(encoding="utf-8")
    assert "INTHUB_API_BASE_URL: https://${INTHUB_DOMAIN:?set INTHUB_DOMAIN}${INTHUB_EXTRA_ORIGINS:-}" in compose
    assert "INTHUB_ALLOWED_ORIGINS: https://${INTHUB_DOMAIN}${INTHUB_EXTRA_ORIGINS:-}" in compose
    remote = (deploy / "remote-release.sh").read_text(encoding="utf-8")
    assert '"INTHUB_EXTRA_ORIGINS=${EXTRA_ORIGINS}"' in remote
    assert remote.index("if new_domain_ready; then") < remote.index("up --detach --no-build --pull never database")
    assert 'INTHUB_BASE_URL="https://${NEW_DOMAIN}" bash "${RELEASE_DIRECTORY}/smoke.sh"' in remote
    assert '{"account.tenonai.cn", "account.tenon.asia"}' in (deploy / "smoke.sh").read_text(encoding="utf-8")
