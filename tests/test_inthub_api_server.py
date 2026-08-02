import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from apps.inthub_api.server import make_handler


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
        assert "itt hub sync" in js
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_private_api_uses_bearer_for_writes_and_http_only_cookie_for_web_reads(tmp_path):
    token = "correct-horse-battery-staple"
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_handler(
            str(tmp_path / "inthub.db"),
            serve_web=True,
            auth_token=token,
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
            f"{base}/api/v1/auth/session",
            method="POST",
            payload={"token": "wrong"},
        )
        assert status == 401
        assert body["error"]["code"] == "AUTH_INVALID"

        status, headers, body = _request_json(
            f"{base}/api/v1/auth/session",
            method="POST",
            payload={"token": token},
        )
        assert status == 200
        assert body["result"]["authenticated"] is True
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        assert "HttpOnly" in headers["Set-Cookie"]
        assert "SameSite=Strict" in headers["Set-Cookie"]

        status, _, body = _request_json(
            f"{base}/api/v1/projects",
            headers={"Cookie": cookie},
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
            headers={"Cookie": cookie},
        )
        assert status == 401
        assert body["error"]["code"] == "AUTH_REQUIRED"

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
            auth_token="cli-write-token",
            github_client_id="github-client-id",
            github_client_secret="github-client-secret",
            github_allowed_user_ids="4242",
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
        assert body["result"]["account"]["role"] == "owner"

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
