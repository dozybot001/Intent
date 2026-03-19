"""HTTP client helpers for IntHub API calls."""

import json
import urllib.error
import urllib.request

from intent_cli.output import error


def http_json(method, url, payload=None, token=None):
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw}
        error(
            "SERVER_ERROR",
            f"IntHub request failed with status {exc.code}.",
            details={"url": url, "response": body},
        )
    except urllib.error.URLError as exc:
        error(
            "NETWORK_ERROR",
            f"Could not reach IntHub at {url}.",
            details={"reason": str(exc.reason)},
            suggested_fix="Check the API base URL or start the IntHub API server.",
        )

    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        error(
            "SERVER_ERROR",
            "IntHub returned invalid JSON.",
            details={"url": url, "raw": raw},
        )

    if body.get("ok") is False:
        server_error = body.get("error", {})
        error(
            "SERVER_ERROR",
            server_error.get("message", "IntHub returned an error."),
            details=server_error,
        )

    return body.get("result", body)
