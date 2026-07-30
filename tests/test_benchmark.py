import json
import os
import subprocess
import sys
from pathlib import Path

from intent_cli.benchmark.harness import (
    BenchError,
    build_context,
    decode_process_output,
    extract_codex_usage,
    list_task_rows,
    live_begin,
    live_checkpoint,
    live_handoff,
    live_report,
    live_score,
    live_start,
    load_task,
    materialize_task,
    minimal_codex_config_text,
    prepare_clean_codex_home,
    run_benchmark_suite,
    score_task_repo,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATHS = [str(REPO_ROOT), str(REPO_ROOT / "src")]


def _run_cli(*args):
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        SOURCE_PATHS + ([existing] if existing else [])
    )
    return subprocess.run(
        [sys.executable, "-m", "intent_cli", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )


def test_benchmark_lists_generic_tasks():
    rows = list_task_rows()
    ids = {row["id"] for row in rows}
    assert "bug-cli-config-cache-001" in ids
    assert "feature-rest-pagination-001" in ids
    assert "decision-stdlib-csv-001" in ids


def test_benchmark_context_ablation_removes_decision_object():
    result = build_context(
        "bug-cli-config-cache-001",
        "intent-full",
        ablation="no-decision",
    )

    content = result["content"]
    assert "### Intent" in content
    assert "### Snaps" in content
    assert "### Decisions" not in content
    assert "decision_ids" not in content


def test_benchmark_materialize_and_score(tmp_path):
    repo = tmp_path / "task"
    materialize_task("decision-stdlib-csv-001", "after_a", repo)

    initial = score_task_repo("decision-stdlib-csv-001", repo)
    assert initial["ok"] is False

    (repo / "importer.py").write_text(
        "import csv\n"
        "from io import StringIO\n\n"
        "def parse_rows(text):\n"
        "    rows = []\n"
        "    for name, score in csv.reader(StringIO(text)):\n"
        "        rows.append({\"name\": name, \"score\": int(score)})\n"
        "    return rows\n",
        encoding="utf-8",
    )
    final = score_task_repo("decision-stdlib-csv-001", repo)
    assert final["ok"] is True
    assert final["score"] == final["total"]


def test_benchmark_hidden_tests_reject_string_only_fake(tmp_path):
    repo = tmp_path / "task"
    materialize_task("decision-stdlib-csv-001", "after_a", repo)
    (repo / "importer.py").write_text(
        "# import csv\n\n"
        "def parse_rows(text):\n"
        "    return []\n",
        encoding="utf-8",
    )

    result = score_task_repo("decision-stdlib-csv-001", repo)

    assert result["ok"] is False
    hidden = next(check for check in result["checks"] if check["kind"] == "hidden_tests")
    assert hidden["passed"] is False


def test_benchmark_cli_list_returns_json():
    result = _run_cli("benchmark", "list")
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["action"] == "benchmark.list"
    assert payload["result"]["tasks"]


def test_benchmark_cli_live_start_returns_json(tmp_path):
    result = _run_cli(
        "benchmark",
        "live",
        "start",
        "--task",
        "bug-cli-config-cache-001",
        "--condition",
        "git-only",
        "--out",
        str(tmp_path / "run"),
    )
    payload = json.loads(result.stdout)

    assert payload["ok"] is True
    assert payload["action"] == "benchmark.live.start"
    assert payload["result"]["status"] == "started"

    task = load_task("bug-cli-config-cache-001")
    instructions = (tmp_path / "run" / "session-a" / "instructions.md").read_text(encoding="utf-8")
    assert task["session_a"]["checkpoint_goal"] in instructions
    assert "Do not implement any later fix" in instructions


def test_benchmark_cli_default_dispatches_run(monkeypatch, capsys, tmp_path):
    import intent_cli.cli as cli

    def fake_run(args):
        print(json.dumps({
            "ok": True,
            "action": "benchmark.run",
            "result": {
                "out": args.out,
                "conditions": args.conditions,
                "reasoning_effort": args.reasoning_effort,
            },
            "warnings": [],
        }))

    monkeypatch.setattr(cli, "cmd_benchmark_run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "itt",
            "benchmark",
            "--out",
            str(tmp_path / "runs"),
            "--conditions",
            "git-only,intent-full",
        ],
    )

    cli.main()
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is True
    assert payload["action"] == "benchmark.run"
    assert payload["result"]["conditions"] == "git-only,intent-full"
    assert payload["result"]["reasoning_effort"] == "low"


def test_benchmark_session_b_goal_does_not_leak_decision_constraint():
    task = load_task("decision-stdlib-csv-001")
    assert "dependenc" not in task["session_b"]["goal"].lower()

    context = build_context("decision-stdlib-csv-001", "no-history")["content"]
    assert "without adding runtime dependencies" not in context


def test_benchmark_decode_timeout_output_accepts_bytes():
    assert decode_process_output(b"hello\xc3\xa9") == "helloé"
    assert decode_process_output(None) == ""
    assert decode_process_output("already text") == "already text"


