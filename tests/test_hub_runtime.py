import json
from types import SimpleNamespace

import pytest

from intent_cli.commands import common as command_common
from intent_cli.commands import hub as hub_commands
from intent_cli.hub import runtime as hub_runtime


def _write_hub_config(base, config):
    base.mkdir(parents=True, exist_ok=True)
    (base / "hub.json").write_text(json.dumps(config), encoding="utf-8")


def test_hub_auth_token_precedence_is_cli_environment_then_global(monkeypatch, tmp_path):
    base = tmp_path / ".intent"
    _write_hub_config(base, {})
    monkeypatch.setattr(hub_runtime, "load_access_token", lambda _url: "stored-token")
    monkeypatch.setenv("INTHUB_TOKEN", "env-token")

    args = SimpleNamespace(token="cli-token", api_base_url="https://inthub.example")
    assert hub_runtime.hub_auth_token(base, args) == "cli-token"
    args.token = None
    assert hub_runtime.hub_auth_token(base, args) == "env-token"

    monkeypatch.delenv("INTHUB_TOKEN")
    assert hub_runtime.hub_auth_token(base, args) == "stored-token"


def test_hub_link_uses_cli_token_without_persisting_it(monkeypatch, tmp_path, capsys):
    base = tmp_path / ".intent"
    base.mkdir()
    captured = {}
    monkeypatch.delenv("INTHUB_TOKEN", raising=False)

    monkeypatch.setattr(command_common, "require_init", lambda: base)
    monkeypatch.setattr(hub_commands, "require_init", lambda: base)
    monkeypatch.setattr(
        hub_commands,
        "current_repository",
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


def test_hub_link_persists_and_reuses_pending_workspace(
    monkeypatch, tmp_path, capsys,
):
    base = tmp_path / ".intent"
    base.mkdir()
    repo = {
        "provider": "gitee",
        "repo_id": "example/demo",
        "owner": "example",
        "name": "demo",
    }
    payloads = []

    monkeypatch.setattr(command_common, "require_init", lambda: base)
    monkeypatch.setattr(hub_commands, "require_init", lambda: base)
    monkeypatch.setattr(hub_commands, "current_repository", lambda: repo)
    monkeypatch.setattr(hub_commands, "hub_auth_configured", lambda _url: True)

    def interrupted(_method, _url, payload, _token):
        payloads.append(payload)
        raise RuntimeError("response was lost")

    monkeypatch.setattr(hub_commands, "http_json", interrupted)
    args = SimpleNamespace(
        api_base_url="https://inthub.example",
        project_name=None,
        token="one-shot-token",
    )

    with pytest.raises(RuntimeError, match="response was lost"):
        hub_commands.cmd_hub_link(args)

    pending_config = json.loads((base / "hub.json").read_text(encoding="utf-8"))
    pending_id = pending_config["pending_link"]["workspace_id"]
    assert pending_id.startswith("wks_")
    assert pending_config["pending_link"]["repo_binding"] == repo
    assert "project_id" not in pending_config

    hub_commands.cmd_hub_status(SimpleNamespace(api_base_url=None))
    status = json.loads(capsys.readouterr().out)
    assert status["result"]["linked"] is False
    assert status["result"]["link_pending"] is True
    assert status["result"]["pending_link"]["workspace_id"] == pending_id

    def succeeds(_method, _url, payload, _token):
        payloads.append(payload)
        return {
            "workspace_id": payload["workspace"]["workspace_id"],
            "project_id": "proj_demo",
            "repo_binding": payload["repo"],
        }

    monkeypatch.setattr(hub_commands, "http_json", succeeds)
    hub_commands.cmd_hub_link(args)
    linked = json.loads(capsys.readouterr().out)
    persisted = json.loads((base / "hub.json").read_text(encoding="utf-8"))

    assert linked["ok"] is True
    assert [item["workspace"]["workspace_id"] for item in payloads] == [
        pending_id,
        pending_id,
    ]
    assert persisted["workspace_id"] == pending_id
    assert persisted["project_id"] == "proj_demo"
    assert "pending_link" not in persisted


def test_push_persists_and_reuses_pending_batch_for_unchanged_state(
    monkeypatch, tmp_path, capsys,
):
    base = tmp_path / ".intent"
    base.mkdir()
    _write_hub_config(base, {
        "api_base_url": "https://inthub.example",
        "workspace_id": "wks_demo",
        "project_id": "proj_demo",
        "repo_binding": {
            "provider": "github",
            "repo_id": "example/demo",
            "owner": "example",
            "name": "demo",
        },
        "last_sync_batch_id": None,
        "last_synced_at": None,
    })
    payloads = []
    state = {"revision": 1}

    monkeypatch.setattr(command_common, "require_init", lambda: base)
    monkeypatch.setattr(hub_commands, "require_init", lambda: base)
    monkeypatch.setattr(hub_commands, "hub_auth_token", lambda *_args: "token")
    monkeypatch.setattr(hub_commands, "hub_auth_configured", lambda _url: True)

    def build_payload(_base, hub, *, generated_at=None):
        return {
            "sync_batch_id": hub["sync_batch_id"],
            "generated_at": generated_at,
            "project_id": hub["project_id"],
            "repo": hub["repo_binding"],
            "workspace": {"workspace_id": hub["workspace_id"]},
            "snapshot": {
                "revision": state["revision"],
                "intents": [],
                "snaps": [],
                "decisions": [],
            },
        }

    monkeypatch.setattr(hub_commands, "build_sync_payload", build_payload)

    def interrupted(_method, _url, payload, _token):
        payloads.append(payload)
        raise RuntimeError("response was lost")

    monkeypatch.setattr(hub_commands, "http_json", interrupted)
    args = SimpleNamespace(api_base_url=None, token=None, dry_run=False)
    with pytest.raises(RuntimeError, match="response was lost"):
        hub_commands.cmd_push(args)

    pending_config = json.loads((base / "hub.json").read_text(encoding="utf-8"))
    pending_id = pending_config["pending_sync"]["sync_batch_id"]
    assert pending_id.startswith("sync_")

    hub_commands.cmd_hub_status(SimpleNamespace(api_base_url=None))
    status = json.loads(capsys.readouterr().out)
    assert status["result"]["sync_pending"] is True
    assert status["result"]["pending_sync"]["sync_batch_id"] == pending_id

    def succeeds(_method, _url, payload, _token):
        payloads.append(payload)
        return {
            "sync_batch_id": payload["sync_batch_id"],
            "project_id": payload["project_id"],
            "workspace_id": payload["workspace"]["workspace_id"],
            "accepted_at": "2026-08-03T10:00:00+00:00",
            "duplicate": True,
        }

    monkeypatch.setattr(hub_commands, "http_json", succeeds)
    hub_commands.cmd_push(args)
    pushed = json.loads(capsys.readouterr().out)
    persisted = json.loads((base / "hub.json").read_text(encoding="utf-8"))

    assert pushed["ok"] is True
    assert [payload["sync_batch_id"] for payload in payloads] == [
        pending_id,
        pending_id,
    ]
    assert persisted["last_sync_batch_id"] == pending_id
    assert "pending_sync" not in persisted

    monkeypatch.setattr(hub_commands, "http_json", interrupted)
    with pytest.raises(RuntimeError, match="response was lost"):
        hub_commands.cmd_push(args)
    changed_pending = json.loads(
        (base / "hub.json").read_text(encoding="utf-8")
    )["pending_sync"]["sync_batch_id"]

    state["revision"] = 2
    monkeypatch.setattr(hub_commands, "http_json", succeeds)
    hub_commands.cmd_push(args)
    capsys.readouterr()
    changed_persisted = json.loads(
        (base / "hub.json").read_text(encoding="utf-8")
    )

    assert payloads[-2]["sync_batch_id"] == changed_pending
    assert payloads[-1]["sync_batch_id"] != changed_pending
    assert changed_persisted["last_sync_batch_id"] == payloads[-1]["sync_batch_id"]
