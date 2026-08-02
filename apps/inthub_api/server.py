"""HTTP server for the IntHub V1 API and optional Web shell."""

import argparse
import hmac
import json
import logging
import mimetypes
import os
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from apps.inthub_api.auth import (
    GitHubOAuthClient,
    account_for_access_token,
    account_for_session,
    consume_login_attempt,
    create_account_access_token,
    create_login_attempt,
    create_web_session,
    delete_web_session,
    list_account_access_tokens,
    revoke_account_access_token,
    safe_return_to,
    upsert_github_account,
)
from apps.inthub_api.common import APIError
from apps.inthub_api.db import check_database, describe_database
from apps.inthub_api.ingest import link_project, store_sync_batch
from apps.inthub_api.queries import (
    get_decision_detail,
    get_intent_detail,
    get_snap_detail,
    list_projects,
    project_handoff,
    project_overview,
    search_project,
)

STATIC_DIR = Path(__file__).resolve().parents[1] / "inthub_web" / "static"
DEFAULT_MAX_BODY_BYTES = 16 * 1024 * 1024
SESSION_COOKIE = "inthub_session"
OAUTH_STATE_COOKIE = "inthub_oauth_state"
ACCOUNT_SESSION_TTL_SECONDS = 7 * 24 * 60 * 60
OAUTH_STATE_TTL_SECONDS = 10 * 60
LOGGER = logging.getLogger("inthub.api")


def _json_success(result):
    return {"ok": True, "result": result}


def _json_error(code, message, details=None):
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
    }


def _env_flag(name, default=False):
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_or_file(name, default=None):
    value = os.getenv(name)
    if value is not None:
        return value
    file_path = os.getenv(f"{name}_FILE")
    if file_path:
        return Path(file_path).read_text(encoding="utf-8").strip()
    return default


def _normalize_origins(allowed_origins):
    if allowed_origins is None:
        return None
    if isinstance(allowed_origins, str):
        allowed_origins = allowed_origins.split(",")
    return {origin.strip().rstrip("/") for origin in allowed_origins if origin.strip()}


