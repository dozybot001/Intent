import json
from types import SimpleNamespace

from intent_cli.commands import common as command_common
from intent_cli.commands import hub as hub_commands
from intent_cli.hub.runtime import hub_auth_token


def _write_hub_config(base, config):
    base.mkdir(parents=True, exist_ok=True)
    (base / "hub.json").write_text(json.dumps(config), encoding="utf-8")


def test_hub_auth_token_uses_only_cli_or_environment(monkeypatch, tmp_path):
    base = tmp_path / ".intent"
    _write_hub_config(base, {})
    monkeypatch.setenv("INTHUB_TOKEN", "env-token")

    assert hub_auth_token(base, SimpleNamespace(token="cli-token")) == "cli-token"
    assert hub_auth_token(base, SimpleNamespace(token=None)) == "env-token"
    assert hub_auth_token(base, SimpleNamespace(token=None)) == "env-token"

    monkeypatch.delenv("INTHUB_TOKEN")
    assert hub_auth_token(base, SimpleNamespace(token=None)) is None


def test_hub_link_uses_cli_token_without_persisting_it(monkeypatch, tmp_path, capsys):
    base = tmp_path / ".intent"
    base.mkdir()
    captured = {}
    monkeypatch.delenv("INTHUB_TOKEN", raising=False)

    monkeypatch.setattr(command_common, "require_init", lambda: base)
    monkeypatch.setattr(hub_commands, "require_init", lambda: base)
    monkeypatch.setattr(
        hub_commands,
        "current_github_repo",
        lambda: {
            "provider": "github",
            "repo_id": "example/demo",
            "owner": "example",
            "name": "demo",
        },
    )

    def fake_http_json(method, url, payload, token):
        captured.update(method=method, url=url, payload=payload, token=token)
        return {
            "workspace_id": payload["workspace"]["workspace_id"],
            "project_id": "proj_demo",
            "repo_binding": payload["repo"],
        }

    monkeypatch.setattr(hub_commands, "http_json", fake_http_json)

    hub_commands.cmd_hub_link(SimpleNamespace(
        api_base_url="http://127.0.0.1:7210",
        project_name="Demo",
        token="one-shot-token",
    ))

    persisted = json.loads((base / "hub.json").read_text(encoding="utf-8"))
    output = json.loads(capsys.readouterr().out)
    assert captured["token"] == "one-shot-token"
    assert "auth_token" not in persisted
    assert output["result"]["auth_configured"] is False
