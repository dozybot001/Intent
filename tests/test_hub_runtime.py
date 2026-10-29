import json
from types import SimpleNamespace

from intent_cli.commands import shared
from intent_cli.hub import runtime


def test_hub_auth_token_precedence_is_cli_environment_then_global(monkeypatch, tmp_path):
    base = tmp_path / ".intent"
    base.mkdir()
    monkeypatch.setattr(runtime, "load_access_token", lambda _url: "stored-token")
    monkeypatch.setenv("INTHUB_TOKEN", "env-token")
    args = SimpleNamespace(token="cli-token", api_base_url="https://inthub.example")
    assert runtime.hub_auth_token(base, args) == "cli-token"
    args.token = None
    assert runtime.hub_auth_token(base, args) == "env-token"
    monkeypatch.delenv("INTHUB_TOKEN")
    assert runtime.hub_auth_token(base, args) == "stored-token"


def test_shared_link_never_persists_or_exposes_cli_token(monkeypatch, tmp_path, capsys):
    base = tmp_path / ".intent"
    for directory in ("intents", "snaps", "decisions"):
        (base / directory).mkdir(parents=True)
    captured = {}
    monkeypatch.setattr(shared, "require_init", lambda: base)
    def http(method, url, payload, token):
        captured["token"] = token
        return {"format_version": 2, "project_id": "proj_demo", "project_name": payload["project_name"]}
    monkeypatch.setattr(shared, "http_json", http)
    shared.cmd_link(SimpleNamespace(api_base_url="http://127.0.0.1:7210", project_name="Demo", token="one-shot-token"))
    output = capsys.readouterr().out
    persisted = (base / "hub.json").read_text()
    assert captured["token"] == "one-shot-token"
    assert "one-shot-token" not in output + persisted
    assert "workspace_id" not in persisted
    assert json.loads(output)["ok"]


def test_unscoped_tokens_only_go_where_the_user_pointed(monkeypatch, tmp_path, capsys):
    base = tmp_path / ".intent"
    base.mkdir()
    monkeypatch.setattr(runtime, "global_api_base_url", lambda: "https://inthub.tenon.asia")
    monkeypatch.setattr(runtime, "load_access_token", lambda url: f"stored-for-{url}")
    monkeypatch.setenv("INTHUB_TOKEN", "env-token")
    no_flag = SimpleNamespace(token=None, api_base_url=None)
    # A shared .intent/hub.json naming some other server must not receive it.
    import pytest
    with pytest.raises(SystemExit):
        runtime.hub_auth_token(base, no_flag, "https://collector.example")
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "TOKEN_ENDPOINT_MISMATCH"
    explicit = SimpleNamespace(token=None, api_base_url="https://collector.example")
    assert runtime.hub_auth_token(base, explicit, "https://collector.example") == "env-token"
    assert runtime.hub_auth_token(base, no_flag, "https://inthub.tenon.asia") == "env-token"
    assert runtime.hub_auth_token(base, no_flag, "http://127.0.0.1:7210") == "env-token"
    monkeypatch.delenv("INTHUB_TOKEN")
    # Credential-helper tokens are stored per endpoint and need no extra scoping.
    assert runtime.hub_auth_token(base, no_flag, "https://collector.example") == "stored-for-https://collector.example"


def test_remote_hubs_require_https():
    import pytest
    from intent_cli.hub.credentials import GlobalHubConfigError, normalize_api_base_url

    assert normalize_api_base_url("http://localhost:7210/") == "http://localhost:7210"
    assert normalize_api_base_url("http://[::1]:7210") == "http://[::1]:7210"
    with pytest.raises(GlobalHubConfigError):
        normalize_api_base_url("http://inthub.example")


def test_status_without_a_remote_never_contacts_a_server(monkeypatch, tmp_path, capsys):
    base = tmp_path / "project" / ".intent"
    for directory in ("intents", "snaps", "decisions"):
        (base / directory).mkdir(parents=True)
    monkeypatch.setattr(shared, "require_init", lambda: base)

    def network(*_args, **_kwargs):
        raise AssertionError("status contacted a server without a configured remote")

    monkeypatch.setattr(shared, "http_json", network)
    shared.cmd_status(SimpleNamespace(local=False, project=None, api_base_url=None, token=None))
    result = json.loads(capsys.readouterr().out)["result"]
    assert result["remote_checked"] is False and result["remote_configured"] is False
