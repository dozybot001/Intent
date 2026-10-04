"""Pull end-to-end tests against an isolated real API and checkout pair."""

import copy
import json
import os
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from apps.inthub_api.server import make_handler
from intent_cli.commands import pull
from intent_cli.hub.snapshots import SnapshotError, require_fast_forward, snapshot_sha256, validate_snapshot

ROOT = Path(__file__).resolve().parents[1]


def run(repo, *args):
    env = dict(os.environ, PYTHONPATH=f"{ROOT / 'src'}{os.pathsep}{ROOT}",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
               INTENT_CONFIG_HOME=str(repo.parent / "isolated-config"))
    env.pop("INTHUB_TOKEN", None)
    process = subprocess.run([sys.executable, "-m", "intent_cli", *args],
                             cwd=repo, env=env, capture_output=True, text=True)
    body = json.loads(process.stdout)
    assert process.returncode == (0 if body["ok"] else 1), process.stderr
    return body


def checkout(path):
    path.mkdir()
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "remote", "add", "origin", "https://gitee.com/example/demo.git"], check=True)
    assert run(path, "init")["ok"]
    return path


def semantic_bytes(repo):
    return {str(p.relative_to(repo)): p.read_bytes() for p in (repo / ".intent").rglob("*")
            if p.is_file() and p.name != ".write.lock"}


@pytest.fixture
def pair(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(str(tmp_path / "hub.db")))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        source, target = checkout(tmp_path / "source"), checkout(tmp_path / "target")
        url = f"http://127.0.0.1:{server.server_port}"
        linked = run(source, "hub", "link", "--api-base-url", url)
        assert linked["ok"]
        assert run(source, "intent", "create", "修复重试", "--why", "避免重复")['ok']
        assert run(source, "snap", "create", "已验证重试；Boundary: 部署待完成；Next: 部署；Blocker: none", "--intent", "intent-001")['ok']
        assert run(source, "push")['ok']
        yield source, target, url, linked["result"]["workspace_id"]
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_pull_restores_then_repeats_without_writes_and_links_separately(pair):
    source, target, url, source_id = pair
    result = run(target, "pull", "--api-base-url", url)
    assert result["ok"] and result["result"]["changed"]
    assert result["result"]["source_workspace_id"] == source_id
    assert result["result"]["linked"] is False
    assert run(target, "inspect")["active_intents"] == run(source, "inspect")["active_intents"]
    before = semantic_bytes(target)
    assert run(target, "pull")["result"]["changed"] is False
    assert semantic_bytes(target) == before
    linked = run(target, "hub", "link")
    assert linked["ok"] and linked["result"]["workspace_id"] != source_id
    assert linked["result"]["pull_source"]["workspace_id"] == source_id
    assert run(target, "push")["ok"]
    assert run(target, "pull")["ok"]


def test_pull_fast_forward_and_terminal_objects(pair):
    source, target, url, _ = pair
    assert run(target, "pull", "--api-base-url", url)["ok"]
    assert run(source, "snap", "create", "部署验证通过", "--intent", "intent-001")["ok"]
    assert run(source, "intent", "done", "intent-001")["ok"]
    assert run(source, "decision", "create", "本地数据保持私有")["ok"]
    assert run(source, "decision", "deprecate", "decision-001", "--reason", "改用其他规则")["ok"]
    assert run(source, "push")["ok"]
    result = run(target, "pull")
    assert result["ok"] and result["result"]["counts"] == {"intents": 1, "snaps": 2, "decisions": 1}
    assert json.loads((target / ".intent/intents/intent-001.json").read_text())["status"] == "done"
    assert json.loads((target / ".intent/decisions/decision-001.json").read_text())["status"] == "deprecated"
    assert run(target, "doctor")["result"]["healthy"]


def test_pull_inherits_github_history_without_changing_gitee_identity(pair):
    source, target, url, _ = pair
    github = "https://github.com/example/demo.git"
    subprocess.run(["git", "-C", str(source), "remote", "set-url", "origin", github], check=True)
    (source / ".intent/hub.json").unlink()  # Set up an independently linked GitHub source.
    linked = run(source, "hub", "link", "--api-base-url", url)
    assert linked["ok"]
    assert run(source, "push")["ok"]
    result = run(target, "pull", "--api-base-url", url, "--source-repo", github)
    assert result["ok"] and result["result"]["changed"]
    assert run(target, "inspect")["active_intents"] == run(source, "inspect")["active_intents"]
    assert subprocess.check_output(["git", "-C", str(target), "remote", "get-url", "origin"], text=True).strip() == "https://gitee.com/example/demo.git"
    assert run(target, "hub", "link")["ok"]
    assert run(target, "push")["ok"]
    assert run(target, "pull")["ok"]
    assert run(source, "snap", "create", "new source checkpoint", "--intent", "intent-001")["ok"]
    assert run(source, "push")["ok"]
    assert run(target, "pull")["result"]["counts"]["snaps"] == 2
    before = semantic_bytes(target)
    switched = run(target, "pull", "--source-repo", "https://gitee.com/example/demo.git")
    assert switched["error"]["code"] == "PULL_SOURCE_MISMATCH"
    assert semantic_bytes(target) == before
    assert run(target, "push")["ok"]
    switched = run(target, "pull", "--source-repo", "https://gitee.com/example/demo.git")
    assert switched["ok"] and not switched["result"]["changed"]
    assert switched["result"]["source_workspace_id"] != linked["result"]["workspace_id"]
    assert run(target, "pull")["ok"]


