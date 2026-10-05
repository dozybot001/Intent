"""Tenon's sole OIDC entry and exact product identity mapping."""

import hashlib
import secrets
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from apps.inthub_api.auth import _expires_at, _is_expired, _sha256, public_account, safe_return_to
from apps.inthub_api.common import APIError, new_id, now_utc
from apps.inthub_api.db import connect

ISSUER = "https://account.tenon.asia/api/auth"
PLATFORM_ROLE = "https://tenon.asia/claims/platform_role"
SESSION_MAX_SECONDS = 30 * 24 * 60 * 60


def create_attempt(db_target, return_to="/", ttl_seconds=600):
    state, verifier, nonce = (secrets.token_urlsafe(48) for _ in range(3))
    with connect(db_target) as conn:
        conn.execute("DELETE FROM tenon_login_attempts WHERE expires_at <= ?", (now_utc(),))
        conn.execute(
            "INSERT INTO tenon_login_attempts(state_hash, code_verifier, nonce, return_to, expires_at, started_at) VALUES (?, ?, ?, ?, ?, ?)",
            (_sha256(state), verifier, nonce, safe_return_to(return_to), _expires_at(ttl_seconds), now_utc()),
        )
    return {"state": state, "code_verifier": verifier, "nonce": nonce}


def consume_attempt(db_target, state):
    with connect(db_target) as conn:
        # DELETE RETURNING makes consumption atomic on both supported databases.
        row = conn.execute(
            "DELETE FROM tenon_login_attempts WHERE state_hash = ? RETURNING *",
            (_sha256(state),),
        ).fetchone()
    if row is None or _is_expired(row["expires_at"]):
        raise APIError("OAUTH_STATE_INVALID", "The sign-in attempt expired. Please try again.", 400)
    return dict(row)


def _identity_lock(conn, subject):
    if conn.backend == "sqlite":
        conn.execute("BEGIN IMMEDIATE")
    else:
        key = int.from_bytes(hashlib.sha256((ISSUER + subject).encode()).digest()[:8], "big", signed=True)
        conn.execute("SELECT pg_advisory_xact_lock(?)", (key,))


def bind_existing_account(db_target, account_id, subject):
    """Operator-only migration after explicit proof of both account owners."""
    if not isinstance(subject, str) or not subject.strip() or len(subject) > 255:
        raise APIError("INVALID_INPUT", "An exact Tenon subject is required.", 400)
    with connect(db_target) as conn:
        _identity_lock(conn, subject)
        if conn.execute("SELECT id FROM accounts WHERE id = ?", (account_id,)).fetchone() is None:
            raise APIError("OBJECT_NOT_FOUND", "Account not found.", 404)
        mappings = conn.execute(
            "SELECT account_id, subject FROM account_identities WHERE issuer = ? AND (subject = ? OR account_id = ?)",
            (ISSUER, subject, account_id),
        ).fetchall()
        if any(row["account_id"] != account_id or row["subject"] != subject for row in mappings):
            raise APIError("IDENTITY_CONFLICT", "The identity is already bound to another account.", 409)
        conn.execute(
            "INSERT INTO account_identities VALUES (?, ?, ?, ?) ON CONFLICT (issuer, subject) DO NOTHING",
            (ISSUER, subject, account_id, now_utc()),
        )
    return {"bound": True}


def account_for_identity(db_target, identity, *, request_started_at=None):
    subject = identity["sub"]
    timestamp = now_utc()
    with connect(db_target) as conn:
        _identity_lock(conn, subject)
        deleted = conn.execute(
            "SELECT max(completed_at) AS completed_at FROM product_deletion_receipts WHERE issuer = ? AND subject = ?",
            (ISSUER, subject),
        ).fetchone()
        if deleted["completed_at"] is not None and (request_started_at is None or request_started_at <= deleted["completed_at"]):
            raise APIError("OAUTH_IDENTITY_RETIRED", "Start a new Tenon sign-in after account deletion.", 401)
        mapping = conn.execute(
            "SELECT account_id FROM account_identities WHERE issuer = ? AND subject = ?",
            (ISSUER, subject),
        ).fetchone()
        if mapping:
            account_id = mapping["account_id"]
        else:
            account_id = new_id("acct")
            # This is a product business record, never an independent credential.
            conn.execute(
                """INSERT INTO accounts
                    (id, provider, provider_user_id, login, display_name, avatar_url,
                     role, created_at, updated_at, last_login_at)
                    VALUES (?, 'tenon', ?, ?, ?, NULL, 'member', ?, ?, ?)""",
                (account_id, subject, subject, identity.get("name"), timestamp, timestamp, timestamp),
            )
            conn.execute("INSERT INTO account_identities VALUES (?, ?, ?, ?)",
                         (ISSUER, subject, account_id, timestamp))
        conn.execute(
            "UPDATE accounts SET display_name = COALESCE(?, display_name), updated_at = ?, last_login_at = ? WHERE id = ?",
            (identity.get("name"), timestamp, timestamp, account_id),
        )
        row = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    return public_account(row)