def test_benchmark_extracts_codex_usage_from_jsonl():
    events = "\n".join([
        json.dumps({"type": "thread.started"}),
        json.dumps({
            "type": "turn.completed",
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 60,
                "output_tokens": 20,
                "reasoning_output_tokens": 3,
            },
        }),
        "not-json",
        json.dumps({
            "type": "turn.completed",
            "usage": {
                "input_tokens": 50,
                "cached_input_tokens": 40,
                "output_tokens": 10,
                "reasoning_output_tokens": 2,
            },
        }),
    ])

    assert extract_codex_usage(events) == {
        "input_tokens": 150,
        "cached_input_tokens": 100,
        "output_tokens": 30,
        "reasoning_output_tokens": 5,
    }


def test_benchmark_minimal_codex_config_removes_global_state():
    source = """
model_provider = "custom"
model = "gpt-5.5"
model_reasoning_effort = "xhigh"
notify = ["/tmp/notify"]

[model_providers.custom]
name = "My Codex"
base_url = "https://example.test/v1"
wire_api = "responses"
requires_openai_auth = true

[mcp_servers.node_repl]
command = "node_repl"

[projects."/tmp/project"]
trust_level = "trusted"
"""

    minimal = minimal_codex_config_text(source)

    assert 'model_provider = "custom"' in minimal
    assert '[model_providers.custom]' in minimal
    assert "base_url" in minimal
    assert 'approval_policy = "never"' in minimal
    assert 'sandbox_mode = "workspace-write"' in minimal
    assert "notify" not in minimal
    assert "mcp_servers" not in minimal
    assert "projects." not in minimal


