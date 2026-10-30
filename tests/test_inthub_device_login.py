"""`itt auth login` through the browser: a code in the terminal, approved by a signed-in browser."""

import sys
import threading

import pytest

from apps.inthub_api.auth import account_for_access_token, list_account_access_tokens
from apps.inthub_api.db import connect
from apps.inthub_api import device
from intent_cli.commands import auth as auth_command
from tests.test_inthub_teams import Hub, Person, request


@pytest.fixture
def hub(tmp_path):
    instance = Hub(tmp_path)
    yield instance
    instance.server.shutdown()
    instance.thread.join()
    instance.server.server_close()


def start(hub, name="itt on laptop"):
    status, body = request(hub.url + "/api/v1/auth/device/start", "POST", {"name": name})
    assert status == 200, body
    return body["result"]


def poll(hub, device_code):
    status, body = request(hub.url + "/api/v1/auth/device/poll", "POST", {"device_code": device_code})
    assert status == 200, body
    return body["result"]


def test_a_code_approved_in_the_browser_gives_the_cli_one_token(hub):
    ana = Person(hub, "ana")
    started = start(hub)
    assert started["verification_path"] == "/device" and started["expires_in"] == 600
    assert len(started["user_code"]) == 9 and started["user_code"][4] == "-"
    assert poll(hub, started["device_code"]) == {"status": "pending"}

    # Case and the hyphen do not matter, and the browser sees only the name the CLI gave.
    typed = started["user_code"].replace("-", "").lower()
    status, body = ana.post("/api/v1/auth/device/lookup", {"code": typed})
    assert status == 200 and body["result"] == {"name": "itt on laptop", "token_days": 90}
    assert ana.post("/api/v1/auth/device/decide", {"code": typed, "approve": True})[0] == 200

    result = poll(hub, started["device_code"])
    assert result["status"] == "approved"
    assert account_for_access_token(hub.db, result["token"])["id"] == ana.id
    tokens = list_account_access_tokens(hub.db, ana.id)
    assert "itt on laptop" in [token["name"] for token in tokens]
    # The token leaves once, and a used code is dead for the browser too.
    assert poll(hub, started["device_code"]) == {"status": "expired"}
    assert ana.post("/api/v1/auth/device/lookup", {"code": typed})[1]["error"]["code"] == "DEVICE_CODE_INVALID"


def test_a_refusal_reaches_the_cli_and_grants_nothing(hub):
    ana = Person(hub, "ana")
    before = len(list_account_access_tokens(hub.db, ana.id))
    started = start(hub)
    status, body = ana.post("/api/v1/auth/device/decide", {"code": started["user_code"], "approve": False})
    assert status == 200 and body["result"]["approved"] is False
    assert poll(hub, started["device_code"]) == {"status": "denied"}
    assert poll(hub, started["device_code"]) == {"status": "expired"}
    assert len(list_account_access_tokens(hub.db, ana.id)) == before


def test_only_true_approves_and_a_code_decides_once(hub):
    ana, ben = Person(hub, "ana"), Person(hub, "ben")
    started = start(hub)
    assert ana.post("/api/v1/auth/device/decide", {"code": started["user_code"], "approve": "yes"})[1]["result"]["approved"] is False
    assert ben.post("/api/v1/auth/device/decide", {"code": started["user_code"], "approve": True})[0] == 404
    assert poll(hub, started["device_code"]) == {"status": "denied"}


def test_approving_needs_the_browser_session_and_codes_expire(hub):
    ana = Person(hub, "ana")
    started = start(hub)
    # An access token is not a browser session, and a visitor has neither.
    assert request(hub.url + "/api/v1/auth/device/decide", "POST", {"code": started["user_code"], "approve": True}, ana.token)[0] in (401, 403)
    assert request(hub.url + "/api/v1/auth/device/decide", "POST", {"code": started["user_code"], "approve": True})[0] in (401, 403)
    with connect(hub.db) as conn:
        conn.execute("UPDATE device_logins SET expires_at = ?", ("2020-01-01T00:00:00+00:00",))
    assert ana.post("/api/v1/auth/device/lookup", {"code": started["user_code"]})[1]["error"]["code"] == "DEVICE_CODE_INVALID"
    assert poll(hub, started["device_code"]) == {"status": "expired"}
    with connect(hub.db) as conn:
        assert conn.execute("SELECT COUNT(*) AS total FROM device_logins").fetchone()["total"] == 0


def test_secrets_are_stored_hashed_and_names_are_cleaned(hub):
    started = start(hub, "itt\x07 on\n box" + "x" * 200)
    with connect(hub.db) as conn:
        row = conn.execute("SELECT * FROM device_logins").fetchone()
    assert started["device_code"] not in str(dict(row)) and started["user_code"] not in str(dict(row))
    assert row["name"].startswith("itt on box") and len(row["name"]) == device.NAME_MAX
    assert poll(hub, "ith_dev_wrong") == {"status": "expired"}
    assert poll(hub, None) == {"status": "expired"}


def test_guessing_codes_and_flooding_are_limited(hub):
    ana = Person(hub, "ana")
    codes = [ana.post("/api/v1/auth/device/lookup", {"code": "BCDF-GHJK"})[0] for _ in range(21)]
    assert codes[:20] == [404] * 20 and codes[20] == 429
    statuses = [request(hub.url + "/api/v1/auth/device/start", "POST", {"name": "x"})[0] for _ in range(11)]
    assert statuses[:10] == [200] * 10 and statuses[10] == 429


def test_the_cli_signs_in_with_a_code_and_stores_the_token(hub, monkeypatch, capsys):
    ana = Person(hub, "ana")
    stored = {}
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(auth_command, "_can_open_browser", lambda: False)
    monkeypatch.setattr(auth_command, "store_access_token", lambda url, token: stored.update({url: token}))
    monkeypatch.setattr(auth_command, "write_global_hub_config", lambda url: None)
    monkeypatch.setattr(auth_command, "load_access_token", lambda url: None)
    monkeypatch.setattr(auth_command, "global_api_base_url", lambda: hub.url)
    monkeypatch.delenv("INTHUB_TOKEN", raising=False)
    real_sleep = auth_command.time.sleep
    approved = threading.Event()

    def approve_during_the_wait(_seconds):
        if not approved.is_set():
            code = capsys.readouterr().err.split("enter this code:\n\n    ", 1)[1][:9]
            assert ana.post("/api/v1/auth/device/decide", {"code": code, "approve": True})[0] == 200
            approved.set()
        real_sleep(0.01)

    monkeypatch.setattr(auth_command.time, "sleep", approve_during_the_wait)
    auth_command.cmd_auth_login(type("Args", (), {"api_base_url": hub.url, "token": None})())
    assert account_for_access_token(hub.db, stored[hub.url])["id"] == ana.id


def test_the_cli_says_what_to_do_without_a_terminal(monkeypatch, capsys):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
    monkeypatch.delenv("INTHUB_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        auth_command._login_token(type("Args", (), {"token": None})(), "https://inthub.example")
    output = capsys.readouterr()
    assert "AUTH_REQUIRED" in output.out + output.err and "INTHUB_TOKEN" in output.out + output.err


def test_an_older_hub_falls_back_to_a_pasted_token(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.delenv("INTHUB_TOKEN", raising=False)
    monkeypatch.setattr(auth_command, "http_json", lambda *args, **kwargs: None)
    monkeypatch.setattr(auth_command.getpass, "getpass", lambda prompt: "ith_pat_pasted")
    assert auth_command._login_token(type("Args", (), {"token": None})(), "https://old.example") == "ith_pat_pasted"
