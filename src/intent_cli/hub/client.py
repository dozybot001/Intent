"""HTTP client helpers for IntHub API calls."""

import http.client
import json
import socket
import urllib.error
import urllib.request

from intent_cli.output import error


DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_ATTEMPTS = 2
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
RETRYABLE_HTTP_STATUSES = {408, 425, 429, 500, 502, 503, 504}


def _bounded_text(raw):
    """Keep server diagnostics useful without reflecting an unbounded response."""
    limit = 4096
    return {
        "raw": raw[:limit],
        "truncated": len(raw) > limit,
    }


def _transport_failure(method, url, exc, attempts, timeout):
    """Emit one structured failure after bounded transport retries are exhausted."""
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    timed_out = isinstance(reason, (TimeoutError, socket.timeout))
    error(
        "NETWORK_TIMEOUT" if timed_out else "NETWORK_ERROR",
        (
            f"IntHub did not respond within {timeout:g} seconds."
            if timed_out
            else f"Could not complete the IntHub request to {url}."
        ),
        details={
            "url": url,
            "reason": type(reason).__name__,
            "attempts": attempts,
            "timeout_seconds": timeout,
            "completion_unknown": method.upper() not in {"GET", "HEAD"},
        },
        suggested_fix=(
            "Check IntHub status before deciding whether to retry. The command "
            "already retried its current operation ID."
        ),
    )


def _decode_response(raw_bytes, url):
    if len(raw_bytes) > MAX_RESPONSE_BYTES:
        error(
            "SERVER_ERROR",
            "IntHub returned a response larger than the client safety limit.",
            details={"url": url, "limit_bytes": MAX_RESPONSE_BYTES},
        )
    try:
        raw = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        error(
            "SERVER_ERROR",
            "IntHub returned a response that is not valid UTF-8.",
            details={"url": url},
        )
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        error(
            "SERVER_ERROR",
            "IntHub returned invalid JSON.",
            details={"url": url, **_bounded_text(raw)},
        )
    if not isinstance(body, dict):
        error(
            "SERVER_ERROR",
            "IntHub returned a JSON value that is not an object.",
            details={"url": url, "response_type": type(body).__name__},
        )
    return body


def _decode_error_response(raw_bytes):
    """Decode an HTTP error body without masking its status with a second error."""
    if len(raw_bytes) > MAX_RESPONSE_BYTES:
        return {"response_too_large": True, "limit_bytes": MAX_RESPONSE_BYTES}
    raw = raw_bytes.decode("utf-8", errors="replace")
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        return _bounded_text(raw)
    if isinstance(body, dict):
        return body
    return {"response_type": type(body).__name__}


def http_json(
    method,
    url,
    payload=None,
    token=None,
    *,
    timeout=DEFAULT_TIMEOUT_SECONDS,
    attempts=DEFAULT_ATTEMPTS,
):
    """Perform a bounded, retryable JSON request using an operation-stable payload."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    method = method.upper()
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    body = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw_bytes = response.read(MAX_RESPONSE_BYTES + 1)
            body = _decode_response(raw_bytes, url)
            break
        except urllib.error.HTTPError as exc:
            if exc.code in RETRYABLE_HTTP_STATUSES and attempt < attempts:
                continue
            try:
                raw_bytes = exc.read(MAX_RESPONSE_BYTES + 1)
            except (OSError, http.client.HTTPException):
                raw_bytes = b""
            response = _decode_error_response(raw_bytes) if raw_bytes else {}
            error(
                "SERVER_ERROR",
                f"IntHub request failed with status {exc.code}.",
                details={
                    "url": url,
                    "status": exc.code,
                    "attempts": attempt,
                    "response": response,
                },
            )
        except urllib.error.URLError as exc:
            if attempt < attempts:
                continue
            _transport_failure(method, url, exc, attempt, timeout)
        except (TimeoutError, socket.timeout) as exc:
            if attempt < attempts:
                continue
            _transport_failure(method, url, exc, attempt, timeout)
        except (http.client.HTTPException, OSError) as exc:
            if attempt < attempts:
                continue
            _transport_failure(method, url, exc, attempt, timeout)

    if body.get("ok") is False:
        server_error = body.get("error", {})
        if not isinstance(server_error, dict):
            error(
                "SERVER_ERROR",
                "IntHub returned a malformed error object.",
                details={
                    "url": url,
                    "error_type": type(server_error).__name__,
                },
            )
        error(
            "SERVER_ERROR",
            server_error.get("message", "IntHub returned an error."),
            details=server_error,
        )

    return body.get("result", body)
