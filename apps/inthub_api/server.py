"""Shared semantic-history API and Web shell."""

import argparse
import logging
import os
import re
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from apps.inthub_api.access import VISITOR
from apps.inthub_api.common import APIError
from apps.inthub_api.db import check_database, describe_database
from apps.inthub_api.product_deletion import ProductDeletionClient, subject_for_account
from apps.inthub_api.tenon import TenonOIDCClient
from apps.inthub_api.http_auth import HttpAuth
from apps.inthub_api.http_base import HttpBase
from apps.inthub_api.http_common import ACCOUNT_SESSION_TTL_SECONDS, AUTH_BODY_LIMIT, DEFAULT_MAX_BODY_BYTES, IntHubHTTPServer, LOGGER, LOOPBACK_HOSTS, OAUTH_STATE_TTL_SECONDS, QUIET_PATHS, STATIC_DIR, TEAM_ACTIONS, VISITOR_READS, _RateLimiter, _env_flag, _env_or_file, _json_error, _json_success, _normalize_origins
from apps.inthub_api.http_routes import HttpRoutes


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
    tenon_client_id=None,
    tenon_client_secret=None,
    oauth_client=None,
    deletion_client=None,
    account_session_ttl_seconds=ACCOUNT_SESSION_TTL_SECONDS,
    oauth_state_ttl_seconds=OAUTH_STATE_TTL_SECONDS,
):
    root = Path(web_static_dir or STATIC_DIR).resolve()
    tenon_configured = bool(tenon_client_id or tenon_client_secret)
    if tenon_configured and not (tenon_client_id and tenon_client_secret):
        raise ValueError("Both Tenon OIDC client ID and client secret are required.")
    provider_client = oauth_client
    if tenon_configured and provider_client is None:
        provider_client = TenonOIDCClient(tenon_client_id, tenon_client_secret)
    auth_required = bool(require_auth or tenon_configured)
    if auth_required and not tenon_configured:
        raise ValueError("Authentication is required but no IntHub authentication is configured.")
    auth_mode = "tenon" if tenon_configured else "none"
    if tenon_configured and not public_api_base_url:
        raise ValueError("Tenon sign-in requires an explicit public API base URL.")
    if tenon_configured:
        callback_origin = urlparse(public_api_base_url)
        if (callback_origin.scheme != "https" or not callback_origin.netloc
                or callback_origin.username or callback_origin.password
                or callback_origin.path not in {"", "/"}
                or callback_origin.query or callback_origin.fragment):
            raise ValueError("Tenon sign-in requires an exact HTTPS public origin.")
    origin_allowlist = _normalize_origins(allowed_origins)
    # Tenon mode is HTTPS-only, so its cookies are always Secure.
    secure_cookies = bool(secure_cookies or tenon_configured)
    allowed_hosts = set(LOOPBACK_HOSTS)
    for url in [public_api_base_url, *(origin_allowlist or ())]:
        if url and urlparse(url).hostname:
            allowed_hosts.add(urlparse(url).hostname)
    sign_in_limiter = _RateLimiter(limit=30, window_seconds=60)
    # A visitor's read parses a whole snapshot, with no account to answer for it.
    visitor_limiter = _RateLimiter(limit=300, window_seconds=60)
    # A code has 20^8 values and lives ten minutes; these keep guessing and polling cheap.
    device_start_limiter = _RateLimiter(limit=10, window_seconds=60)
    device_poll_limiter = _RateLimiter(limit=120, window_seconds=60)
    device_code_limiter = _RateLimiter(limit=20, window_seconds=60)
    # Twenty requests a second from one address is far above any person or Agent.
    api_limiter = _RateLimiter(limit=1200, window_seconds=60)
    # Each one makes a call to Tenon, with no credentials to check first.
    deletion_limiter = _RateLimiter(limit=30, window_seconds=60)
    product_deletion = deletion_client
    if tenon_configured and product_deletion is None:
        product_deletion = ProductDeletionClient(tenon_client_id, tenon_client_secret)
    settings = SimpleNamespace(
        account_session_ttl_seconds=account_session_ttl_seconds,
        allowed_hosts=allowed_hosts,
        api_limiter=api_limiter,
        auth_mode=auth_mode,
        auth_required=auth_required,
        db_path=db_path,
        default_project_id=default_project_id,
        deletion_limiter=deletion_limiter,
        device_code_limiter=device_code_limiter,
        device_poll_limiter=device_poll_limiter,
        device_start_limiter=device_start_limiter,
        max_body_bytes=max_body_bytes,
        oauth_state_ttl_seconds=oauth_state_ttl_seconds,
        origin_allowlist=origin_allowlist,
        product_deletion=product_deletion,
        provider_client=provider_client,
        public_api_base_url=public_api_base_url,
        root=root,
        secure_cookies=secure_cookies,
        serve_web=serve_web,
        sign_in_limiter=sign_in_limiter,
        tenon_configured=tenon_configured,
        visitor_limiter=visitor_limiter,
    )

    class IntHubHandler(HttpRoutes, HttpAuth, HttpBase, BaseHTTPRequestHandler):
        hub = settings
        server_version = "IntHub"
        # Bound slow or idle clients so they cannot pin worker threads.
        timeout = 30

        def do_POST(self):
            parsed = urlparse(self.path)
            try:
                self._check_host()
                if not parsed.path.startswith("/api/"):
                    raise APIError("OBJECT_NOT_FOUND", f"Endpoint {parsed.path} not found.", status=404)
                self._check_rate()
                if parsed.path == "/api/auth/tenon/delete/execute":
                    # Server-to-server from Tenon: browsers always send Origin.
                    if self.headers.get("Origin") or not self.hub.product_deletion:
                        raise APIError("DELETION_AUTHORIZATION_REQUIRED", "Use Tenon's product deletion flow.", 403)
                    if not self.hub.deletion_limiter.allow(self._client_address()):
                        raise APIError("RATE_LIMITED", "Too many requests. Wait a minute and try again.", 429)
                    payload = self._read_json_body(limit=AUTH_BODY_LIMIT, require_json=False)
                    self._send_json(200, self.hub.product_deletion.execute(self.hub.db_path, payload))
                    return
                self._check_origin()
                if parsed.path == "/api/auth/tenon/delete/start":
                    # Same-origin JSON POST + host-only session is this web app's
                    # CSRF boundary. A CLI PAT cannot delete a browser account.
                    if self.headers.get("Origin") != self._request_base_url():
                        raise APIError("ORIGIN_DENIED", "The request origin is not allowed.", 403)
                    if not self.headers.get("Content-Type", "").startswith("application/json"):
                        raise APIError("INVALID_INPUT", "JSON is required.", 415)
                    if self._read_json_body(limit=AUTH_BODY_LIMIT) != {}:
                        raise APIError("INVALID_DELETION_REQUEST", "Invalid deletion request.", 400)
                    account = self._require_browser_account()
                    if not self.hub.product_deletion:
                        raise APIError("DELETION_SERVICE_UNAVAILABLE", "Tenon account management is temporarily unavailable.", 503)
                    self._send_json(200, _json_success(self.hub.product_deletion.start(subject_for_account(self.hub.db_path, account["id"]))))
                    return
                if parsed.path in ("/api/v1/auth/device/start", "/api/v1/auth/device/poll"):
                    self._handle_device_cli(parsed.path)
                    return
                if parsed.path in ("/api/v1/auth/device/lookup", "/api/v1/auth/device/decide"):
                    self._handle_device_browser(parsed.path)
                    return
                if parsed.path == "/api/v1/auth/tenon/prepare":
                    body = self._read_json_body(limit=AUTH_BODY_LIMIT)
                    location, cookie = self._prepare_tenon_login(body.get("return_to", "/"))
                    self._send_json(200, _json_success({"authorizationUrl": location}), {"Set-Cookie": cookie})
                    return
                if parsed.path.startswith("/api/v1/auth/github/"):
                    raise APIError("ACCOUNT_MANAGED_BY_TENON", "Sign in with Tenon.", 410)
                if parsed.path == "/api/v1/auth/logout":
                    self._handle_logout()
                    return
                if parsed.path == "/api/v1/auth/tokens":
                    self._handle_create_account_token()
                    return
                if (
                    parsed.path.startswith("/api/v1/auth/tokens/")
                    and parsed.path.endswith("/revoke")
                ):
                    token_id = parsed.path.split("/")[5]
                    self._handle_revoke_account_token(token_id)
                    return
                if re.fullmatch(r"/api/v1/projects/[^/]+/(rename|delete|visibility|transfer)", parsed.path):
                    self._handle_project_admin(parsed.path)
                    return
                for pattern, action in TEAM_ACTIONS:
                    match = re.fullmatch(pattern, parsed.path)
                    if match:
                        self._handle_team_action(action, match.groups())
                        return
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
                self._check_host()
                if parsed.path == "/showcase" or parsed.path.startswith(("/showcase/", "/api/v1/public-profiles/")):
                    raise APIError("FEATURE_RETIRED", "Public showcase has been removed.", status=410)
                if parsed.path.startswith("/api/v1/auth/github/"):
                    raise APIError("ACCOUNT_MANAGED_BY_TENON", "Sign in with Tenon.", 410)

                if parsed.path == "/api/v1/auth/tenon/callback":
                    self._handle_tenon_callback(parse_qs(parsed.query))
                    return

                if parsed.path in {"/health", "/healthz"}:
                    self._send_json(
                        200,
                        _json_success({"service": "inthub-api", "status": "alive"}),
                    )
                    return

                if parsed.path == "/readyz" or parsed.path.startswith("/api/"):
                    self._check_rate()
                if parsed.path == "/readyz":
                    check_database(self.hub.db_path)
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
                    viewer = self._viewer()
                    if viewer == VISITOR:
                        if not VISITOR_READS.fullmatch(parsed.path):
                            raise APIError("AUTH_REQUIRED", "Sign in or provide a valid IntHub account access token.", status=401)
                        if not self.hub.visitor_limiter.allow(self._client_address()):
                            raise APIError("RATE_LIMITED", "Too many requests. Wait a minute and try again.", 429)
                    self._route_get(parsed.path, parse_qs(parsed.query), account_id=viewer)
                    return

                if self.hub.serve_web and self._serve_web(parsed.path):
                    return

                raise APIError("OBJECT_NOT_FOUND", f"Endpoint {parsed.path} not found.", status=404)
            except APIError as exc:
                self._handle_api_error(exc)
            except Exception:  # pragma: no cover - defensive fallback
                LOGGER.exception("Unhandled IntHub GET error")
                self._send_json(500, _json_error("INTERNAL_ERROR", "Unhandled server error."))

        def do_HEAD(self):
            self.do_GET()

        def do_OPTIONS(self):
            try:
                self._check_host()
                self._check_origin()
                self.send_response(204)
                request_origin = self.headers.get("Origin")
                if request_origin and self.hub.origin_allowlist is not None:
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

        def _method_not_allowed(self):
            self._send_json(405, _json_error("METHOD_NOT_ALLOWED", f"{self.command} is not supported."), {"Allow": "GET, HEAD, POST, OPTIONS"})

        do_PUT = do_PATCH = do_DELETE = _method_not_allowed

        def version_string(self):
            # No interpreter or library versions in responses.
            return self.server_version

        def parse_request(self):
            self._started = time.monotonic()
            return super().parse_request()

        def log_request(self, code="-", size="-"):
            # One line per request without query strings, which can carry search text.
            path = urlparse(self.path).path
            if path not in QUIET_PATHS:
                elapsed = (time.monotonic() - getattr(self, "_started", time.monotonic())) * 1000
                LOGGER.info("%s %s %s %.0fms", self.command, path, code, elapsed)

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
    tenon_client_id=None,
    tenon_client_secret=None,
    oauth_client=None,
    account_session_ttl_seconds=ACCOUNT_SESSION_TTL_SECONDS,
    oauth_state_ttl_seconds=OAUTH_STATE_TTL_SECONDS,
):
    check_database(db_path)
    return IntHubHTTPServer(
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
            tenon_client_id=tenon_client_id,
            tenon_client_secret=tenon_client_secret,
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
    tenon_client_id=None,
    tenon_client_secret=None,
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
        tenon_client_id=tenon_client_id,
        tenon_client_secret=tenon_client_secret,
        oauth_client=oauth_client,
        account_session_ttl_seconds=account_session_ttl_seconds,
        oauth_state_ttl_seconds=oauth_state_ttl_seconds,
    )
    web_status = " + Web" if serve_web else ""
    print(
        f"IntHub API{web_status} listening on http://{host}:{server.server_port} "
        f"using {describe_database(db_path)}"
    )
    # docker stop sends SIGTERM to PID 1: drain in-flight requests and exit
    # instead of waiting out the grace period for SIGKILL.
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown, daemon=True).start())
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

    tenon_client_id = _env_or_file("INTHUB_TENON_CLIENT_ID")
    tenon_client_secret = _env_or_file("INTHUB_TENON_CLIENT_SECRET")
    tenon_configured = bool(tenon_client_id or tenon_client_secret)
    require_auth = _env_flag("INTHUB_REQUIRE_AUTH", tenon_configured)
    if (not tenon_configured and not require_auth and args.host not in LOOPBACK_HOSTS
            and not _env_flag("INTHUB_ALLOW_UNAUTHENTICATED", False)):
        parser.error(
            "refusing to serve unauthenticated history on a non-loopback address; "
            "configure Tenon sign-in, bind to 127.0.0.1, or set INTHUB_ALLOW_UNAUTHENTICATED=1 "
            "for an isolated container"
        )
    allowed_origins = os.getenv("INTHUB_ALLOWED_ORIGINS")
    run_server(
        args.host,
        args.port,
        args.database_url or args.db_path,
        serve_web=args.serve_web,
        public_api_base_url=args.public_api_base_url,
        default_project_id=args.default_project_id,
        web_static_dir=args.web_static_dir,
        require_auth=require_auth,
        allowed_origins=allowed_origins,
        max_body_bytes=int(os.getenv("INTHUB_MAX_BODY_BYTES", str(DEFAULT_MAX_BODY_BYTES))),
        secure_cookies=_env_flag("INTHUB_SECURE_COOKIES", False),
        tenon_client_id=tenon_client_id,
        tenon_client_secret=tenon_client_secret,
    )


if __name__ == "__main__":
    main()
