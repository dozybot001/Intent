"""How a request is read and an answer sent, and the static web app."""

import json
import mimetypes
from pathlib import Path
from urllib.parse import quote, urlparse

from apps.inthub_api.common import APIError
from apps.inthub_web import product_version
from apps.inthub_api.http_common import WEB_ROUTES


class HttpBase:
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
        if (request_origin and self.hub.origin_allowlist is not None
                and request_origin.rstrip("/") in self.hub.origin_allowlist):
            self.send_header("Access-Control-Allow-Origin", request_origin)
            self.send_header("Vary", "Origin")
        header_items = (extra_headers or {}).items() if hasattr(extra_headers or {}, "items") else extra_headers
        for name, value in header_items:
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _request_base_url(self):
        if self.hub.public_api_base_url:
            return self.hub.public_api_base_url.rstrip("/")
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

    def _send_file(self, path, status=200):
        body = path.read_bytes()
        # Asset URLs carry the release, so a new one reaches every browser at once.
        if path.suffix in {".html", ".css"}:
            body = body.replace(b"__REV__", quote(product_version()).encode("ascii"))
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {
            "application/javascript",
            "application/json",
        }:
            content_type = f"{content_type}; charset=utf-8"
        cache_control = "no-cache" if path.suffix == ".html" else "public, max-age=3600"
        self._send_bytes(status, body, content_type, cache_control=cache_control)

    def _serve_index(self):
        self._send_file(self.hub.root / "index.html")

    def _serve_web(self, path):
        if path == "/auth/redirect":
            self._send_file(self.hub.root / "auth-redirect.html")
            return True
        if path == "/config.json":
            self._send_json(
                200,
                {
                    "apiBaseUrl": self._request_base_url(),
                    "defaultProjectId": self.hub.default_project_id,
                    "authRequired": self.hub.auth_required,
                    "authMode": self.hub.auth_mode,
                    "productVersion": product_version(),
                },
            )
            return True

        if WEB_ROUTES.fullmatch(path):
            self._serve_index()
            return True
        if path == "/favicon.ico":
            self._send_redirect("/tenon-mark.svg")
            return True
        if path == "/.well-known/security.txt":
            self._send_file(self.hub.root / "security.txt")
            return True
        if not Path(path).suffix and not path.startswith("/api/"):
            self._send_file(self.hub.root / "404.html", status=404)
            return True

        candidate = (self.hub.root / path.lstrip("/")).resolve()
        try:
            candidate.relative_to(self.hub.root)
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
        if host and (urlparse(f"//{host}").hostname or "") not in self.hub.allowed_hosts:
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
        allowed = origin in self.hub.origin_allowlist if self.hub.origin_allowlist is not None else self._same_origin(origin)
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
        limit = self.hub.max_body_bytes if limit is None else min(limit, self.hub.max_body_bytes)
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

    def _check_rate(self):
        if self.hub.auth_required and not self.hub.api_limiter.allow(self._client_address()):
            raise APIError("RATE_LIMITED", "Too many requests. Wait a minute and try again.", 429)
