"""Account, browser-session, and GitHub OAuth helpers for IntHub."""

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from apps.inthub_api.common import APIError, new_id, now_utc
from apps.inthub_api.db import connect


GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_API_VERSION = "2022-11-28"


def _sha256(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _expires_at(seconds):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _is_expired(value):
    try:
        expires_at = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= datetime.now(timezone.utc)


def safe_return_to(value):
    """Keep post-login navigation on this IntHub deployment."""
    if not isinstance(value, str) or not value.startswith("/") or value.startswith("//"):
        return "/"
    if "\\" in value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        return "/"
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        return "/"
    return value


def create_login_attempt(db_target, return_to="/", ttl_seconds=600):
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    created_at = now_utc()
    expires_at = _expires_at(ttl_seconds)

    with connect(db_target) as conn:
        conn.execute("DELETE FROM oauth_login_attempts WHERE expires_at <= ?", (created_at,))
        conn.execute(
            """
            INSERT INTO oauth_login_attempts (
                state_hash, code_verifier, return_to, created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (_sha256(state), verifier, safe_return_to(return_to), created_at, expires_at),
        )

    return {
        "state": state,
        "code_verifier": verifier,
        "code_challenge": challenge,
        "return_to": safe_return_to(return_to),
        "expires_at": expires_at,
    }


def consume_login_attempt(db_target, state):
    if not isinstance(state, str) or not state:
        raise APIError("OAUTH_STATE_INVALID", "The sign-in attempt is invalid or expired.", 400)
    state_hash = _sha256(state)
    with connect(db_target) as conn:
        row = conn.execute(
            """
            SELECT code_verifier, return_to, expires_at
            FROM oauth_login_attempts
            WHERE state_hash = ?
            """,
            (state_hash,),
        ).fetchone()
        conn.execute("DELETE FROM oauth_login_attempts WHERE state_hash = ?", (state_hash,))

    if row is None or _is_expired(row["expires_at"]):
        raise APIError("OAUTH_STATE_INVALID", "The sign-in attempt is invalid or expired.", 400)
    return {
        "code_verifier": row["code_verifier"],
        "return_to": safe_return_to(row["return_to"]),
    }


def upsert_github_account(db_target, user):
    provider_user_id = str(user.get("id", "")).strip()
    login = str(user.get("login", "")).strip()
    if not provider_user_id or not login:
        raise APIError("OAUTH_IDENTITY_INVALID", "GitHub returned an invalid identity.", 502)

    timestamp = now_utc()
    with connect(db_target) as conn:
        existing = conn.execute(
            "SELECT id, role, created_at FROM accounts WHERE provider = ? AND provider_user_id = ?",
            ("github", provider_user_id),
        ).fetchone()
        account_id = existing["id"] if existing else new_id("acct")
        role = existing["role"] if existing else "member"
        created_at = existing["created_at"] if existing else timestamp
        conn.execute(
            """
            INSERT INTO accounts (
                id, provider, provider_user_id, login, display_name,
                avatar_url, role, created_at, updated_at, last_login_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (provider, provider_user_id) DO UPDATE SET
                login = excluded.login,
                display_name = excluded.display_name,
                avatar_url = excluded.avatar_url,
                updated_at = excluded.updated_at,
                last_login_at = excluded.last_login_at
            """,
            (
                account_id,
                "github",
                provider_user_id,
                login,
                user.get("name"),
                user.get("avatar_url"),
                role,
                created_at,
                timestamp,
                timestamp,
            ),
        )
        row = conn.execute(
            "SELECT * FROM accounts WHERE provider = ? AND provider_user_id = ?",
            ("github", provider_user_id),
        ).fetchone()
    return public_account(row)


def create_web_session(db_target, account_id, ttl_seconds=7 * 24 * 60 * 60):
    token = f"ith_ses_{secrets.token_urlsafe(32)}"
    timestamp = now_utc()
    expires_at = _expires_at(ttl_seconds)
    with connect(db_target) as conn:
        conn.execute("DELETE FROM web_sessions WHERE expires_at <= ?", (timestamp,))
        conn.execute(
            """
            INSERT INTO web_sessions (
                id, token_hash, account_id, created_at, expires_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (new_id("ses"), _sha256(token), account_id, timestamp, expires_at, timestamp),
        )
    return {"token": token, "expires_at": expires_at}


def account_for_session(db_target, token):
    if not isinstance(token, str) or not token.startswith("ith_ses_"):
        return None
    token_hash = _sha256(token)
    with connect(db_target) as conn:
        row = conn.execute(
            """
            SELECT
                a.id, a.provider, a.provider_user_id, a.login,
                a.display_name, a.avatar_url, a.role,
                a.created_at, a.updated_at, a.last_login_at,
                s.expires_at
            FROM web_sessions AS s
            JOIN accounts AS a ON a.id = s.account_id
            WHERE s.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()
        if row is not None and _is_expired(row["expires_at"]):
            conn.execute("DELETE FROM web_sessions WHERE token_hash = ?", (token_hash,))
            return None
    return public_account(row) if row is not None else None


def delete_web_session(db_target, token):
    if not isinstance(token, str) or not token:
        return
    with connect(db_target) as conn:
        conn.execute("DELETE FROM web_sessions WHERE token_hash = ?", (_sha256(token),))


def create_account_access_token(
    db_target,
    account_id,
    name="CLI",
    ttl_seconds=90 * 24 * 60 * 60,
):
    """Create an account-scoped token and return its plaintext exactly once."""
    if not isinstance(account_id, str) or not account_id:
        raise APIError("INVALID_INPUT", "An account is required.", 400)
    label = str(name or "CLI").strip()[:100] or "CLI"
    ttl_seconds = int(ttl_seconds)
    if ttl_seconds < 60 or ttl_seconds > 366 * 24 * 60 * 60:
        raise APIError(
            "INVALID_INPUT",
            "Access token lifetime must be between 60 seconds and 366 days.",
            400,
        )
    token = f"ith_pat_{secrets.token_urlsafe(32)}"
    created_at = now_utc()
    expires_at = _expires_at(ttl_seconds)
    token_id = new_id("pat")
    with connect(db_target) as conn:
        account = conn.execute("SELECT id FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if account is None:
            raise APIError("OBJECT_NOT_FOUND", "Account not found.", 404)
        conn.execute(
            """
            INSERT INTO account_access_tokens (
                id, token_hash, account_id, name, created_at,
                expires_at, last_used_at, revoked_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id,
                _sha256(token),
                account_id,
                label,
                created_at,
                expires_at,
                None,
                None,
            ),
        )
    return {
        "id": token_id,
        "token": token,
        "name": label,
        "created_at": created_at,
        "expires_at": expires_at,
    }


def account_for_access_token(db_target, token):
    if not isinstance(token, str) or not token.startswith("ith_pat_"):
        return None
    token_hash = _sha256(token)
    with connect(db_target) as conn:
        row = conn.execute(
            """
            SELECT
                a.id, a.provider, a.provider_user_id, a.login,
                a.display_name, a.avatar_url, a.role,
                a.created_at, a.updated_at, a.last_login_at,
                t.expires_at, t.revoked_at
            FROM account_access_tokens AS t
            JOIN accounts AS a ON a.id = t.account_id
            WHERE t.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()
        if row is None or row["revoked_at"] is not None or _is_expired(row["expires_at"]):
            return None
        conn.execute(
            "UPDATE account_access_tokens SET last_used_at = ? WHERE token_hash = ?",
            (now_utc(), token_hash),
        )
    return public_account(row)


def revoke_account_access_token(db_target, account_id, token_id):
    with connect(db_target) as conn:
        result = conn.execute(
            """
            UPDATE account_access_tokens
            SET revoked_at = ?
            WHERE id = ? AND account_id = ? AND revoked_at IS NULL
            """,
            (now_utc(), token_id, account_id),
        )
    if result.rowcount == 0:
        raise APIError("OBJECT_NOT_FOUND", f"Access token {token_id} not found.", 404)


def list_account_access_tokens(db_target, account_id):
    with connect(db_target) as conn:
        rows = conn.execute(
            """
            SELECT id, name, created_at, expires_at, last_used_at, revoked_at
            FROM account_access_tokens
            WHERE account_id = ?
            ORDER BY created_at DESC
            """,
            (account_id,),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "last_used_at": row["last_used_at"],
            "revoked_at": row["revoked_at"],
        }
        for row in rows
    ]


def public_account(row):
    if row is None:
        return None
    return {
        "id": row["id"],
        "provider": row["provider"],
        "provider_user_id": row["provider_user_id"],
        "login": row["login"],
        "display_name": row["display_name"],
        "avatar_url": row["avatar_url"],
        "role": row["role"],
        "created_at": row["created_at"],
        "last_login_at": row["last_login_at"],
    }


class GitHubOAuthClient:
    """Small server-side client for GitHub's OAuth web application flow."""

    def __init__(
        self,
        client_id,
        client_secret,
        authorize_url=GITHUB_AUTHORIZE_URL,
        token_url=GITHUB_TOKEN_URL,
        user_url=GITHUB_USER_URL,
        timeout=10,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorize_url = authorize_url
        self.token_url = token_url
        self.user_url = user_url
        self.timeout = timeout

    def authorization_url(self, redirect_uri, state, code_challenge):
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "allow_signup": "false",
            }
        )
        return f"{self.authorize_url}?{query}"

    def exchange_code(self, code, redirect_uri, code_verifier):
        payload = urlencode(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            }
        ).encode("utf-8")
        response = self._json_request(
            self.token_url,
            method="POST",
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        token = response.get("access_token")
        if not isinstance(token, str) or not token:
            raise APIError("OAUTH_EXCHANGE_FAILED", "GitHub sign-in could not be completed.", 502)
        return token

    def get_user(self, access_token):
        user = self._json_request(
            self.user_url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {access_token}",
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
            },
        )
        if not isinstance(user, dict):
            raise APIError("OAUTH_IDENTITY_INVALID", "GitHub returned an invalid identity.", 502)
        return user

    def _json_request(self, url, method="GET", data=None, headers=None):
        request_headers = {"User-Agent": "IntHub", **(headers or {})}
        request = Request(url, data=data, headers=request_headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise APIError("OAUTH_PROVIDER_ERROR", "GitHub sign-in is temporarily unavailable.", 502) from exc
        if not isinstance(payload, dict) or payload.get("error"):
            raise APIError("OAUTH_PROVIDER_ERROR", "GitHub sign-in is temporarily unavailable.", 502)
        return payload
