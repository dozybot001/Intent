import json
import os
import subprocess
import threading
import time
import base64
import hashlib
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from apps.inthub_api import server as server_module
from apps.inthub_api.auth import create_account_access_token, upsert_github_account
from apps.inthub_api.server import make_handler


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class FakeTenonOIDCClient:
    def __init__(self, user=None):
        self.user = user or {"sub": "tenon-dozy", "name": "Dozy", "platform_role": "user", "expires_at": time.time() + 900}
        self.exchange = None

    def authorization_url(self, redirect_uri, attempt):
        state = attempt["state"]
        code_challenge = base64.urlsafe_b64encode(hashlib.sha256(attempt["code_verifier"].encode()).digest()).rstrip(b"=").decode()
        query = parse_qs(
            f"redirect_uri={redirect_uri}&state={state}&code_challenge={code_challenge}"
        )
        assert query["redirect_uri"] == [redirect_uri]
        return (
            "https://account.tenon.asia/api/auth/oauth2/authorize"
            f"?state={state}&code_challenge={code_challenge}"
        )

    def complete_login(self, code, redirect_uri, attempt):
        self.exchange = {
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": attempt["code_verifier"],
            "nonce": attempt["nonce"],
        }
        return self.user


def _raw_request(server, path, method="GET", headers=None, body=None):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    payload = response.read()
    result = response.status, response.getheaders(), payload
    connection.close()
    return result


def _get_json(url):
    with urlopen(url) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _request_json(url, method="GET", payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = dict(headers or {})
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=request_headers, method=method)
    try:
        response = urlopen(request)
    except HTTPError as exc:
        response = exc
    with response:
        body = json.loads(response.read().decode("utf-8"))
        return response.status, dict(response.headers), body


