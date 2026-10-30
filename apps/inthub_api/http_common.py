"""Constants and small helpers the HTTP layers share."""

import logging
import os
import re
import threading
import time
from collections import deque
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from apps.inthub_api.auth import safe_return_to
from apps.inthub_api.common import APIError
from apps.inthub_api.teams import accept_invite, create_invite, create_team, delete_team, remove_member, revoke_invite, set_member_role, update_team
from apps.inthub_api.tenon import SESSION_MAX_SECONDS

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
# Paths the web app answers itself; anything else gets a real 404.
WEB_ROUTES = re.compile(r"/(?:showcase|account(?:/danger)?|settings(?:/teams|/usage)?|invite|device|teams/[^/]+(?:/projects|/settings)?)?/?")
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