def test_benchmark_prepare_clean_codex_home_copies_only_auth_and_minimal_config(tmp_path, monkeypatch):
    source_codex_home = tmp_path / "source-codex"
    source_codex_home.mkdir()
    (source_codex_home / "auth.json").write_text('{"auth_mode":"apikey"}', encoding="utf-8")
    (source_codex_home / "AGENTS.md").write_text("global pollution", encoding="utf-8")
    (source_codex_home / "skills").mkdir()
    (source_codex_home / "config.toml").write_text(
        'model_provider = "openai"\n'
        'notify = ["/tmp/notify"]\n\n'
        '[model_providers.openai]\n'
        'name = "OpenAI"\n'
        'base_url = "https://api.openai.com/v1"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(source_codex_home))

    clean = prepare_clean_codex_home(tmp_path / "phase")
    codex_home = clean["codex_home"]

    assert clean["home"] == tmp_path / "phase" / "runner-home"
    assert (codex_home / "auth.json").is_file()
    assert (codex_home / "config.toml").is_file()
    assert not (codex_home / "AGENTS.md").exists()
    assert not (codex_home / "skills").exists()
    assert "notify" not in (codex_home / "config.toml").read_text(encoding="utf-8")


def test_benchmark_score_requires_existing_repo(tmp_path):
    missing = tmp_path / "missing"
    try:
        score_task_repo("bug-cli-config-cache-001", missing)
    except BenchError as exc:
        assert "Repository directory not found" in str(exc)
    else:
        raise AssertionError("Expected BenchError for missing repo")


def test_benchmark_live_flow_scores_and_reports(tmp_path):
    run = tmp_path / "run-git"
    state = live_start("bug-cli-config-cache-001", "git-only", run)
    assert state["status"] == "started"
    assert (run / "session-a" / "instructions.md").is_file()

    live_begin(run, "a")
    task = load_task("bug-cli-config-cache-001")
    session_a_repo = run / "session-a" / "repo"
    for rel_path, content in task["session_a"]["changes"].items():
        path = session_a_repo / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    checkpoint = live_checkpoint(run)
    assert checkpoint["scores"]["checkpoint"]["ok"] is True

    handoff = live_handoff(run)
    assert handoff["status"] == "handoff_ready"
    assert handoff["metrics"]["handoff_chars"] > 0
    assert (run / "session-b" / "context.md").is_file()

    live_begin(run, "b")
    (run / "session-b" / "repo" / "settings.py").write_text(
        "import json\n"
        "from pathlib import Path\n\n"
        "_cache = {}\n\n\n"
        "def load_settings(path):\n"
        "    p = Path(path)\n"
        "    key = str(p)\n"
        "    mtime = p.stat().st_mtime_ns\n"
        "    cached = _cache.get(key)\n"
        "    if cached is None or cached[0] != mtime:\n"
        "        _cache[key] = (mtime, json.loads(p.read_text(encoding=\"utf-8\")))\n"
        "    return _cache[key][1]\n",
        encoding="utf-8",
    )

    final = live_score(run)
    assert final["status"] == "done"
    assert final["scores"]["final"]["ok"] is True
    assert final["metrics"]["session_b_elapsed_seconds"] is not None
    assert final["metrics"]["total_elapsed_seconds"] is not None

    report = live_report(tmp_path)
    assert report["runs"][0]["final_ok"] is True
    assert report["summary"][0]["condition"] == "git-only"
    assert report["summary"][0]["success_rate"] == 1.0


def test_benchmark_suite_runs_fake_two_session_trials(tmp_path):
    suite_dir = tmp_path / "runs"
    report = run_benchmark_suite(
        suite_dir,
        tasks=["bug-cli-config-cache-001"],
        conditions=["no-history", "chat-summary", "intent-full", "full-transcript"],
        runner="fake",
        reasoning_effort="low",
        runner_func=_fake_runner,
    )

    assert report["runner"] == "fake"
    assert report["reasoning_effort"] == "low"
    assert report["errors"] == []
    assert len(report["runs"]) == 4
    assert all(row["final_ok"] is True for row in report["runs"])
    assert report["out"] == str(suite_dir)
    assert report["manifest_path"] == str(suite_dir / "manifest.json")
    assert report["report_path"] == str(suite_dir / "report.json")
    assert report["tasks_dir"] == str(suite_dir / "tasks")
    assert report["trials_dir"] == str(suite_dir / "trials")
    assert (suite_dir / "tasks" / "bug-cli-config-cache-001.json").is_file()
    assert all("/trials/" in row["run"] for row in report["runs"])

    table = {row["condition"]: row for row in report["table"]}
    assert table["no-history"]["success"] == "100%"
    assert table["chat-summary"]["handoff_chars"] is not None
    assert table["intent-full"]["b_time"] is not None
    assert table["full-transcript"]["success"] == "100%"
    assert table["no-history"]["input_tokens"] == 200
    assert table["no-history"]["reasoning_output_tokens"] == 2

    manifest = json.loads((suite_dir / "manifest.json").read_text(encoding="utf-8"))
    saved_report = json.loads((suite_dir / "report.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "intent-benchmark-suite-v1"
    assert manifest["status"] == "completed"
    assert manifest["runner_isolation"] == "injected-runner"
    assert manifest["reasoning_effort"] == "low"
    assert manifest["tasks"] == ["bug-cli-config-cache-001"]
    assert manifest["conditions"] == ["no-history", "chat-summary", "intent-full", "full-transcript"]
    assert saved_report["table"] == report["table"]


def _fake_runner(phase, repo, instructions, run_dir):
    state = json.loads((Path(run_dir) / "run.json").read_text(encoding="utf-8"))
    task = load_task(state["task_id"])
    assert Path(instructions).is_file()

    if phase == "a":
        for rel_path, content in task["session_a"]["changes"].items():
            path = Path(repo) / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        _fake_handoff_artifacts(Path(repo), task, state["condition"])
    elif phase == "b":
        _fake_finish_task(Path(repo), task["id"])
    else:
        raise AssertionError(f"Unexpected benchmark phase: {phase}")
    return {
        "input_tokens": 100,
        "cached_input_tokens": 80,
        "output_tokens": 10,
        "reasoning_output_tokens": 1,
    }


def _fake_handoff_artifacts(repo, task, condition):
    benchmark_dir = repo / ".benchmark"
    if condition == "chat-summary":
        benchmark_dir.mkdir(parents=True, exist_ok=True)
        (benchmark_dir / "handoff-summary.md").write_text(
            task["session_a"]["chat_summary"],
            encoding="utf-8",
        )
    elif condition == "full-transcript":
        benchmark_dir.mkdir(parents=True, exist_ok=True)
        (benchmark_dir / "transcript.md").write_text(
            task["session_a"]["transcript"],
            encoding="utf-8",
        )
    elif condition == "intent-full":
        _fake_intent_context(repo, task["intent_context"])


def _fake_intent_context(repo, context):
    base = repo / ".intent"
    (base / "intents").mkdir(parents=True, exist_ok=True)
    (base / "snaps").mkdir(parents=True, exist_ok=True)
    (base / "decisions").mkdir(parents=True, exist_ok=True)

    intent = context["intent"]
    (base / "intents" / f"{intent['id']}.json").write_text(
        json.dumps(intent, indent=2),
        encoding="utf-8",
    )
    for snap in context["snaps"]:
        (base / "snaps" / f"{snap['id']}.json").write_text(
            json.dumps(snap, indent=2),
            encoding="utf-8",
        )
    for decision in context["decisions"]:
        (base / "decisions" / f"{decision['id']}.json").write_text(
            json.dumps(decision, indent=2),
            encoding="utf-8",
        )


def _fake_finish_task(repo, task_id):
    if task_id == "bug-cli-config-cache-001":
        (repo / "settings.py").write_text(
            "import json\n"
            "from pathlib import Path\n\n"
            "_cache = {}\n\n\n"
            "def load_settings(path):\n"
            "    p = Path(path)\n"
            "    key = str(p)\n"
            "    mtime = p.stat().st_mtime_ns\n"
            "    cached = _cache.get(key)\n"
            "    if cached is None or cached[0] != mtime:\n"
            "        _cache[key] = (mtime, json.loads(p.read_text(encoding=\"utf-8\")))\n"
            "    return _cache[key][1]\n",
            encoding="utf-8",
        )
        return
    raise AssertionError(f"Unsupported fake benchmark task: {task_id}")