def test_api_healthz(tmp_path):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_handler(str(tmp_path / "inthub.db")),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        payload = _get_json(f"{base}/healthz")
        assert payload["ok"] is True
        assert payload["result"]["service"] == "inthub-api"
        assert payload["result"]["status"] == "alive"
        assert set(payload["result"]) == {"service", "status"}
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_api_server_can_serve_web_shell(tmp_path, monkeypatch):
    monkeypatch.setenv("INTHUB_VERSION", "6.0.1.dev36+gtest123")
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_handler(
            str(tmp_path / "inthub.db"),
            serve_web=True,
            default_project_id="proj_demo123",
        ),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        config = _get_json(f"{base}/config.json")
        assert config["apiBaseUrl"] == base
        assert config["defaultProjectId"] == "proj_demo123"
        assert config["authRequired"] is False
        assert config["productVersion"] == "6.0.1.dev36+gtest123"

        mark = urlopen(f"{base}/tenon-mark.svg").read().decode("utf-8")
        assert 'fill="#f06b32"' in mark
        with urlopen(f"{base}/auth/redirect") as response:
            assert response.headers["Cache-Control"] == "no-cache"
            transition = response.read().decode("utf-8")
        assert 'id="transition-title"' in transition
        assert 'id="transition-retry"' in transition
        assert 'id="shell"' not in transition
        font = urlopen(f"{base}/InterVariable.woff2").read()
        assert font[:4] == b"wOF2"
        assert len(font) == 352240
        theme = urlopen(f"{base}/theme.js").read().decode("utf-8")
        assert "inthub.theme" in theme

        html = urlopen(f"{base}/").read().decode("utf-8")
        assert "IntHub" in html
        # Every asset URL carries the running release; nobody bumps a revision by hand.
        assert "__REV__" not in html and "/app.js?rev=" in html
        assert ".list-row" in urlopen(f"{base}/styles.css").read().decode("utf-8")
        for path in ("/settings/usage", "/settings/teams/", "/account/danger", "/device", "/invite", "/teams/acme/projects"):
            assert 'id="site-content"' in urlopen(f"{base}{path}").read().decode("utf-8"), path
        # A path nobody serves is a real 404, for browsers and crawlers alike.
        for path in ("/terms", "/pricing", "/projects/demo", "/settings/other"):
            with pytest.raises(HTTPError) as missing:
                urlopen(f"{base}{path}")
            assert missing.value.code == 404 and "Page not found" in missing.value.read().decode("utf-8"), path
        robots = urlopen(f"{base}/robots.txt").read().decode("utf-8")
        assert "Allow: /$" in robots and "Disallow: /\n" in robots
        assert "Contact: mailto:support@tenonai.cn" in urlopen(f"{base}/.well-known/security.txt").read().decode("utf-8")
        assert urlopen(f"{base}/favicon.ico").url.endswith("/tenon-mark.svg")
        js = urlopen(f"{base}/app.js").read().decode("utf-8")
        assert "itt push" in js
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_retired_showcase_routes_do_not_fall_through_to_private_shell(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
        str(tmp_path / "inthub.db"), serve_web=True, require_auth=True,
        tenon_client_id="test", tenon_client_secret="test", oauth_client=FakeTenonOIDCClient(),
        public_api_base_url="https://inthub.example",
    ))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for path in ("/showcase", "/showcase/", "/showcase/config.json",
                     "/api/v1/public-profiles/showcase",
                     "/api/v1/public-profiles/showcase/projects"):
            status, _, payload = _raw_request(server, path)
            assert status == 410
            assert json.loads(payload)["error"]["code"] == "FEATURE_RETIRED"
        assert _raw_request(server, "/api/v1/projects")[0] == 401
        assert _raw_request(server, "/")[0] == 200
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_fixed_login_prepare_is_same_origin_fresh_and_validates_destination(tmp_path):
    provider = FakeTenonOIDCClient()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(
        str(tmp_path / "inthub.db"), serve_web=True,
        tenon_client_id="test", tenon_client_secret="test",
        oauth_client=provider, public_api_base_url="https://inthub.example",
        allowed_origins=["https://inthub.example"], secure_cookies=True,
    ))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        states = []
        for _ in range(2):
            status, headers, body = _request_json(base + "/api/v1/auth/tenon/prepare", "POST", {"return_to": "/?tab=snaps"})
            assert status == 200 and body["ok"] is True
            url = body["result"]["authorizationUrl"]
            assert url.startswith("https://account.tenon.asia/api/auth/oauth2/authorize?")
            states.append(parse_qs(urlparse(url).query)["state"][0])
            assert "HttpOnly" in headers["Set-Cookie"] and "Secure" in headers["Set-Cookie"]
            assert headers["Cache-Control"] == "no-store"
        assert states[0] != states[1]
        status, _, _ = _request_json(base + "/api/v1/auth/tenon/prepare", "POST", {}, {"Origin": "https://evil.example"})
        assert status == 403
        status, _, _ = _request_json(base + "/api/v1/auth/tenon/prepare", "POST", {}, {"Sec-Fetch-Site": "cross-site"})
        assert status == 403
        provider.authorization_url = lambda *_: "https://evil.example/authorize"
        status, _, body = _request_json(base + "/api/v1/auth/tenon/prepare", "POST", {})
        assert status == 503 and body["error"]["code"] == "AUTH_FLOW_UNAVAILABLE"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_production_smoke_accepts_order_independent_required_csp(tmp_path):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_handler(
            str(tmp_path / "inthub.db"),
            serve_web=True,
            tenon_client_id="github-client-id",
            tenon_client_secret="github-client-secret",
            oauth_client=FakeTenonOIDCClient(),
            public_api_base_url="https://inthub.example",
        ),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        environment = os.environ.copy()
        environment["INTHUB_BASE_URL"] = f"http://127.0.0.1:{server.server_port}"
        environment.pop("INTHUB_LOOPBACK_URL", None)
        subprocess.run(
            ["bash", str(REPOSITORY_ROOT / "deploy" / "inthub" / "smoke.sh")],
            check=True,
            env=environment,
            capture_output=True,
            text=True,
        )
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_account_pat_authenticates_cli_reads_and_writes(tmp_path):
    db_path = str(tmp_path / "inthub.db")
    account = upsert_github_account(db_path, {"id": 101, "login": "pat-user"})
    token = create_account_access_token(db_path, account["id"], ttl_seconds=3600)["token"]
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_handler(
            db_path,
            serve_web=True,
            tenon_client_id="github-client-id",
            tenon_client_secret="github-client-secret",
            oauth_client=FakeTenonOIDCClient(),
            public_api_base_url="https://inthub.example",
        ),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        config = _get_json(f"{base}/config.json")
        assert config["authRequired"] is True

        status, headers, body = _request_json(f"{base}/api/v1/projects")
        assert status == 401
        assert body["error"]["code"] == "AUTH_REQUIRED"
        assert headers["WWW-Authenticate"] == "Bearer"

        status, _, body = _request_json(
            f"{base}/api/v1/projects",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert body["result"]["projects"] == []

        link_payload = {"project_name": "Demo"}
        status, _, body = _request_json(
            f"{base}/api/v2/link",
            method="POST",
            payload=link_payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert body["result"]["project_id"].startswith("proj_")
        status, _, body = _request_json(
            f"{base}/api/v1/hub/link", method="POST", payload=link_payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 404
        assert body["error"]["code"] == "OBJECT_NOT_FOUND"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


@pytest.mark.parametrize("role", ["user", "admin"])
def test_tenon_account_login_uses_pkce_database_session_and_logout(tmp_path, role):
    oauth = FakeTenonOIDCClient({
        "sub": "tenon-dozy", "name": "Dozy", "platform_role": role,
        "expires_at": time.time() + 900,
    })
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_handler(
            str(tmp_path / "inthub.db"),
            serve_web=True,
            public_api_base_url="https://inthub.example",
            tenon_client_id="github-client-id",
            tenon_client_secret="github-client-secret",
            oauth_client=oauth,
            secure_cookies=True,
        ),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        config = _get_json(f"{base}/config.json")
        assert config["authMode"] == "tenon"
        assert _raw_request(server, "/api/v1/auth/github/start")[0] == 410
        assert _raw_request(server, "/api/v1/auth/github/callback", method="POST")[0] == 410
        assert _raw_request(server, "/api/v1/auth/tenon/prepare", method="POST", headers={"Sec-Fetch-Site": "cross-site"})[0] == 403

        status, root_headers, _ = _raw_request(server, "/")
        assert status == 200
        assert "default-src 'self'" in dict(root_headers)["Content-Security-Policy"]

        status, headers, body = _raw_request(
            server,
            "/api/v1/auth/tenon/prepare", method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"return_to": "/projects/demo?tab=snaps"}),
        )
        assert status == 200
        header_map = dict(headers)
        authorize = json.loads(body)["result"]["authorizationUrl"]
        state = parse_qs(urlparse(authorize).query)["state"][0]
        state_cookie = header_map["Set-Cookie"].split(";", 1)[0]
        assert "HttpOnly" in header_map["Set-Cookie"]
        assert "Secure" in header_map["Set-Cookie"]
        assert "Max-Age=600" in header_map["Set-Cookie"]

        status, callback_headers, _ = _raw_request(
            server,
            f"/api/v1/auth/tenon/callback?code=temporary-code&state={state}",
            headers={"Cookie": state_cookie},
        )
        assert status == 302
        assert dict(callback_headers)["Location"] == "/projects/demo?tab=snaps"
        cookies = [value for name, value in callback_headers if name == "Set-Cookie"]
        session_cookie = next(value.split(";", 1)[0] for value in cookies if "ith_ses_" in value)
        session_header = next(value for value in cookies if "ith_ses_" in value)
        assert session_cookie.startswith("__Host-inthub_session=")
        assert "Path=/;" in session_header and "Secure" in session_header and "Domain" not in session_header
        assert "SameSite=Strict" in session_header
        assert "Max-Age=2592000" in next(value for value in cookies if "ith_ses_" in value)
        assert oauth.exchange["code"] == "temporary-code"
        assert oauth.exchange["redirect_uri"] == (
            "https://inthub.example/api/v1/auth/tenon/callback"
        )
        assert oauth.exchange["code_verifier"]
        assert oauth.exchange["nonce"]
        status, replay_headers, _ = _raw_request(
            server, f"/api/v1/auth/tenon/callback?code=temporary-code&state={state}",
            headers={"Cookie": state_cookie},
        )
        assert status == 302
        assert dict(replay_headers)["Location"] == "/?auth_error=tenon_failed"

        status, _, body = _request_json(
            f"{base}/api/v1/auth/me",
            headers={"Cookie": 'theme={"mode":"dark"}; ' + session_cookie},
        )
        assert status == 200
        assert body["result"]["account"]["display_name"] == "Dozy"
        assert body["result"]["account"]["role"] == ("admin" if role == "admin" else "member")
        # The pre-prefix cookie name is never trusted, so a sibling site cannot plant it.
        status, _, _ = _request_json(
            f"{base}/api/v1/auth/me",
            headers={"Cookie": "inthub_session=" + session_cookie.split("=", 1)[1]},
        )
        assert status == 401

        status, _, body = _request_json(
            f"{base}/api/v1/projects",
            headers={"Cookie": session_cookie},
        )
        assert status == 200
        assert body["result"]["projects"] == []

        status, _, body = _request_json(
            f"{base}/api/v2/link",
            method="POST",
            payload={
                "project_name": "Must stay read-only",
            },
            headers={"Cookie": session_cookie},
        )
        assert status == 401
        assert body["error"]["code"] == "AUTH_REQUIRED"

        status, _, body = _request_json(
            f"{base}/api/v1/auth/tokens",
            method="POST",
            payload={"name": "Laptop", "ttl_seconds": 3600},
            headers={"Cookie": session_cookie},
        )
        assert status == 201
        account_token = body["result"]["token"]
        account_token_id = body["result"]["id"]
        assert account_token.startswith("ith_pat_")

        status, _, body = _request_json(
            f"{base}/api/v1/auth/tokens",
            headers={"Cookie": session_cookie},
        )
        assert status == 200
        assert body["result"]["tokens"][0]["id"] == account_token_id
        assert "token" not in body["result"]["tokens"][0]

        status, _, body = _request_json(
            f"{base}/api/v2/link",
            method="POST",
            payload={
                "project_name": "Account-owned project",
            },
            headers={"Authorization": f"Bearer {account_token}"},
        )
        assert status == 200
        assert body["result"]["project_id"].startswith("proj_")

        status, _, body = _request_json(
            f"{base}/api/v1/auth/tokens/{account_token_id}/revoke",
            method="POST",
            headers={"Cookie": session_cookie},
        )
        assert status == 200
        assert body["result"]["revoked"] is True
        status, _, body = _request_json(
            f"{base}/api/v1/projects",
            headers={"Authorization": f"Bearer {account_token}"},
        )
        assert status == 401

        status, _, _ = _request_json(
            f"{base}/api/v1/auth/logout",
            method="POST",
            headers={"Cookie": session_cookie},
        )
        assert status == 200
        status, _, body = _request_json(
            f"{base}/api/v1/auth/me",
            headers={"Cookie": session_cookie},
        )
        assert status == 401
        assert body["error"]["code"] == "AUTH_REQUIRED"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


@pytest.mark.parametrize("legacy_ttl", ["900", "invalid"])
def test_legacy_runtime_ttl_cannot_shorten_browser_login(monkeypatch, legacy_ttl):
    session_lifetimes = []

    def capture_run_server(*args, account_session_ttl_seconds=server_module.ACCOUNT_SESSION_TTL_SECONDS, **kwargs):
        session_lifetimes.append(account_session_ttl_seconds)

    monkeypatch.setenv("INTHUB_SESSION_TTL_SECONDS", legacy_ttl)
    monkeypatch.setattr("sys.argv", ["inthub"])
    monkeypatch.setattr(server_module, "run_server", capture_run_server)
    server_module.main()
    assert session_lifetimes == [30 * 24 * 60 * 60]


def test_api_rejects_disallowed_origins_and_oversized_bodies(tmp_path):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_handler(
            str(tmp_path / "inthub.db"),
            allowed_origins="https://inthub.example.com",
            max_body_bytes=8,
        ),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        status, _, body = _request_json(
            f"{base}/api/v1/projects",
            headers={"Origin": "https://attacker.example"},
        )
        assert status == 403
        assert body["error"]["code"] == "ORIGIN_DENIED"

        status, _, body = _request_json(
            f"{base}/api/v2/history",
            method="POST",
            payload={"too": "large"},
        )
        assert status == 413
        assert body["error"]["code"] == "PAYLOAD_TOO_LARGE"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def _serving(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _stop(server, thread):
    server.shutdown()
    thread.join()
    server.server_close()


def test_local_mode_serves_only_same_origin_pages_on_loopback_names(tmp_path):
    server, thread = _serving(make_handler(str(tmp_path / "inthub.db"), serve_web=True))
    own_origin = f"http://127.0.0.1:{server.server_port}"
    try:
        status, headers, body = _raw_request(server, "/api/v1/projects", headers={"Origin": "https://evil.example"})
        assert status == 403 and json.loads(body)["error"]["code"] == "ORIGIN_DENIED"
        assert "Access-Control-Allow-Origin" not in dict(headers)
        status, headers, _ = _raw_request(server, "/api/v2/link", method="OPTIONS", headers={
            "Origin": "https://evil.example", "Access-Control-Request-Method": "POST",
        })
        assert status == 403 and "Access-Control-Allow-Origin" not in dict(headers)
        status, headers, _ = _raw_request(server, "/api/v1/projects", headers={"Origin": own_origin})
        assert status == 200 and "Access-Control-Allow-Origin" not in dict(headers)
        assert dict(headers)["Server"] == "IntHub"
        # DNS rebinding keeps the attacker's name in Host.
        status, _, body = _raw_request(server, "/api/v1/projects", headers={"Host": "rebind.evil.example"})
        assert status == 403 and json.loads(body)["error"]["code"] == "HOST_DENIED"
        assert _raw_request(server, "/api/v1/projects", headers={"Host": f"localhost:{server.server_port}"})[0] == 200
        # A form-encodable body is never accepted as JSON.
        status, _, _ = _raw_request(server, "/api/v2/link", method="POST",
                                    headers={"Content-Type": "text/plain"}, body=json.dumps({"project_name": "planted"}))
        assert status == 415
        assert _get_json(f"{own_origin}/api/v1/projects")["result"]["projects"] == []
    finally:
        _stop(server, thread)


def test_requests_fail_closed_before_reading_untrusted_bodies(tmp_path):
    server, thread = _serving(make_handler(str(tmp_path / "inthub.db")))
    try:
        status, _, body = _raw_request(server, "/api/v2/history", method="POST",
                                       headers={"Content-Type": "application/json"}, body="[" * 100000)
        assert status == 400 and json.loads(body)["error"]["code"] == "INVALID_INPUT"
        assert _raw_request(server, "/not-an-api", method="POST", body="x" * 1024)[0] == 404
        assert _raw_request(server, "/not-a-page")[0] == 404
        status, headers, body = _raw_request(server, "/api/v1/projects", method="PUT")
        assert status == 405 and json.loads(body)["error"]["code"] == "METHOD_NOT_ALLOWED"
        assert "POST" in dict(headers)["Allow"]
        status, _, body = _raw_request(server, "/api/v2/link", method="POST",
                                       headers={"Content-Type": "application/json"}, body="x" * (17 * 1024))
        assert status == 413
    finally:
        _stop(server, thread)


def test_sign_in_preparation_is_rate_limited_per_client(tmp_path):
    server, thread = _serving(make_handler(
        str(tmp_path / "inthub.db"), tenon_client_id="client", tenon_client_secret="secret",
        oauth_client=FakeTenonOIDCClient(), public_api_base_url="https://inthub.example",
    ))
    try:
        statuses = [
            _raw_request(server, "/api/v1/auth/tenon/prepare", method="POST",
                         headers={"Content-Type": "application/json", "X-Forwarded-For": "203.0.113.9"}, body="{}")[0]
            for _ in range(31)
        ]
        assert statuses[:30] == [200] * 30 and statuses[30] == 429
        assert _raw_request(server, "/api/v1/auth/tenon/prepare", method="POST",
                            headers={"Content-Type": "application/json", "X-Forwarded-For": "203.0.113.10"}, body="{}")[0] == 200
    finally:
        _stop(server, thread)


def test_unauthenticated_server_refuses_public_interfaces(monkeypatch):
    calls = []
    monkeypatch.setattr(server_module, "run_server", lambda *args, **kwargs: calls.append(args))
    for name in ("INTHUB_TENON_CLIENT_ID", "INTHUB_TENON_CLIENT_SECRET", "INTHUB_REQUIRE_AUTH", "INTHUB_ALLOW_UNAUTHENTICATED"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("sys.argv", ["inthub", "--host", "0.0.0.0"])
    with pytest.raises(SystemExit):
        server_module.main()
    assert calls == []
    monkeypatch.setenv("INTHUB_ALLOW_UNAUTHENTICATED", "1")
    server_module.main()
    assert calls and calls[0][0] == "0.0.0.0"
