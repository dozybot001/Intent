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
