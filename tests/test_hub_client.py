import http.client
import io
import json
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from intent_cli.hub import client


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, amount=-1):
        return self.payload if amount < 0 else self.payload[:amount]


def test_http_json_retries_timeout_with_the_same_request(monkeypatch):
    calls = []

    def fake_open_request(request, timeout):
        calls.append((request, timeout))
        if len(calls) == 1:
            raise TimeoutError("temporary timeout")
        return FakeResponse(b'{"ok":true,"result":{"linked":true}}')

    monkeypatch.setattr(client, "_open_request", fake_open_request)

    result = client.http_json(
        "POST",
        "https://inthub.example/api/v1/hub/link",
        {"workspace": {"workspace_id": "wks_stable"}},
        "secret-token",
        timeout=0.1,
    )

    assert result == {"linked": True}
    assert len(calls) == 2
    assert calls[0][0] is calls[1][0]
    assert [timeout for _request, timeout in calls] == [0.1, 0.1]


def test_http_json_timeout_is_structured_and_marks_post_unknown(
    monkeypatch, capsys,
):
    def always_timeout(_request, timeout):
        raise TimeoutError(f"timed out after {timeout}")

    monkeypatch.setattr(client, "_open_request", always_timeout)

    with pytest.raises(SystemExit):
        client.http_json(
            "POST",
            "https://inthub.example/api/v1/hub/link",
            {"workspace": {"workspace_id": "wks_stable"}},
            timeout=0.01,
        )

    output = json.loads(capsys.readouterr().out)
    assert output["error"]["code"] == "NETWORK_TIMEOUT"
    assert output["error"]["details"] == {
        "url": "https://inthub.example/api/v1/hub/link",
        "reason": "TimeoutError",
        "attempts": 2,
        "timeout_seconds": 0.01,
        "completion_unknown": True,
    }


def test_http_json_normalizes_disconnect_and_non_object_json(
    monkeypatch, capsys,
):
    responses = iter([
        http.client.RemoteDisconnected("closed"),
        http.client.RemoteDisconnected("closed"),
    ])

    def disconnect(_request, timeout):
        raise next(responses)

    monkeypatch.setattr(client, "_open_request", disconnect)
    with pytest.raises(SystemExit):
        client.http_json("GET", "https://inthub.example/api/v1/projects")

    output = json.loads(capsys.readouterr().out)
    assert output["error"]["code"] == "NETWORK_ERROR"
    assert output["error"]["details"]["completion_unknown"] is False

    monkeypatch.setattr(
        client,
        "_open_request",
        lambda _request, timeout: FakeResponse(b"[]"),
    )
    with pytest.raises(SystemExit):
        client.http_json("GET", "https://inthub.example/api/v1/projects")

    output = json.loads(capsys.readouterr().out)
    assert output["error"]["code"] == "SERVER_ERROR"
    assert output["error"]["details"]["response_type"] == "list"


@contextmanager
def _running_http_server(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(
        target=lambda: server.serve_forever(poll_interval=0.01), daemon=True,
    )
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
        assert not thread.is_alive()


def test_api_redirect_does_not_send_dummy_bearer_to_second_local_server(
    monkeypatch, capsys,
):
    # The only real requests in this test remain on temporary loopback servers.
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    source_requests = []
    receiver_requests = []
    receiver_authorizations = []
    dummy_token = "dummy-local-test-token"

    class Receiver(BaseHTTPRequestHandler):
        def do_GET(self):
            receiver_requests.append(self.path)
            receiver_authorizations.append(self.headers.get("Authorization"))
            payload = b'{"ok":true,"result":{"unexpected_redirect":true}}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args):
            pass

    with _running_http_server(Receiver) as receiver:
        destination = f"http://127.0.0.1:{receiver.server_port}/capture"

        class Source(BaseHTTPRequestHandler):
            def do_GET(self):
                source_requests.append(self.headers.get("Authorization"))
                self.send_response(302)
                self.send_header("Location", destination)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *_args):
                pass

        with _running_http_server(Source) as source:
            with pytest.raises(SystemExit) as exc_info:
                client.http_json(
                    "GET", f"http://127.0.0.1:{source.server_port}/snapshot",
                    token=dummy_token, timeout=2,
                )

    output = json.loads(capsys.readouterr().out)
    assert exc_info.value.code == 1
    assert output["error"]["code"] == "SERVER_ERROR"
    assert output["error"]["details"]["status"] == 302
    assert output["error"]["details"]["attempts"] == 1
    assert source_requests == [f"Bearer {dummy_token}"]
    assert receiver_requests == []
    assert receiver_authorizations == []


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_api_redirect_handler_rejects_https_to_http_without_creating_request(status):
    request = Request(
        "https://inthub.example/api/v1/hub/snapshot",
        headers={"Authorization": "Bearer dummy-local-test-token"},
    )
    redirected = client._NoAPIRedirects().redirect_request(
        request, None, status, "Redirect", {}, "http://foreign.example/capture",
    )
    assert redirected is None


@pytest.fixture
def limited_json_integers():
    if not hasattr(sys, "set_int_max_str_digits"):
        pytest.skip("this Python does not impose a JSON integer conversion limit")
    original = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(640)
    try:
        yield
    finally:
        sys.set_int_max_str_digits(original)