def create_session(db_target, account_id, identity, ttl_seconds=SESSION_MAX_SECONDS):
    ttl = min(int(ttl_seconds), SESSION_MAX_SECONDS)
    # The callback identity must still be valid when issuing the local session.
    # Its short token lifetime does not limit the independent product session.
    if ttl <= 0 or identity["expires_at"] <= time.time():
        raise APIError("OAUTH_IDENTITY_INVALID", "The identity expired.", 401)
    timestamp = now_utc()
    token, session_id = "ith_ses_" + secrets.token_urlsafe(32), new_id("ses")
    with connect(db_target) as conn:
        conn.execute("DELETE FROM web_sessions WHERE expires_at <= ?", (timestamp,))
        mapping = conn.execute(
            "SELECT account_id FROM account_identities WHERE issuer = ? AND subject = ?",
            (ISSUER, identity["sub"]),
        ).fetchone()
        if not mapping or mapping["account_id"] != account_id:
            raise APIError("IDENTITY_CONFLICT", "The identity mapping changed.", 409)
        conn.execute("INSERT INTO web_sessions VALUES (?, ?, ?, ?, ?, ?)",
                     (session_id, _sha256(token), account_id, timestamp, _expires_at(ttl), timestamp))
        conn.execute("INSERT INTO tenon_session_grants VALUES (?, ?, ?, ?, ?)",
                     (session_id, ISSUER, identity["sub"], identity["platform_role"], timestamp))
    return {"token": token, "ttl_seconds": ttl}


def account_for_session(db_target, token):
    if not isinstance(token, str) or not token.startswith("ith_ses_"):
        return None
    with connect(db_target) as conn:
        row = conn.execute(
            """SELECT a.*, s.expires_at, g.platform_role, g.verified_at
                FROM web_sessions s JOIN accounts a ON a.id = s.account_id
                JOIN tenon_session_grants g ON g.session_id = s.id
                JOIN account_identities i ON i.issuer = g.issuer AND i.subject = g.subject
                    AND i.account_id = s.account_id
                WHERE s.token_hash = ? AND g.issuer = ?""",
            (_sha256(token), ISSUER),
        ).fetchone()
    if row is None or _is_expired(row["expires_at"]):
        return None
    verified = datetime.fromisoformat(row["verified_at"]).timestamp()
    if not 0 <= time.time() - verified < SESSION_MAX_SECONDS:
        return None
    account = public_account(row)
    account["auth"] = "tenon"
    account["platform_role"] = row["platform_role"]
    if row["platform_role"] == "admin":
        account["role"] = "admin"
    return account


class TenonOIDCClient:
    """Authlib handles authorization, PKCE, JWT/JWK and OIDC claim validation."""

    def __init__(self, client_id, client_secret):
        from authlib.integrations.base_client import BaseApp, OAuth2Mixin, OpenIDMixin
        from authlib.integrations.httpx_client import OAuth2Client

        class OIDCApp(OAuth2Mixin, OpenIDMixin, BaseApp):
            client_cls = OAuth2Client

            def load_server_metadata(self):
                metadata = super().load_server_metadata()
                if metadata.get("issuer") != ISSUER:
                    raise ValueError("Unexpected OIDC issuer")
                for field in ("authorization_endpoint", "token_endpoint", "userinfo_endpoint", "jwks_uri"):
                    url = urlsplit(metadata.get(field, ""))
                    if url.scheme != "https" or url.netloc != "account.tenon.asia" or url.fragment:
                        raise ValueError("Unexpected OIDC endpoint")
                if "S256" not in metadata.get("code_challenge_methods_supported", []):
                    raise ValueError("PKCE unavailable")
                algorithms = metadata.get("id_token_signing_alg_values_supported", [])
                if not algorithms or any(alg not in {"EdDSA", "RS256", "ES256"} for alg in algorithms):
                    raise ValueError("Unexpected signing algorithm")
                return metadata

        self.app = OIDCApp(None, "tenon", client_id=client_id, client_secret=client_secret,
                           server_metadata_url=ISSUER + "/.well-known/openid-configuration",
                           client_kwargs={"scope": "openid profile email", "code_challenge_method": "S256",
                                          "token_endpoint_auth_method": "client_secret_basic", "timeout": 10})

    def authorization_url(self, redirect_uri, attempt):
        try:
            return self.app.create_authorization_url(redirect_uri, **attempt)["url"]
        except Exception as exc:
            raise APIError("OAUTH_PROVIDER_ERROR", "Tenon sign-in is temporarily unavailable.", 502) from exc

    def complete_login(self, code, redirect_uri, attempt):
        try:
            token = self.app.fetch_access_token(redirect_uri, code=code,
                                                code_verifier=attempt["code_verifier"])
            if not token.get("id_token") or not token.get("access_token"):
                raise ValueError("Missing token")
            claims = self.app.parse_id_token(token, nonce=attempt["nonce"], leeway=0)
            # Require nonce even if a provider advertises nonce_supported=false.
            if claims.get("nonce") != attempt["nonce"] or claims.get("iss") != ISSUER:
                raise ValueError("Invalid nonce or issuer")
            info = self.app.userinfo(token=token)
            role = info.get(PLATFORM_ROLE)
            if not claims.get("sub") or info.get("sub") != claims["sub"] or info.get("email_verified") is not True:
                raise ValueError("Unverified identity")
            if role not in {"admin", "user"} or claims.get(PLATFORM_ROLE) != role:
                raise ValueError("Invalid platform role")
            expiration = min(float(claims["exp"]), time.time() + float(token["expires_in"]))
            if expiration <= time.time():
                raise ValueError("Expired identity")
            name = info.get("name")
            return {"sub": claims["sub"], "platform_role": role, "expires_at": expiration,
                    "name": name.strip()[:80] if isinstance(name, str) and name.strip() else None}
        except Exception as exc:
            # Never include provider payloads, claims, tokens or secrets in the error.
            raise APIError("OAUTH_IDENTITY_INVALID", "Tenon sign-in could not be verified.", 502) from exc