def test_pull_local_changes_noop_if_remote_unchanged_then_refuses_divergence(pair):
    source, target, url, _ = pair
    assert run(target, "pull", "--api-base-url", url)["ok"]
    assert run(target, "snap", "create", "本地验证进展", "--intent", "intent-001")["ok"]
    before = semantic_bytes(target)
    result = run(target, "pull")
    assert result["ok"] and not result["result"]["changed"] and result["result"]["local_changes"]
    assert semantic_bytes(target) == before
    assert run(source, "snap", "create", "源端的不同进展", "--intent", "intent-001")["ok"]
    assert run(source, "push")["ok"]
    result = run(target, "pull")
    assert result["error"]["code"] == "LOCAL_CHANGES"
    assert semantic_bytes(target) == before


def test_pull_dry_run_and_uninitialized_fail_without_side_effects(pair, tmp_path):
    _, target, url, _ = pair
    before = semantic_bytes(target)
    result = run(target, "pull", "--api-base-url", url, "--dry-run")
    assert result["ok"] and result["result"]["changed"]
    assert semantic_bytes(target) == before
    raw = tmp_path / "raw"
    raw.mkdir()
    subprocess.run(["git", "init", str(raw)], check=True, capture_output=True)
    assert run(raw, "pull")["error"]["code"] == "NOT_INITIALIZED"
    assert not (raw / ".intent").exists()


def test_pull_unknown_baseline_refuses_and_pending_push_blocks(pair):
    _, target, url, _ = pair
    assert run(target, "intent", "create", "独立本地目标")["ok"]
    before = semantic_bytes(target)
    assert run(target, "pull", "--api-base-url", url)["error"]["code"] == "LOCAL_HISTORY_CONFLICT"
    assert semantic_bytes(target) == before
    (target / ".intent/hub.json").write_text(json.dumps({"pending_sync": {
        "sync_batch_id": "sync_pending", "generated_at": "now", "payload_sha256": "0" * 64,
    }}))
    before = semantic_bytes(target)
    assert run(target, "pull", "--api-base-url", url)["error"]["code"] == "HUB_OPERATION_PENDING"
    assert semantic_bytes(target) == before


def test_pull_multiple_workspaces_requires_choice(pair):
    source, target, url, source_id = pair
    assert run(target, "hub", "link", "--api-base-url", url)["ok"]
    assert run(target, "push")["ok"]
    hub = target / ".intent/hub.json"
    hub.unlink()  # Test setup: a new, empty checkout with no selected source.
    before = semantic_bytes(target)
    result = run(target, "pull", "--api-base-url", url)
    assert result["error"]["details"]["response"]["error"]["code"] == "WORKSPACE_REQUIRED"
    assert semantic_bytes(target) == before
    assert run(target, "pull", "--api-base-url", url, "--workspace", source_id)["ok"]


def test_snapshot_validation_duplicate_path_schema_and_graph(pair):
    source, _, _, _ = pair
    snapshot = {kind: [json.loads(p.read_text()) for p in (source / ".intent" / kind).glob("*.json")]
                for kind in ("intents", "snaps", "decisions")}
    validate_snapshot(snapshot)
    for mutate in (
        lambda s: s["snaps"].append(copy.deepcopy(s["snaps"][0])),
        lambda s: s["intents"][0].update(id="../outside"),
        lambda s: s["snaps"][0].pop("what"),
        lambda s: s["intents"][0].update(snap_ids=[]),
        lambda s: s["intents"][0].update(status="unknown"),
        lambda s: s["snaps"][0].update(what="\ud800"),
        lambda s: s["snaps"][0].update(extra=float("nan")),
    ):
        broken = copy.deepcopy(snapshot)
        mutate(broken)
        with pytest.raises(SnapshotError):
            validate_snapshot(broken)
    rewritten = copy.deepcopy(snapshot)
    rewritten["snaps"][0]["what"] = "rewritten"
    with pytest.raises(SnapshotError):
        require_fast_forward(snapshot, rewritten)
    reordered = copy.deepcopy(snapshot)
    for values in reordered.values():
        values.reverse()
    assert snapshot_sha256(snapshot) == snapshot_sha256(reordered)


