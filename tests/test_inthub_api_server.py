import json
import os
import subprocess
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from apps.inthub_api.auth import create_account_access_token, upsert_github_account
from apps.inthub_api.server import make_handler


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class FakeGitHubOAuthClient:
    def __init__(self, user=None):
        self.user = user or {
            "id": 4242,
            "login": "dozy",
            "name": "Dozy",
            "avatar_url": "https://avatars.example/dozy.png",
        }
        self.exchange = None

    def authorization_url(self, redirect_uri, state, code_challenge):
        query = parse_qs(
            f"redirect_uri={redirect_uri}&state={state}&code_challenge={code_challenge}"
        )
        assert query["redirect_uri"] == [redirect_uri]
        return (
            "https://github.example/authorize"
            f"?state={state}&code_challenge={code_challenge}"
        )

    def exchange_code(self, code, redirect_uri, code_verifier):
        self.exchange = {
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
        return "github-token-used-once"

    def get_user(self, access_token):
        assert access_token == "github-token-used-once"
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


def test_api_server_can_serve_web_shell(tmp_path):
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


def test_production_smoke_accepts_order_independent_required_csp(tmp_path):
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_handler(
            str(tmp_path / "inthub.db"),
            serve_web=True,
            github_client_id="github-client-id",
            github_client_secret="github-client-secret",
            oauth_client=FakeGitHubOAuthClient(),
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
            github_client_id="github-client-id",
            github_client_secret="github-client-secret",
            oauth_client=FakeGitHubOAuthClient(),
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


def test_github_account_login_uses_pkce_database_session_and_logout(tmp_path):
    oauth = FakeGitHubOAuthClient()
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_handler(
            str(tmp_path / "inthub.db"),
            serve_web=True,
            public_api_base_url="https://inthub.example",
            github_client_id="github-client-id",
            github_client_secret="github-client-secret",
            oauth_client=oauth,
            secure_cookies=True,
        ),
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        config = _get_json(f"{base}/config.json")
        assert config["authMode"] == "github"

        status, root_headers, _ = _raw_request(server, "/")
        assert status == 200
        assert "default-src 'self'" in dict(root_headers)["Content-Security-Policy"]

        status, headers, _ = _raw_request(
            server,
            "/api/v1/auth/github/start?return_to=%2Fprojects%2Fdemo%3Ftab%3Dsnaps",
        )
        assert status == 302
        header_map = dict(headers)
        authorize = header_map["Location"]
        state = parse_qs(urlparse(authorize).query)["state"][0]
        state_cookie = header_map["Set-Cookie"].split(";", 1)[0]
        assert "HttpOnly" in header_map["Set-Cookie"]
        assert "Secure" in header_map["Set-Cookie"]

        status, callback_headers, _ = _raw_request(
            server,
            f"/api/v1/auth/github/callback?code=temporary-code&state={state}",
            headers={"Cookie": state_cookie},
        )
        assert status == 302
        assert dict(callback_headers)["Location"] == "/projects/demo?tab=snaps"
        cookies = [value for name, value in callback_headers if name == "Set-Cookie"]
        session_cookie = next(value.split(";", 1)[0] for value in cookies if "ith_ses_" in value)
        assert "SameSite=Strict" in next(value for value in cookies if "ith_ses_" in value)
        assert oauth.exchange["code"] == "temporary-code"
        assert oauth.exchange["redirect_uri"] == (
            "https://inthub.example/api/v1/auth/github/callback"
        )
        assert oauth.exchange["code_verifier"]

        status, _, body = _request_json(
            f"{base}/api/v1/auth/me",
            headers={"Cookie": session_cookie},
        )
        assert status == 200
        assert body["result"]["account"]["login"] == "dozy"
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
