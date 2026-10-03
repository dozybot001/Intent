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
        assert _get_json(f"{base}/showcase/config.json")["productVersion"] == config["productVersion"]

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
        deep_link = urlopen(f"{base}/projects/demo").read().decode("utf-8")
        assert "IntHub" in deep_link
        js = urlopen(f"{base}/app.js").read().decode("utf-8")
        assert "itt push" in js
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

        link_payload = {
            "project_name": "Demo",
            "repo": {
                "provider": "github",
                "repo_id": "example/demo",
                "owner": "example",
                "name": "demo",
            },
            "workspace": {"workspace_id": "wks_demo"},
        }
        status, _, body = _request_json(
            f"{base}/api/v1/hub/link",
            method="POST",
            payload=link_payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status == 200
        assert body["result"]["project_id"].startswith("proj_")
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_tenon_account_login_uses_pkce_database_session_and_logout(tmp_path):
    oauth = FakeTenonOIDCClient()
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

        status, callback_headers, _ = _raw_request(
            server,
            f"/api/v1/auth/tenon/callback?code=temporary-code&state={state}",
            headers={"Cookie": state_cookie},
        )
        assert status == 302
        assert dict(callback_headers)["Location"] == "/projects/demo?tab=snaps"
        cookies = [value for name, value in callback_headers if name == "Set-Cookie"]
        session_cookie = next(value.split(";", 1)[0] for value in cookies if "ith_ses_" in value)
        assert "SameSite=Strict" in next(value for value in cookies if "ith_ses_" in value)
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
            headers={"Cookie": session_cookie},
        )
        assert status == 200
        assert body["result"]["account"]["display_name"] == "Dozy"
        assert body["result"]["account"]["role"] == "member"

        status, _, body = _request_json(
            f"{base}/api/v1/projects",
            headers={"Cookie": session_cookie},
        )
        assert status == 200
        assert body["result"]["projects"] == []

        status, _, body = _request_json(
            f"{base}/api/v1/hub/link",
            method="POST",
            payload={
                "project_name": "Must stay read-only",
                "repo": {
                    "provider": "github",
                    "repo_id": "example/read-only",
                    "owner": "example",
                    "name": "read-only",
                },
                "workspace": {"workspace_id": "wks_read_only"},
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
            f"{base}/api/v1/hub/link",
            method="POST",
            payload={
                "project_name": "Account-owned project",
                "repo": {
                    "provider": "github",
                    "repo_id": "example/account-owned",
                    "owner": "example",
                    "name": "account-owned",
                },
                "workspace": {"workspace_id": "wks_account_owned"},
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
            f"{base}/api/v1/hub/link",
            method="POST",
            payload={"too": "large"},
        )
        assert status == 413
        assert body["error"]["code"] == "PAYLOAD_TOO_LARGE"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