def test_pull_download_race_and_invalid_identity_leave_local_untouched(pair, monkeypatch, capsys):
    source, target, url, _ = pair
    monkeypatch.chdir(target)
    monkeypatch.setenv("INTENT_CONFIG_HOME", str(target.parent / "isolated-config"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("INTHUB_TOKEN", raising=False)
    from intent_cli.hub.client import http_json
    result = http_json("GET", f"{url}/api/v1/hub/snapshot?provider=gitee&repo_id=example/demo")
    before = semantic_bytes(target)
    args = SimpleNamespace(workspace=None, api_base_url=url, token=None, dry_run=False)
    broken = copy.deepcopy(result)
    broken["repo_binding"]["repo_id"] = "another/repo"
    monkeypatch.setattr(pull, "http_json", lambda *_a, **_kw: broken)
    with pytest.raises(SystemExit):
        pull.cmd_pull(args)
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "INVALID_REMOTE_SNAPSHOT"
    assert semantic_bytes(target) == before

    def raced(*_args, **_kwargs):
        assert run(target, "intent", "create", "并发的新本地目标")["ok"]
        return result
    monkeypatch.setattr(pull, "http_json", raced)
    with pytest.raises(SystemExit):
        pull.cmd_pull(args)
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "LOCAL_STATE_CHANGED"
    assert not (target / ".intent/hub.json").exists()
    assert run(target, "doctor")["result"]["healthy"]


@pytest.mark.parametrize("config", [
    {"repo_binding": ["gitee", "example/demo"]},
    {"repo_binding": {"provider": [], "repo_id": "example/demo"}},
    {"api_base_url": 123},
    {"workspace_id": []},
    {"pull_source": {"workspace_id": "wks_source", "sync_batch_id": "sync_one",
                     "sequence_id": 0, "snapshot_sha256": "0" * 64}},
])
def test_pull_invalid_config_is_json_and_does_not_change_history(pair, config):
    _, target, url, _ = pair
    (target / ".intent/hub.json").write_text(json.dumps(config))
    before = semantic_bytes(target)
    result = run(target, "pull", "--api-base-url", url)
    assert result["error"]["code"] == "HUB_STATE_INVALID"
    assert semantic_bytes(target) == before


def test_pull_remote_rewind_and_same_revision_replacement_are_refused(pair, monkeypatch, capsys):
    _, target, url, _ = pair
    assert run(target, "pull", "--api-base-url", url)["ok"]
    monkeypatch.chdir(target)
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("INTENT_CONFIG_HOME", str(target.parent / "isolated-config"))
    monkeypatch.delenv("INTHUB_TOKEN", raising=False)
    from intent_cli.hub.client import http_json
    result = http_json("GET", f"{url}/api/v1/hub/snapshot?provider=gitee&repo_id=example/demo")
    args = SimpleNamespace(workspace=None, api_base_url=url, token=None, dry_run=False)
    hub = target / ".intent/hub.json"
    config = json.loads(hub.read_text())
    config["pull_source"]["sequence_id"] = result["batch"]["sequence_id"] + 1
    hub.write_text(json.dumps(config))
    before = semantic_bytes(target)
    monkeypatch.setattr(pull, "http_json", lambda *_a, **_kw: result)
    with pytest.raises(SystemExit):
        pull.cmd_pull(args)
    assert json.loads(capsys.readouterr().out)["error"]["code"] == "REMOTE_HISTORY_REWOUND"
    assert semantic_bytes(target) == before

    config["pull_source"]["sequence_id"] = result["batch"]["sequence_id"]
    hub.write_text(json.dumps(config))
    before = semantic_bytes(target)
    for field, value in (("sync_batch_id", "sync_replaced"), ("sequence_id", result["batch"]["sequence_id"] + 1),
                         ("snapshot", None)):
        changed = copy.deepcopy(result)
        if field == "snapshot":
            changed["snapshot"]["snaps"][0]["what"] = "Rewritten checkpoint"
        else:
            changed["batch"][field] = value
        monkeypatch.setattr(pull, "http_json", lambda *_a, **_kw: changed)
        with pytest.raises(SystemExit):
            pull.cmd_pull(args)
        assert json.loads(capsys.readouterr().out)["error"]["code"] == "REMOTE_HISTORY_CONFLICT"
        assert semantic_bytes(target) == before