def make_handler(
    db_path,
    serve_web=False,
    public_api_base_url=None,
    default_project_id=None,
    web_static_dir=None,
    require_auth=False,
    allowed_origins=None,
    max_body_bytes=DEFAULT_MAX_BODY_BYTES,
    secure_cookies=False,
    github_client_id=None,
    github_client_secret=None,
    oauth_client=None,
    account_session_ttl_seconds=ACCOUNT_SESSION_TTL_SECONDS,
    oauth_state_ttl_seconds=OAUTH_STATE_TTL_SECONDS,
):
    root = Path(web_static_dir or STATIC_DIR).resolve()
    github_configured = bool(github_client_id or github_client_secret)
    if github_configured and not (github_client_id and github_client_secret):
        raise ValueError("Both GitHub OAuth client ID and client secret are required.")
    provider_client = oauth_client
    if github_configured and provider_client is None:
        provider_client = GitHubOAuthClient(github_client_id, github_client_secret)
    auth_required = bool(require_auth or github_configured)
    if auth_required and not github_configured:
        raise ValueError("Authentication is required but no IntHub authentication is configured.")
    auth_mode = "github" if github_configured else "none"
    origin_allowlist = _normalize_origins(allowed_origins)

    class IntHubHandler(BaseHTTPRequestHandler):
        server_version = "IntHubAPI/0.3"

        def _send_json(self, status, payload, extra_headers=None):
            body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
            self._send_bytes(
                status,
                body,
                "application/json; charset=utf-8",
                extra_headers=extra_headers,
                cache_control="no-store",
            )

        def _send_bytes(
            self,
            status,
            body,
            content_type,
            extra_headers=None,
            cache_control="no-cache",
        ):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache_control)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; "
                "img-src 'self' https://avatars.githubusercontent.com data:; "
                "script-src 'self'; style-src 'self'; connect-src 'self'; "
                "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
                "form-action 'self'",
            )
            self.send_header(
                "Permissions-Policy",
                "camera=(), microphone=(), geolocation=(), payment=()",
            )
            request_origin = self.headers.get("Origin")
            if request_origin:
                if origin_allowlist is None:
                    self.send_header("Access-Control-Allow-Origin", "*")
                elif request_origin.rstrip("/") in origin_allowlist:
                    self.send_header("Access-Control-Allow-Origin", request_origin)
                    self.send_header("Vary", "Origin")
            header_items = (extra_headers or {}).items() if hasattr(extra_headers or {}, "items") else extra_headers
            for name, value in header_items:
                self.send_header(name, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _request_base_url(self):
            if public_api_base_url:
                return public_api_base_url.rstrip("/")
            proto = self.headers.get("X-Forwarded-Proto", "http")
            host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host")
            if not host:
                host = f"{self.server.server_address[0]}:{self.server.server_address[1]}"
            return f"{proto}://{host}"

        def _oauth_callback_url(self):
            return f"{self._request_base_url()}/api/v1/auth/github/callback"

        def _send_redirect(self, location, cookies=None):
            headers = [("Location", location)]
            headers.extend(("Set-Cookie", cookie) for cookie in (cookies or ()))
            self._send_bytes(
                302,
                b"",
                "text/plain; charset=utf-8",
                extra_headers=headers,
                cache_control="no-store",
            )

        def _send_file(self, path):
            body = path.read_bytes()
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if content_type.startswith("text/") or content_type in {
                "application/javascript",
                "application/json",
            }:
                content_type = f"{content_type}; charset=utf-8"
            cache_control = "no-cache" if path.name == "index.html" else "public, max-age=3600"
            self._send_bytes(200, body, content_type, cache_control=cache_control)

        def _serve_index(self):
            self._send_file(root / "index.html")

        def _serve_web(self, path):
            if path == "/config.json":
                self._send_json(
                    200,
                    {
                        "apiBaseUrl": self._request_base_url(),
                        "defaultProjectId": default_project_id,
                        "authRequired": auth_required,
                        "authMode": auth_mode,
                    },
                )
                return True

            if path == "/" or (not Path(path).suffix and not path.startswith("/api/")):
                self._serve_index()
                return True

            candidate = (root / path.lstrip("/")).resolve()
            try:
                candidate.relative_to(root)
            except ValueError as exc:
                raise APIError("OBJECT_NOT_FOUND", f"Asset {path} not found.", status=404) from exc
            if candidate.is_file():
                self._send_file(candidate)
                return True
            return False

        def _check_origin(self):
            origin = self.headers.get("Origin")
            if (
                origin
                and origin_allowlist is not None
                and origin.rstrip("/") not in origin_allowlist
            ):
                raise APIError(
                    "ORIGIN_DENIED",
                    "The request origin is not allowed.",
                    status=403,
                )

        def _read_json_body(self):
            raw_length = self.headers.get("Content-Length", "0")
            try:
                length = int(raw_length)
            except (TypeError, ValueError) as exc:
                raise APIError(
                    "INVALID_INPUT",
                    "Content-Length must be a valid integer.",
                    status=400,
                ) from exc
            if length < 0:
                raise APIError("INVALID_INPUT", "Content-Length cannot be negative.", status=400)
            if length > max_body_bytes:
                raise APIError(
                    "PAYLOAD_TOO_LARGE",
                    f"Request body exceeds the {max_body_bytes}-byte limit.",
                    status=413,
                )
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            try:
                payload = json.loads(raw or "{}")
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise APIError(
                    "INVALID_INPUT",
                    "Request body must be valid UTF-8 JSON.",
                    status=400,
                ) from exc
            if not isinstance(payload, dict):
                raise APIError("INVALID_INPUT", "Request body must be a JSON object.", status=400)
            return payload

        def _bearer_account(self):
            header = self.headers.get("Authorization", "")
            scheme, separator, token = header.partition(" ")
            if not separator or scheme.lower() != "bearer":
                return None
            return account_for_access_token(db_path, token)

        def _cookie_value(self, name):
            cookie = SimpleCookie()
            try:
                cookie.load(self.headers.get("Cookie", ""))
            except Exception:
                return None
            morsel = cookie.get(name)
            return morsel.value if morsel else None

        def _current_account(self):
            if not github_configured:
                return None
            return account_for_session(db_path, self._cookie_value(SESSION_COOKIE))

        def _require_auth(self, allow_cookie=False):
            if not auth_required:
                return {"account": None}
            account = self._bearer_account()
            if account is not None:
                return {"account": account}
            if allow_cookie:
                account = self._current_account()
                if account is not None:
                    return {"account": account}
            raise APIError(
                "AUTH_REQUIRED",
                "Sign in or provide a valid IntHub account access token.",
                status=401,
            )

        def _cookie_header(self, name, value, max_age, same_site="Lax", path="/"):
            cookie = (
                f"{name}={value}; Path={path}; HttpOnly; SameSite={same_site}; "
                f"Max-Age={max_age}"
            )
            if secure_cookies:
                cookie += "; Secure"
            return cookie

        def _session_cookie(self, value, max_age):
            return self._cookie_header(SESSION_COOKIE, value, max_age, same_site="Strict")

        def _oauth_state_cookie(self, value, max_age):
            return self._cookie_header(
                OAUTH_STATE_COOKIE,
                value,
                max_age,
                same_site="Lax",
                path="/api/v1/auth/github",
            )

        def _handle_logout(self):
            delete_web_session(db_path, self._cookie_value(SESSION_COOKIE))
            self._send_json(
                200,
                _json_success({"authenticated": False}),
                {"Set-Cookie": self._session_cookie("", 0)},
            )

        def _handle_auth_me(self):
            if not auth_required:
                self._send_json(
                    200,
                    _json_success({"authenticated": True, "account": None}),
                )
                return
            account = self._current_account()
            if account is None:
                raise APIError("AUTH_REQUIRED", "Sign in to continue.", status=401)
            self._send_json(
                200,
                _json_success({"authenticated": True, "account": account}),
            )

        def _handle_create_account_token(self):
            account = self._current_account()
            if account is None:
                raise APIError("AUTH_REQUIRED", "Sign in to continue.", status=401)
            payload = self._read_json_body()
            ttl_seconds = payload.get("ttl_seconds", 90 * 24 * 60 * 60)
            try:
                ttl_seconds = int(ttl_seconds)
            except (TypeError, ValueError) as exc:
                raise APIError(
                    "INVALID_INPUT",
                    "ttl_seconds must be an integer.",
                    400,
                ) from exc
            token = create_account_access_token(
                db_path,
                account["id"],
                name=payload.get("name", "CLI"),
                ttl_seconds=ttl_seconds,
            )
            self._send_json(201, _json_success(token))

        def _require_browser_account(self):
            account = self._current_account()
            if account is None:
                raise APIError("AUTH_REQUIRED", "Sign in to continue.", status=401)
            return account

        def _handle_list_account_tokens(self):
            account = self._require_browser_account()
            self._send_json(
                200,
                _json_success(
                    {"tokens": list_account_access_tokens(db_path, account["id"])}
                ),
            )

        def _handle_revoke_account_token(self, token_id):
            account = self._require_browser_account()
            revoke_account_access_token(db_path, account["id"], token_id)
            self._send_json(200, _json_success({"revoked": True, "id": token_id}))

        def _begin_github_login(self, return_to="/"):
            if not github_configured or provider_client is None:
                raise APIError("AUTH_FLOW_UNAVAILABLE", "GitHub sign-in is not configured.", 404)
            attempt = create_login_attempt(
                db_path,
                return_to=safe_return_to(return_to),
                ttl_seconds=oauth_state_ttl_seconds,
            )
            location = provider_client.authorization_url(
                self._oauth_callback_url(),
                attempt["state"],
                attempt["code_challenge"],
            )
            self._send_redirect(
                location,
                [self._oauth_state_cookie(attempt["state"], oauth_state_ttl_seconds)],
            )

        def _handle_github_start(self, query):
            return_to = safe_return_to(query.get("return_to", ["/"])[0])
            self._begin_github_login(return_to=return_to)

        def _handle_github_callback(self, query):
            clear_state = self._oauth_state_cookie("", 0)
            if query.get("error"):
                self._send_redirect("/?auth_error=github_denied", [clear_state])
                return

            state = query.get("state", [""])[0]
            cookie_state = self._cookie_value(OAUTH_STATE_COOKIE) or ""
            if not state or not hmac.compare_digest(state, cookie_state):
                self._send_redirect("/?auth_error=invalid_state", [clear_state])
                return

            try:
                attempt = consume_login_attempt(db_path, state)
                code = query.get("code", [""])[0]
                if not code:
                    raise APIError("OAUTH_CODE_MISSING", "GitHub did not return a sign-in code.", 400)
                if provider_client is None:
                    raise APIError("AUTH_FLOW_UNAVAILABLE", "GitHub sign-in is not configured.", 404)
                access_token = provider_client.exchange_code(
                    code,
                    self._oauth_callback_url(),
                    attempt["code_verifier"],
                )
                user = provider_client.get_user(access_token)
                account = upsert_github_account(db_path, user)
                session = create_web_session(
                    db_path,
                    account["id"],
                    ttl_seconds=account_session_ttl_seconds,
                )
            except APIError as exc:
                LOGGER.warning("GitHub sign-in failed: %s", exc.code)
                self._send_redirect("/?auth_error=github_failed", [clear_state])
                return

            self._send_redirect(
                attempt["return_to"],
                [
                    self._session_cookie(session["token"], account_session_ttl_seconds),
                    clear_state,
                ],
            )

        def _handle_api_error(self, exc):
            headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
            self._send_json(
                exc.status,
                _json_error(exc.code, exc.message, exc.details),
                headers,
            )

        def _route_post(self, path, account_id=None):
            payload = self._read_json_body()
            if path == "/api/v1/hub/link":
                result = link_project(
                    db_path=db_path,
                    project_name=payload.get("project_name"),
                    repo=payload.get("repo", {}),
                    workspace_id=payload.get("workspace", {}).get("workspace_id"),
                    account_id=account_id,
                )
                self._send_json(200, _json_success(result))
                return

            if path == "/api/v1/sync-batches":
                result = store_sync_batch(
                    db_path=db_path,
                    payload=payload,
                    account_id=account_id,
                )
                self._send_json(200, _json_success(result))
                return

            raise APIError("OBJECT_NOT_FOUND", f"Endpoint {path} not found.", status=404)

        def _route_get(self, path, query, account_id=None):
            if path == "/api/v1/projects":
                self._send_json(
                    200,
                    _json_success(list_projects(db_path, account_id=account_id)),
                )
                return

            if path.startswith("/api/v1/projects/") and path.endswith("/overview"):
                project_id = path.split("/")[4]
                self._send_json(
                    200,
                    _json_success(
                        project_overview(db_path, project_id, account_id=account_id)
                    ),
                )
                return

            if path.startswith("/api/v1/projects/") and path.endswith("/handoff"):
                project_id = path.split("/")[4]
                self._send_json(
                    200,
                    _json_success(
                        project_handoff(db_path, project_id, account_id=account_id)
                    ),
                )
                return

            if path.startswith("/api/v1/intents/"):
                remote_object_id = path.split("/")[4]
                self._send_json(
                    200,
                    _json_success(
                        get_intent_detail(db_path, remote_object_id, account_id=account_id)
                    ),
                )
                return

            if path.startswith("/api/v1/decisions/"):
                remote_object_id = path.split("/")[4]
                self._send_json(
                    200,
                    _json_success(
                        get_decision_detail(db_path, remote_object_id, account_id=account_id)
                    ),
                )
                return

            if path.startswith("/api/v1/snaps/"):
                remote_object_id = path.split("/")[4]
                self._send_json(
                    200,
                    _json_success(
                        get_snap_detail(db_path, remote_object_id, account_id=account_id)
                    ),
                )
                return

            if path == "/api/v1/search":
                project_id = query.get("project_id", [None])[0]
                if not project_id:
                    raise APIError(
                        "INVALID_INPUT",
                        "Missing query parameter 'project_id'.",
                        status=400,
                    )
                search_query = query.get("q", [""])[0]
                self._send_json(
                    200,
                    _json_success(
                        search_project(
                            db_path,
                            project_id,
                            search_query,
                            account_id=account_id,
                        )
                    ),
                )
                return

            raise APIError("OBJECT_NOT_FOUND", f"Endpoint {path} not found.", status=404)

        def do_POST(self):
            parsed = urlparse(self.path)
            try:
                self._check_origin()
                if parsed.path == "/api/v1/auth/logout":
                    self._handle_logout()
                    return
                if parsed.path == "/api/v1/auth/tokens":
                    self._check_origin()
                    self._handle_create_account_token()
                    return
                if (
                    parsed.path.startswith("/api/v1/auth/tokens/")
                    and parsed.path.endswith("/revoke")
                ):
                    self._check_origin()
                    token_id = parsed.path.split("/")[5]
                    self._handle_revoke_account_token(token_id)
                    return
                context = {"account": None}
                if parsed.path.startswith("/api/"):
                    # Sync writes require an account PAT. Browser sessions stay
                    # read-only so a compromised page cannot mutate history.
                    context = self._require_auth(allow_cookie=False)
                account = context.get("account")
                self._route_post(
                    parsed.path,
                    account_id=account.get("id") if account else None,
                )
            except APIError as exc:
                self._handle_api_error(exc)
            except Exception:  # pragma: no cover - defensive fallback
                LOGGER.exception("Unhandled IntHub POST error")
                self._send_json(500, _json_error("INTERNAL_ERROR", "Unhandled server error."))

        def do_GET(self):
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/api/v1/auth/github/start":
                    self._handle_github_start(parse_qs(parsed.query))
                    return

                if parsed.path == "/api/v1/auth/github/callback":
                    self._handle_github_callback(parse_qs(parsed.query))
                    return

                if parsed.path in {"/health", "/healthz"}:
                    self._send_json(
                        200,
                        _json_success({"service": "inthub-api", "status": "alive"}),
                    )
                    return

                if parsed.path == "/readyz":
                    check_database(db_path)
                    self._send_json(
                        200,
                        _json_success({"service": "inthub-api", "status": "ready"}),
                    )
                    return

                if parsed.path == "/api/v1/auth/me":
                    self._check_origin()
                    self._handle_auth_me()
                    return

                if parsed.path == "/api/v1/auth/tokens":
                    self._check_origin()
                    self._handle_list_account_tokens()
                    return

                if parsed.path.startswith("/api/"):
                    self._check_origin()
                    context = self._require_auth(allow_cookie=True)
                    account = context.get("account")
                    self._route_get(
                        parsed.path,
                        parse_qs(parsed.query),
                        account_id=account.get("id") if account else None,
                    )
                    return

                if serve_web and self._serve_web(parsed.path):
                    return

                self._route_get(parsed.path, parse_qs(parsed.query), account_id=None)
            except APIError as exc:
                self._handle_api_error(exc)
            except Exception:  # pragma: no cover - defensive fallback
                LOGGER.exception("Unhandled IntHub GET error")
                self._send_json(500, _json_error("INTERNAL_ERROR", "Unhandled server error."))

        def do_HEAD(self):
            self.do_GET()

        def do_OPTIONS(self):
            try:
                self._check_origin()
                self.send_response(204)
                request_origin = self.headers.get("Origin")
                if request_origin:
                    if origin_allowlist is None:
                        self.send_header("Access-Control-Allow-Origin", "*")
                    else:
                        self.send_header("Access-Control-Allow-Origin", request_origin)
                        self.send_header("Vary", "Origin")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
                self.send_header("Access-Control-Max-Age", "600")
                self.end_headers()
            except APIError as exc:
                self._handle_api_error(exc)

        def do_TRACE(self):
            self._send_json(405, _json_error("METHOD_NOT_ALLOWED", "TRACE is not allowed."))

        def log_message(self, _format, *_args):
            return

    return IntHubHandler


def build_server(
    host,
    port,
    db_path,
    serve_web=False,
    public_api_base_url=None,
    default_project_id=None,
    web_static_dir=None,
    require_auth=False,
    allowed_origins=None,
    max_body_bytes=DEFAULT_MAX_BODY_BYTES,
    secure_cookies=False,
    github_client_id=None,
    github_client_secret=None,
    oauth_client=None,
    account_session_ttl_seconds=ACCOUNT_SESSION_TTL_SECONDS,
    oauth_state_ttl_seconds=OAUTH_STATE_TTL_SECONDS,
):
    check_database(db_path)
    return ThreadingHTTPServer(
        (host, port),
        make_handler(
            db_path,
            serve_web=serve_web,
            public_api_base_url=public_api_base_url,
            default_project_id=default_project_id,
            web_static_dir=web_static_dir,
            require_auth=require_auth,
            allowed_origins=allowed_origins,
            max_body_bytes=max_body_bytes,
            secure_cookies=secure_cookies,
            github_client_id=github_client_id,
            github_client_secret=github_client_secret,
            oauth_client=oauth_client,
            account_session_ttl_seconds=account_session_ttl_seconds,
            oauth_state_ttl_seconds=oauth_state_ttl_seconds,
        ),
    )


def run_server(
    host,
    port,
    db_path,
    serve_web=False,
    public_api_base_url=None,
    default_project_id=None,
    web_static_dir=None,
    require_auth=False,
    allowed_origins=None,
    max_body_bytes=DEFAULT_MAX_BODY_BYTES,
    secure_cookies=False,
    github_client_id=None,
    github_client_secret=None,
    oauth_client=None,
    account_session_ttl_seconds=ACCOUNT_SESSION_TTL_SECONDS,
    oauth_state_ttl_seconds=OAUTH_STATE_TTL_SECONDS,
):
    server = build_server(
        host,
        port,
        db_path,
        serve_web=serve_web,
        public_api_base_url=public_api_base_url,
        default_project_id=default_project_id,
        web_static_dir=web_static_dir,
        require_auth=require_auth,
        allowed_origins=allowed_origins,
        max_body_bytes=max_body_bytes,
        secure_cookies=secure_cookies,
        github_client_id=github_client_id,
        github_client_secret=github_client_secret,
        oauth_client=oauth_client,
        account_session_ttl_seconds=account_session_ttl_seconds,
        oauth_state_ttl_seconds=oauth_state_ttl_seconds,
    )
    web_status = " + Web" if serve_web else ""
    print(
        f"IntHub API{web_status} listening on http://{host}:{server.server_port} "
        f"using {describe_database(db_path)}"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    logging.basicConfig(level=os.getenv("INTHUB_LOG_LEVEL", "INFO"))
    parser = argparse.ArgumentParser(description="Run the IntHub V1 API server.")
    parser.add_argument("--host", default=os.getenv("INTHUB_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", os.getenv("INTHUB_PORT", "8000"))),
    )
    parser.add_argument("--db-path", default=os.getenv("INTHUB_DB_PATH", ".inthub/inthub.db"))
    parser.add_argument("--database-url", default=_env_or_file("INTHUB_DATABASE_URL"))
    parser.add_argument(
        "--serve-web",
        action="store_true",
        default=_env_flag("INTHUB_SERVE_WEB", False),
    )
    parser.add_argument("--public-api-base-url", default=os.getenv("INTHUB_API_BASE_URL"))
    parser.add_argument("--default-project-id", default=os.getenv("INTHUB_DEFAULT_PROJECT_ID"))
    parser.add_argument("--web-static-dir", default=os.getenv("INTHUB_WEB_STATIC_DIR"))
    args = parser.parse_args()

    github_client_id = _env_or_file("INTHUB_GITHUB_CLIENT_ID")
    github_client_secret = _env_or_file("INTHUB_GITHUB_CLIENT_SECRET")
    github_configured = bool(github_client_id or github_client_secret)
    allowed_origins = os.getenv("INTHUB_ALLOWED_ORIGINS")
    run_server(
        args.host,
        args.port,
        args.database_url or args.db_path,
        serve_web=args.serve_web,
        public_api_base_url=args.public_api_base_url,
        default_project_id=args.default_project_id,
        web_static_dir=args.web_static_dir,
        require_auth=_env_flag(
            "INTHUB_REQUIRE_AUTH",
            github_configured,
        ),
        allowed_origins=allowed_origins,
        max_body_bytes=int(os.getenv("INTHUB_MAX_BODY_BYTES", str(DEFAULT_MAX_BODY_BYTES))),
        secure_cookies=_env_flag("INTHUB_SECURE_COOKIES", False),
        github_client_id=github_client_id,
        github_client_secret=github_client_secret,
        account_session_ttl_seconds=int(
            os.getenv("INTHUB_SESSION_TTL_SECONDS", str(ACCOUNT_SESSION_TTL_SECONDS))
        ),
    )


if __name__ == "__main__":
    main()