def test_success_response_huge_json_integer_is_a_structured_error(
    monkeypatch, capsys, limited_json_integers,
):
    raw = b'{"ok":true,"result":{"value":' + b"9" * 10000 + b"}}"
    monkeypatch.setattr(
        client, "_open_request", lambda _request, timeout: FakeResponse(raw),
    )
    with pytest.raises(SystemExit) as exc_info:
        client.http_json("GET", "https://inthub.example/api/v1/hub/snapshot")
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exc_info.value.code == 1
    assert output["error"]["code"] == "SERVER_ERROR"
    assert captured.err == ""
    assert len(captured.out) < 10000


def test_http_error_huge_json_integer_preserves_http_status(
    monkeypatch, capsys, limited_json_integers,
):
    url = "https://inthub.example/api/v1/hub/snapshot"
    raw = b'{"error":{"value":' + b"9" * 10000 + b"}}"

    def fail_request(_request, timeout):
        raise HTTPError(url, 502, "Bad Gateway", {}, io.BytesIO(raw))

    monkeypatch.setattr(client, "_open_request", fail_request)
    with pytest.raises(SystemExit) as exc_info:
        client.http_json("GET", url, attempts=1)
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert exc_info.value.code == 1
    assert output["error"]["code"] == "SERVER_ERROR"
    assert output["error"]["details"]["status"] == 502
    assert captured.err == ""
    assert len(captured.out) < 10000


@pytest.mark.parametrize("http_status", [None, 503])
def test_json_decoder_recursion_error_stays_structured_and_preserves_http_status(
    monkeypatch, capsys, http_status,
):
    url = "https://inthub.example/api/v1/hub/snapshot"
    real_json_loads = json.loads
    raw = b'{"ok":true,"result":{}}'

    def fail_decode(_raw):
        raise RecursionError("simulated JSON decoder recursion limit")

    def open_request(_request, timeout):
        if http_status is not None:
            raise HTTPError(url, http_status, "Unavailable", {}, io.BytesIO(raw))
        return FakeResponse(raw)

    monkeypatch.setattr(client, "_open_request", open_request)
    monkeypatch.setattr(client.json, "loads", fail_decode)
    with pytest.raises(SystemExit) as exc_info:
        client.http_json("GET", url, attempts=1)
    captured = capsys.readouterr()
    output = real_json_loads(captured.out)
    assert exc_info.value.code == 1
    assert output["error"]["code"] == "SERVER_ERROR"
    if http_status is not None:
        assert output["error"]["details"]["status"] == http_status
    assert captured.err == ""


def test_http_json_retries_retryable_http_status_with_the_same_request(monkeypatch):
    calls = []

    def open_request(request, timeout):
        calls.append((request, timeout))
        if len(calls) == 1:
            raise HTTPError(request.full_url, 503, "Unavailable", {}, io.BytesIO(b""))
        return FakeResponse(b'{"ok":true,"result":{"retried":true}}')

    monkeypatch.setattr(client, "_open_request", open_request)
    result = client.http_json(
        "GET", "https://inthub.example/api/v1/hub/snapshot", timeout=0.1,
    )
    assert result == {"retried": True}
    assert len(calls) == 2
    assert calls[0][0] is calls[1][0]
    assert [timeout for _request, timeout in calls] == [0.1, 0.1]


@pytest.mark.parametrize("raw", [
    b'{"ok":false,"error":{"message":"\\ud800"}}',
    b'{"ok":true,"result":{"nested":[{"value":NaN}]}}',
    b'{"ok":true,"result":{"nested":[{"value":Infinity}]}}',
    b'{"ok":true,"result":{"nested":[{"value":-Infinity}]}}',
])
def test_success_status_invalid_unicode_or_nested_nonfinite_number_stays_utf8_json(
    monkeypatch, capsys, raw,
):
    monkeypatch.setattr(
        client, "_open_request", lambda _request, timeout: FakeResponse(raw),
    )
    with pytest.raises(SystemExit) as exc_info:
        client.http_json("GET", "https://inthub.example/api/v1/hub/snapshot")
    captured = capsys.readouterr()
    # JSON parsing alone accepts lone surrogate code points; encoding must work.
    encoded_output = captured.out.encode("utf-8")
    output = json.loads(encoded_output)
    assert exc_info.value.code == 1
    assert output["error"]["code"] == "SERVER_ERROR"
    assert output["error"]["details"]["raw"] == raw.decode("utf-8")
    assert output["error"]["details"]["truncated"] is False
    assert captured.err == ""


@pytest.mark.parametrize("invalid_value", [
    b'"\\ud800"', b"NaN", b"Infinity", b"-Infinity",
])
def test_http_error_invalid_unicode_or_nonfinite_number_keeps_status_and_bounded_raw(
    monkeypatch, capsys, invalid_value,
):
    url = "https://inthub.example/api/v1/hub/snapshot"
    raw = (
        b'{"error":{"nested":[{"value":' + invalid_value + b'}],"padding":"'
        + b"x" * 10000 + b'"}}'
    )

    def fail_request(_request, timeout):
        raise HTTPError(url, 422, "Unprocessable Content", {}, io.BytesIO(raw))

    monkeypatch.setattr(client, "_open_request", fail_request)
    with pytest.raises(SystemExit) as exc_info:
        client.http_json("GET", url, attempts=1)
    captured = capsys.readouterr()
    output = json.loads(captured.out.encode("utf-8"))
    assert exc_info.value.code == 1
    assert output["error"]["code"] == "SERVER_ERROR"
    assert output["error"]["details"]["status"] == 422
    response = output["error"]["details"]["response"]
    assert response["raw"] == raw.decode("utf-8")[:4096]
    assert response["truncated"] is True
    assert len(captured.out) < 10000
    assert captured.err == ""
