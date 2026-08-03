import http.client
import json

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

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        if len(calls) == 1:
            raise TimeoutError("temporary timeout")
        return FakeResponse(b'{"ok":true,"result":{"linked":true}}')

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

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

    monkeypatch.setattr(client.urllib.request, "urlopen", always_timeout)

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

    monkeypatch.setattr(client.urllib.request, "urlopen", disconnect)
    with pytest.raises(SystemExit):
        client.http_json("GET", "https://inthub.example/api/v1/projects")

    output = json.loads(capsys.readouterr().out)
    assert output["error"]["code"] == "NETWORK_ERROR"
    assert output["error"]["details"]["completion_unknown"] is False

    monkeypatch.setattr(
        client.urllib.request,
        "urlopen",
        lambda _request, timeout: FakeResponse(b"[]"),
    )
    with pytest.raises(SystemExit):
        client.http_json("GET", "https://inthub.example/api/v1/projects")

    output = json.loads(capsys.readouterr().out)
    assert output["error"]["code"] == "SERVER_ERROR"
    assert output["error"]["details"]["response_type"] == "list"
