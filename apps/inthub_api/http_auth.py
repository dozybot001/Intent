"""Who is asking: sessions, access tokens, device sign-in and the Tenon callback."""

import hmac
from urllib.parse import urlparse

from apps.inthub_api.access import VISITOR
from apps.inthub_api.auth import account_for_access_token, create_account_access_token, delete_web_session, list_account_access_tokens, revoke_account_access_token, safe_return_to
from apps.inthub_api.common import APIError
from apps.inthub_api.device import decide_device_login, describe_device_login, poll_device_login, start_device_login
from apps.inthub_api.tenon import account_for_identity, account_for_session, consume_attempt, create_attempt, create_session
from apps.inthub_api.http_common import AUTH_BODY_LIMIT, LOGGER, OAUTH_STATE_COOKIE, SESSION_COOKIE, _json_success, _login_error_return


class HttpAuth:
    def _bearer_account(self):
        header = self.headers.get("Authorization", "")
        scheme, separator, token = header.partition(" ")
        if not separator or scheme.lower() != "bearer":
            return None
        return account_for_access_token(self.hub.db_path, token)

    def _cookie_value(self, name):
        # Parse leniently: one malformed cookie from a sibling site must not
        # hide ours (SimpleCookie stops at the first value it cannot parse).
        for part in self.headers.get("Cookie", "").split(";"):
            key, separator, value = part.strip().partition("=")
            if separator and key == name:
                return value.strip().strip('"') or None
        return None

    def _current_account(self):
        if not self.hub.tenon_configured:
            return None
        return account_for_session(self.hub.db_path, self._cookie_value(SESSION_COOKIE))

    def _require_auth(self, allow_cookie=False):
        if not self.hub.auth_required:
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
        if self.hub.secure_cookies:
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
        delete_web_session(self.hub.db_path, self._cookie_value(SESSION_COOKIE))
        self._send_json(
            200,
            _json_success({"authenticated": False}),
            {"Set-Cookie": self._session_cookie("", 0)},
        )

    def _handle_auth_me(self):
        if not self.hub.auth_required:
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
            self.hub.db_path,
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
        if not self.hub.auth_required:
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
        account_id = self._require_browser_account()["id"] if self.hub.auth_required else None
        return account_id, self._read_json_body(limit=AUTH_BODY_LIMIT)

    def _handle_device_cli(self, path):
        # The CLI has no credentials yet: the request is all it can show.
        if not self.hub.auth_required:
            raise APIError("OBJECT_NOT_FOUND", "A hub without accounts has no sign-in.", 404)
        starting = path.endswith("/start")
        limiter = self.hub.device_start_limiter if starting else self.hub.device_poll_limiter
        if not limiter.allow(self._client_address()):
            raise APIError("RATE_LIMITED", "Too many requests. Wait a minute and try again.", 429)
        body = self._read_json_body(limit=AUTH_BODY_LIMIT)
        result = start_device_login(self.hub.db_path, body.get("name")) if starting else poll_device_login(self.hub.db_path, body.get("device_code"))
        self._send_json(200, _json_success(result))

    def _handle_device_browser(self, path):
        if not self.hub.auth_required:
            raise APIError("OBJECT_NOT_FOUND", "A hub without accounts has no sign-in.", 404)
        account_id, body = self._browser_action()
        if not self.hub.device_code_limiter.allow(account_id):
            raise APIError("RATE_LIMITED", "Too many attempts. Wait a minute and try again.", 429)
        result = (describe_device_login(self.hub.db_path, body.get("code")) if path.endswith("/lookup")
                  else decide_device_login(self.hub.db_path, body.get("code"), body.get("approve"), account_id))
        self._send_json(200, _json_success(result))

    def _handle_list_account_tokens(self):
        account = self._require_browser_account()
        self._send_json(
            200,
            _json_success(
                {"tokens": list_account_access_tokens(self.hub.db_path, account["id"])}
            ),
        )

    def _handle_revoke_account_token(self, token_id):
        account = self._require_browser_account()
        revoke_account_access_token(self.hub.db_path, account["id"], token_id)
        self._send_json(200, _json_success({"revoked": True, "id": token_id}))

    def _prepare_tenon_login(self, return_to="/"):
        self._check_origin()
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise APIError("ORIGIN_DENIED", "Start sign-in from IntHub.", 403)
        if not self.hub.sign_in_limiter.allow(self._client_address()):
            raise APIError("RATE_LIMITED", "Too many sign-in attempts. Wait a minute and try again.", 429)
        if not self.hub.tenon_configured or self.hub.provider_client is None:
            raise APIError("AUTH_FLOW_UNAVAILABLE", "Tenon sign-in is not configured.", 404)
        attempt = create_attempt(
            self.hub.db_path,
            return_to=safe_return_to(return_to),
            ttl_seconds=self.hub.oauth_state_ttl_seconds,
        )
        try:
            location = self.hub.provider_client.authorization_url(self._oauth_callback_url(), attempt)
        except Exception:
            consume_attempt(self.hub.db_path, attempt["state"])
            raise
        target = urlparse(location)
        if (target.scheme != "https" or target.netloc != "account.tenon.asia"
                or target.path != "/api/auth/oauth2/authorize" or target.fragment):
            consume_attempt(self.hub.db_path, attempt["state"])
            raise APIError("AUTH_FLOW_UNAVAILABLE", "Tenon authorization is unavailable.", 503)
        return location, self._oauth_state_cookie(attempt["state"], self.hub.oauth_state_ttl_seconds)

    def _handle_tenon_callback(self, query):
        clear_state = self._oauth_state_cookie("", 0)
        state = query.get("state", [""])[0]
        cookie_state = self._cookie_value(OAUTH_STATE_COOKIE) or ""
        if not state or not hmac.compare_digest(state, cookie_state):
            self._send_redirect("/?auth_error=invalid_state", [clear_state])
            return

        attempt = None
        try:
            attempt = consume_attempt(self.hub.db_path, state)
            if query.get("error"):
                self._send_redirect(_login_error_return(attempt["return_to"], "tenon_denied"), [clear_state])
                return
            code = query.get("code", [""])[0]
            if not code:
                raise APIError("OAUTH_CODE_MISSING", "Tenon did not return a sign-in code.", 400)
            if self.hub.provider_client is None:
                raise APIError("AUTH_FLOW_UNAVAILABLE", "Tenon sign-in is not configured.", 404)
            identity = self.hub.provider_client.complete_login(
                code,
                self._oauth_callback_url(),
                attempt,
            )
            account = account_for_identity(self.hub.db_path, identity, request_started_at=attempt.get("started_at"))
            session = create_session(
                self.hub.db_path,
                account["id"],
                identity,
                ttl_seconds=self.hub.account_session_ttl_seconds,
            )
        except APIError as exc:
            LOGGER.warning("Tenon sign-in failed: %s", exc.code)
            reason = "suspended" if exc.code == "ACCOUNT_SUSPENDED" else "tenon_failed"
            self._send_redirect(_login_error_return(attempt["return_to"] if attempt else "/", reason), [clear_state])
            return

        self._send_redirect(
            attempt["return_to"],
            [
                self._session_cookie(session["token"], session["ttl_seconds"]),
                clear_state,
            ],
        )
