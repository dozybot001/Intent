"""Shared semantic-history API and Web shell."""

import argparse
import hmac
import json
import logging
import mimetypes
import os
import re
import signal
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse
from apps.inthub_web import product_version

from apps.inthub_api.access import VISITOR
from apps.inthub_api.auth import (
    account_for_access_token,
    create_account_access_token,
    delete_web_session,
    list_account_access_tokens,
    revoke_account_access_token,
    safe_return_to,
)
from apps.inthub_api.tenon import (
    TenonOIDCClient, account_for_identity, account_for_session,
    consume_attempt, create_attempt, create_session, SESSION_MAX_SECONDS,
)
from apps.inthub_api.common import APIError
from apps.inthub_api.db import check_database, describe_database
from apps.inthub_api.history import link_history, push_history, read_history
from apps.inthub_api.product_deletion import ProductDeletionClient, subject_for_account
from apps.inthub_api.projects import delete_project, export_project, rename_project, set_visibility, transfer_project
from apps.inthub_api.revisions import project_revisions, revision_detail
from apps.inthub_api.queries import (
    SNAP_PAGE_MAX,
    get_decision_detail,
    get_intent_detail,
    get_snap_detail,
    list_projects,
    project_handoff,
    project_home,
    project_overview,
    project_snaps,
    search_project,
)
from apps.inthub_api.teams import (
    accept_invite,
    create_invite,
    create_team,
    delete_team,
    list_teams,
    preview_invite,
    remove_member,
    revoke_invite,
    set_member_role,
    team_detail,
    update_team,
)
from intent_cli.store import StorageSecurityError, validate_object_id

STATIC_DIR = Path(__file__).resolve().parents[1] / "inthub_web" / "static"
DEFAULT_MAX_BODY_BYTES = 16 * 1024 * 1024
# Small JSON bodies only: sign-in, token and deletion requests.
AUTH_BODY_LIMIT = 16 * 1024
# Host-only and HTTPS-only: no other *.tenon.asia site can plant this cookie.
SESSION_COOKIE = "__Host-inthub_session"
REVISION_PAGE_MAX = 100
# What a signed-out visitor can ask for; the project itself must still be public.
VISITOR_READS = re.compile(r"/api/v1/(?:projects/[^/]+/(?:overview|handoff|snaps|revisions(?:/[^/]+)?)|(?:intents|decisions|snaps)/[^/]+|search)")
TEAM_ACTIONS = (
    (r"/api/v1/teams", lambda db, me, body: create_team(db, body.get("name"), body.get("slug"), me)),
    (r"/api/v1/teams/([^/]+)", lambda db, me, body, team: update_team(db, team, body.get("name"), body.get("slug"), me)),
    (r"/api/v1/teams/([^/]+)/delete", lambda db, me, body, team: delete_team(db, team, body.get("confirm"), me)),
    (r"/api/v1/teams/([^/]+)/invites", lambda db, me, body, team: create_invite(db, team, body.get("role"), me)),
    (r"/api/v1/teams/([^/]+)/invites/([^/]+)/revoke", lambda db, me, body, team, invite: revoke_invite(db, team, invite, me)),
    (r"/api/v1/teams/([^/]+)/members/([^/]+)/role", lambda db, me, body, team, member: set_member_role(db, team, member, body.get("role"), me)),
    (r"/api/v1/teams/([^/]+)/members/([^/]+)/remove", lambda db, me, body, team, member: remove_member(db, team, member, me)),
    (r"/api/v1/invites/accept", lambda db, me, body: accept_invite(db, body.get("token"), me)),
)
OAUTH_STATE_COOKIE = "inthub_oauth_state"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
QUIET_PATHS = {"/health", "/healthz", "/readyz"}
ACCOUNT_SESSION_TTL_SECONDS = SESSION_MAX_SECONDS
OAUTH_STATE_TTL_SECONDS = 10 * 60
LOGGER = logging.getLogger("inthub.api")


def _json_success(result):
    return {"ok": True, "result": result}


