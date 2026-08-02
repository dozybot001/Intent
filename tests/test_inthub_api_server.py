import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from apps.inthub_api.server import make_handler


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