def _query_int(query, name, default, minimum, maximum):
    raw = query.get(name, [None])[0]
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        value = None
    if value is None or value < minimum or (maximum is not None and value > maximum):
        bound = f" and {maximum}" if maximum is not None else " or more"
        raise APIError("INVALID_INPUT", f"Query parameter '{name}' must be an integer of {minimum}{bound}.", status=400)
    return value


def _login_error_return(return_to, code):
    target = urlparse(safe_return_to(return_to))
    query = [(key, value) for key, value in parse_qsl(target.query, keep_blank_values=True) if key != "auth_error"]
    query.append(("auth_error", code))
    return urlunparse(target._replace(query=urlencode(query)))


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


class _RateLimiter:
    """Fixed-window limiter for unauthenticated endpoints that create state."""

    def __init__(self, limit, window_seconds):
        self.limit = limit
        self.window = window_seconds
        self.hits = {}
        self.lock = threading.Lock()

    def allow(self, key):
        now = time.monotonic()
        with self.lock:
            recent = self.hits.setdefault(key, deque())
            while recent and now - recent[0] > self.window:
                recent.popleft()
            if len(recent) >= self.limit:
                return False
            recent.append(now)
            if len(self.hits) > 10000:
                self.hits = {key: recent}
            return True


class IntHubHTTPServer(ThreadingHTTPServer):
    # The stdlib default backlog of 5 resets connections under modest bursts.
    request_queue_size = 128


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
    product_deletion = deletion_client
    if tenon_configured and product_deletion is None:
        product_deletion = ProductDeletionClient(tenon_client_id, tenon_client_secret)

    class IntHubHandler(BaseHTTPRequestHandler):
        server_version = "IntHub"
        # Bound slow or idle clients so they cannot pin worker threads.
        timeout = 30

        def _send_json(self, status, payload, extra_headers=None, compact=False):
            options = (
                {"ensure_ascii": False, "separators": (",", ":")}
                if compact
                else {"indent": 2, "ensure_ascii": False}
            )
            body = json.dumps(payload, **options).encode("utf-8")
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
                "img-src 'self' data:; "
                "script-src 'self'; style-src 'self'; connect-src 'self'; "
                "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
                "form-action 'self'",
            )
            self.send_header(
                "Permissions-Policy",
                "camera=(), microphone=(), geolocation=(), payment=()",
            )
            request_origin = self.headers.get("Origin")
            # Cross-origin access is only ever granted to an explicit allowlist;
            # the bundled web app is same-origin and needs no CORS at all.
            if (request_origin and origin_allowlist is not None
                    and request_origin.rstrip("/") in origin_allowlist):
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
            return f"{self._request_base_url()}/api/v1/auth/tenon/callback"

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
            cache_control = "no-cache" if path.suffix == ".html" else "public, max-age=3600"
            self._send_bytes(200, body, content_type, cache_control=cache_control)

        def _serve_index(self):
            self._send_file(root / "index.html")

        def _serve_web(self, path):
            if path == "/auth/redirect":
                self._send_file(root / "auth-redirect.html")
                return True
            if path == "/config.json":
                self._send_json(
                    200,
                    {
                        "apiBaseUrl": self._request_base_url(),
                        "defaultProjectId": default_project_id,
                        "authRequired": auth_required,
                        "authMode": auth_mode,
                        "productVersion": product_version(),
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

        def _check_host(self):
            # Reject DNS-rebound names: a page on evil.example resolving to
            # 127.0.0.1 still sends its own name in Host.
            host = self.headers.get("Host")
            if host and (urlparse(f"//{host}").hostname or "") not in allowed_hosts:
                raise APIError("HOST_DENIED", "This host name is not served here.", status=403)

        def _same_origin(self, origin):
            if origin == self._request_base_url():
                return True
            host = self.headers.get("Host")
            return bool(host) and origin in {f"http://{host}", f"https://{host}"}

        def _check_origin(self):
            origin = self.headers.get("Origin")
            if not origin:
                return
            origin = origin.rstrip("/")
            allowed = origin in origin_allowlist if origin_allowlist is not None else self._same_origin(origin)
            if not allowed:
                raise APIError(
                    "ORIGIN_DENIED",
                    "The request origin is not allowed.",
                    status=403,
                )

        def _client_address(self):
            # Production listens on loopback behind Caddy, which sets this header.
            forwarded = self.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
            return forwarded or self.client_address[0]

        def _read_json_body(self, limit=None, require_json=True):
            limit = max_body_bytes if limit is None else min(limit, max_body_bytes)
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
            if length > limit:
                raise APIError(
                    "PAYLOAD_TOO_LARGE",
                    f"Request body exceeds the {limit}-byte limit.",
                    status=413,
                )
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if length and require_json and content_type != "application/json":
                raise APIError("UNSUPPORTED_MEDIA_TYPE", "Request bodies must be application/json.", status=415)
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8") if length else "{}")
            except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
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
            # Parse leniently: one malformed cookie from a sibling site must not
            # hide ours (SimpleCookie stops at the first value it cannot parse).
            for part in self.headers.get("Cookie", "").split(";"):
                key, separator, value = part.strip().partition("=")
                if separator and key == name:
                    return value.strip().strip('"') or None
            return None

        def _current_account(self):
            if not tenon_configured:
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
                path="/api/v1/auth/tenon",
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
            payload = self._read_json_body(limit=AUTH_BODY_LIMIT)
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

        def _viewer(self):
            """None on a hub without accounts, VISITOR when nobody is signed in."""
            if not auth_required:
                return None
            if self.headers.get("Authorization"):
                # A bad token gets an answer, not a visitor's view of the project.
                return self._require_auth()["account"]["id"]
            account = self._current_account()
            return account["id"] if account else VISITOR

        def _browser_action(self):
            # Managing projects and teams is a browser action, like deleting the
            # account: same-origin JSON with the session. Access tokens cannot do it.
            if self.headers.get("Origin") != self._request_base_url():
                raise APIError("ORIGIN_DENIED", "The request origin is not allowed.", 403)
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                raise APIError("INVALID_INPUT", "JSON is required.", 415)
            account_id = self._require_browser_account()["id"] if auth_required else None
            return account_id, self._read_json_body(limit=AUTH_BODY_LIMIT)

        def _handle_project_admin(self, path):
            account_id, body = self._browser_action()
            _, _, _, _, project_id, action = path.split("/")
            if action == "rename":
                result = rename_project(db_path, project_id, body.get("name"), account_id)
            elif action == "delete":
                result = delete_project(db_path, project_id, body.get("confirm"), account_id)
            elif not auth_required:
                raise APIError("OBJECT_NOT_FOUND", "A hub without accounts has no owners or visibility.", 404)
            elif action == "visibility":
                result = set_visibility(db_path, project_id, body.get("visibility"), body.get("confirm"), account_id)
            else:
                result = transfer_project(db_path, project_id, body.get("team_id"), body.get("confirm"), account_id)
            self._send_json(200, _json_success(result))

        def _handle_team_action(self, action, route_args):
            if not auth_required:
                raise APIError("OBJECT_NOT_FOUND", "A hub without accounts has no teams.", 404)
            account_id, body = self._browser_action()
            self._send_json(200, _json_success(action(db_path, account_id, body, *route_args)))

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

        def _prepare_tenon_login(self, return_to="/"):
            self._check_origin()
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                raise APIError("ORIGIN_DENIED", "Start sign-in from IntHub.", 403)
            if not sign_in_limiter.allow(self._client_address()):
                raise APIError("RATE_LIMITED", "Too many sign-in attempts. Wait a minute and try again.", 429)
            if not tenon_configured or provider_client is None:
                raise APIError("AUTH_FLOW_UNAVAILABLE", "Tenon sign-in is not configured.", 404)
            attempt = create_attempt(
                db_path,
                return_to=safe_return_to(return_to),
                ttl_seconds=oauth_state_ttl_seconds,
            )
            try:
                location = provider_client.authorization_url(self._oauth_callback_url(), attempt)
            except Exception:
                consume_attempt(db_path, attempt["state"])
                raise
            target = urlparse(location)
            if (target.scheme != "https" or target.netloc != "account.tenon.asia"
                    or target.path != "/api/auth/oauth2/authorize" or target.fragment):
                consume_attempt(db_path, attempt["state"])
                raise APIError("AUTH_FLOW_UNAVAILABLE", "Tenon authorization is unavailable.", 503)
            return location, self._oauth_state_cookie(attempt["state"], oauth_state_ttl_seconds)

        def _handle_tenon_callback(self, query):
            clear_state = self._oauth_state_cookie("", 0)
            state = query.get("state", [""])[0]
            cookie_state = self._cookie_value(OAUTH_STATE_COOKIE) or ""
            if not state or not hmac.compare_digest(state, cookie_state):
                self._send_redirect("/?auth_error=invalid_state", [clear_state])
                return

            attempt = None
            try:
                attempt = consume_attempt(db_path, state)
                if query.get("error"):
                    self._send_redirect(_login_error_return(attempt["return_to"], "tenon_denied"), [clear_state])
                    return
                code = query.get("code", [""])[0]
                if not code:
                    raise APIError("OAUTH_CODE_MISSING", "Tenon did not return a sign-in code.", 400)
                if provider_client is None:
                    raise APIError("AUTH_FLOW_UNAVAILABLE", "Tenon sign-in is not configured.", 404)
                identity = provider_client.complete_login(
                    code,
                    self._oauth_callback_url(),
                    attempt,
                )
                account = account_for_identity(db_path, identity, request_started_at=attempt.get("started_at"))
                session = create_session(
                    db_path,
                    account["id"],
                    identity,
                    ttl_seconds=account_session_ttl_seconds,
                )
            except APIError as exc:
                LOGGER.warning("Tenon sign-in failed: %s", exc.code)
                self._send_redirect(_login_error_return(attempt["return_to"] if attempt else "/", "tenon_failed"), [clear_state])
                return

            self._send_redirect(
                attempt["return_to"],
                [
                    self._session_cookie(session["token"], session["ttl_seconds"]),
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
            # Match the route before reading any body.
            if path == "/api/v2/link":
                payload = self._read_json_body(limit=AUTH_BODY_LIMIT)
                self._send_json(200, _json_success(link_history(db_path, payload.get("project_name"), account_id)))
                return
            if path == "/api/v2/history":
                self._send_json(200, _json_success(push_history(db_path, self._read_json_body(), account_id)))
                return
            raise APIError("OBJECT_NOT_FOUND", f"Endpoint {path} not found.", status=404)

        def _route_get(self, path, query, account_id=None):
            if path == "/api/v2/history":
                self._send_json(200, _json_success(read_history(
                    db_path, query.get("project", [None])[0], account_id, project_id=query.get("project_id", [None])[0])), compact=True)
                return
            if path == "/api/v1/projects":
                self._send_json(
                    200,
                    _json_success(list_projects(db_path, account_id=account_id)),
                    compact=True,
                )
                return

            if path == "/api/v1/home":
                self._send_json(200, _json_success(project_home(db_path, account_id=account_id)), compact=True)
                return

            if path == "/api/v1/teams" and auth_required:
                self._send_json(200, _json_success(list_teams(db_path, account_id)), compact=True)
                return

            if re.fullmatch(r"/api/v1/teams/[^/]+", path) and auth_required:
                self._send_json(200, _json_success(team_detail(db_path, path.split("/")[4], account_id)), compact=True)
                return

            if path == "/api/v1/invites/preview" and auth_required:
                self._send_json(200, _json_success(preview_invite(db_path, query.get("token", [None])[0], account_id)))
                return

            if path.startswith("/api/v1/projects/") and path.endswith("/overview"):
                project_id = path.split("/")[4]
                self._send_json(
                    200,
                    _json_success(
                        project_overview(db_path, project_id, account_id=account_id)
                    ),
                    compact=True,
                )
                return

            if path.startswith("/api/v1/projects/") and path.endswith("/snaps"):
                project_id = path.split("/")[4]
                offset = _query_int(query, "offset", 0, 0, None)
                limit = _query_int(query, "limit", 50, 1, SNAP_PAGE_MAX)
                intent_id = query.get("intent_id", [None])[0]
                if intent_id is not None:
                    try:
                        validate_object_id("intent", intent_id)
                    except StorageSecurityError as exc:
                        raise APIError("INVALID_INPUT", "Invalid intent_id.", status=400) from exc
                self._send_json(
                    200,
                    _json_success(project_snaps(db_path, project_id, offset, limit, intent_id, query.get("author", [None])[0], account_id=account_id)),
                    compact=True,
                )
                return

            if path.startswith("/api/v1/projects/") and path.endswith("/revisions"):
                offset = _query_int(query, "offset", 0, 0, None)
                limit = _query_int(query, "limit", 30, 1, REVISION_PAGE_MAX)
                self._send_json(200, _json_success(project_revisions(db_path, path.split("/")[4], offset, limit, account_id=account_id)), compact=True)
                return

            if re.fullmatch(r"/api/v1/projects/[^/]+/revisions/[^/]+", path):
                _, _, _, _, project_id, _, revision = path.split("/")
                self._send_json(200, _json_success(revision_detail(db_path, project_id, revision, account_id=account_id)), compact=True)
                return

            if path.startswith("/api/v1/projects/") and path.endswith("/export"):
                self._send_json(200, _json_success(export_project(db_path, path.split("/")[4], account_id=account_id)))
                return

            if path.startswith("/api/v1/projects/") and path.endswith("/handoff"):
                project_id = path.split("/")[4]
                self._send_json(
                    200,
                    _json_success(
                        project_handoff(db_path, project_id, account_id=account_id)
                    ),
                    compact=True,
                )
                return

            if path.startswith("/api/v1/intents/"):
                remote_object_id = path.split("/")[4]
                self._send_json(
                    200,
                    _json_success(
                        get_intent_detail(db_path, remote_object_id, account_id=account_id)
                    ),
                    compact=True,
                )
                return

            if path.startswith("/api/v1/decisions/"):
                remote_object_id = path.split("/")[4]
                self._send_json(
                    200,
                    _json_success(
                        get_decision_detail(db_path, remote_object_id, account_id=account_id)
                    ),
                    compact=True,
                )
                return

            if path.startswith("/api/v1/snaps/"):
                remote_object_id = path.split("/")[4]
                self._send_json(
                    200,
                    _json_success(
                        get_snap_detail(db_path, remote_object_id, account_id=account_id)
                    ),
                    compact=True,
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
                    compact=True,
                )
                return

            raise APIError("OBJECT_NOT_FOUND", f"Endpoint {path} not found.", status=404)

        def do_POST(self):
            parsed = urlparse(self.path)
            try:
                self._check_host()
                if not parsed.path.startswith("/api/"):
                    raise APIError("OBJECT_NOT_FOUND", f"Endpoint {parsed.path} not found.", status=404)
                if parsed.path == "/api/auth/tenon/delete/execute":
                    # Server-to-server from Tenon: browsers always send Origin.
                    if self.headers.get("Origin") or not product_deletion:
                        raise APIError("DELETION_AUTHORIZATION_REQUIRED", "Use Tenon's product deletion flow.", 403)
                    payload = self._read_json_body(limit=AUTH_BODY_LIMIT, require_json=False)
                    self._send_json(200, product_deletion.execute(db_path, payload))
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
                    if not product_deletion:
                        raise APIError("DELETION_SERVICE_UNAVAILABLE", "Tenon account management is temporarily unavailable.", 503)
                    self._send_json(200, _json_success(product_deletion.start(subject_for_account(db_path, account["id"]))))
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
                    viewer = self._viewer()
                    if viewer == VISITOR:
                        if not VISITOR_READS.fullmatch(parsed.path):
                            raise APIError("AUTH_REQUIRED", "Sign in or provide a valid IntHub account access token.", status=401)
                        if not visitor_limiter.allow(self._client_address()):
                            raise APIError("RATE_LIMITED", "Too many requests. Wait a minute and try again.", 429)
                    self._route_get(parsed.path, parse_qs(parsed.query), account_id=viewer)
                    return

                if serve_web and self._serve_web(parsed.path):
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
                if request_origin and origin_allowlist is not None:
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
