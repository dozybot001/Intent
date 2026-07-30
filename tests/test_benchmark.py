import copy
import json
import os
import subprocess
import sys
from pathlib import Path

from intent_cli.benchmark.continuation import (
    build_trial_plan,
    matched_fact_rows,
    run_continuation_suite,
    semantic_graph_payload,
    write_intent_fixture,
)
from intent_cli.benchmark.harness import (
    BenchError,
    RunnerTimeout,
    build_context,
    decode_process_output,
    evaluator_read_isolation_profile,
    extract_codex_usage,
    flat_fact_rows,
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
    render_intent_context,
    run_benchmark_suite,
    score_task_repo,
)
from intent_cli.commands.core import build_inspect_result


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


def test_benchmark_renders_multiple_intents_and_deprecated_reason():
    context = {
        "intents": [
            {
                "id": "intent-001",
                "status": "active",
                "what": "Finish CSV export",
                "why": "Compliance deadline",
                "snap_ids": ["snap-001"],
                "decision_ids": ["decision-001", "decision-002"],
            },
            {
                "id": "intent-002",
                "status": "suspend",
                "what": "Explore Parquet export",
                "why": "Blocked on format approval",
                "snap_ids": ["snap-002"],
                "decision_ids": ["decision-002"],
            },
        ],
        "snaps": [],
        "decisions": [
            {
                "id": "decision-001",
                "status": "deprecated",
                "what": "Use mtime-only invalidation",
                "reason": "Network filesystems can preserve timestamps",
                "intent_ids": ["intent-001"],
            },
            {
                "id": "decision-002",
                "status": "active",
                "what": "Do not add binary dependencies",
                "why": "Deployment must stay portable",
                "intent_ids": ["intent-001", "intent-002"],
            },
        ],
    }

    rendered = "\n".join(render_intent_context(context))
    no_why = "\n".join(render_intent_context(context, "no-why"))

    assert "### Intents" in rendered
    assert "status=active" in rendered
    assert "status=suspend" in rendered
    assert "Network filesystems can preserve timestamps" in rendered
    assert "Network filesystems can preserve timestamps" not in no_why
    assert "Deployment must stay portable" not in no_why


def test_flat_fact_rows_supports_structured_ledger_without_design_notes():
    rows = flat_fact_rows({
        "repository_visible": ["A visible fact."],
        "semantic_handoff": ["A code-external fact."],
        "fairness_note": "This must never reach the model.",
    })

    assert rows == [
        ("repository_visible.001", "A visible fact."),
        ("semantic_handoff.001", "A code-external fact."),
    ]


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


def test_benchmark_oracle_can_restrict_changes_to_explicit_paths(tmp_path):
    task = copy.deepcopy(load_task("decision-stdlib-csv-001"))
    repo = tmp_path / "task"
    materialize_task(task["id"], "after_a", repo)
    (repo / "unexpected.py").write_text("SIDE_EFFECT = True\n", encoding="utf-8")
    task["oracle"]["only_paths_may_change"] = {
        "paths": ["importer.py"],
        "reason": "Only the approved implementation file is in scope.",
    }

    from intent_cli.benchmark.harness import score_repo_with_oracle

    result = score_repo_with_oracle(task, repo, "oracle")
    scope = next(check for check in result["checks"] if check["kind"] == "only_paths_may_change")

    assert scope["passed"] is False
    assert scope["unexpected_paths"] == ["unexpected.py"]


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
                "protocol": args.protocol,
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
    assert payload["result"]["protocol"] == "continuation"
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


def test_evaluator_read_isolation_allows_current_trial_and_denies_siblings(tmp_path):
    if sys.platform != "darwin":
        return
    current = tmp_path / "suite" / "trials" / "trial-0001"
    sibling = tmp_path / "suite" / "trials" / "trial-0002"
    current.mkdir(parents=True)
    sibling.mkdir(parents=True)
    (current / "allowed.txt").write_text("allowed", encoding="utf-8")
    (sibling / "denied.txt").write_text("denied", encoding="utf-8")
    profile = evaluator_read_isolation_profile(current)

    allowed = subprocess.run(
        ["sandbox-exec", "-p", profile, "/bin/cat", str(current / "allowed.txt")],
        cwd=current,
        capture_output=True,
        text=True,
    )
    denied = subprocess.run(
        ["sandbox-exec", "-p", profile, "/bin/cat", str(sibling / "denied.txt")],
        cwd=current,
        capture_output=True,
        text=True,
    )

    assert allowed.returncode == 0
    assert allowed.stdout == "allowed"
    assert denied.returncode != 0


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


def test_continuation_plan_is_seeded_paired_and_opaque():
    first = build_trial_plan(
        ["task-a", "task-b"],
        ["git-only", "flat-facts", "intent-full"],
        repeat=2,
        seed=42,
        max_pairs=2,
    )
    second = build_trial_plan(
        ["task-a", "task-b"],
        ["git-only", "flat-facts", "intent-full"],
        repeat=2,
        seed=42,
        max_pairs=2,
    )

    assert first == second
    assert first["pair_count"] == 2
    assert first["trial_count"] == 6
    assert {pair["task"] for pair in first["pairs"]} == {"task-a", "task-b"}
    assert {pair["repeat_index"] for pair in first["pairs"]} == {1}
    assert all(len(pair["trials"]) == 3 for pair in first["pairs"])
    assert all(
        trial["trial_id"].startswith("trial-")
        and trial["condition"] not in trial["trial_id"]
        for pair in first["pairs"]
        for trial in pair["trials"]
    )


def test_matched_flat_ledger_contains_every_product_graph_field(tmp_path):
    task = load_task("decision-stdlib-csv-001")
    repo = tmp_path / "repo"
    repo.mkdir()
    write_intent_fixture(repo, task["intent_context"])

    inspected = build_inspect_result(repo / ".intent", full=True)
    product_payload = {
        "intents": inspected["intents"],
        "snaps": inspected["snaps"],
        "decisions": inspected["decisions"],
    }
    expected_payload = semantic_graph_payload(task["intent_context"])

    assert product_payload == expected_payload
    assert matched_fact_rows(product_payload) == matched_fact_rows(expected_payload)

    flat_cli = build_context(task["id"], "flat-facts-matched")["content"]
    graph_cli = build_context(task["id"], "intent-full")["content"]
    assert "Condition:" not in flat_cli
    assert "Condition:" not in graph_cli
    assert task["id"] not in flat_cli
    assert task["id"] not in graph_cli


def test_continuation_suite_reuses_checkpoint_and_runs_only_session_b(tmp_path):
    suite_dir = tmp_path / "continuation"
    masked_states = []

    def masked_runner(phase, repo, instructions, run_dir):
        state = json.loads((Path(run_dir) / "run.json").read_text(encoding="utf-8"))
        manifest_text = (Path(run_dir).parents[1] / "manifest.json").read_text(encoding="utf-8")
        assert state["task_id"].startswith("task-")
        assert state["condition"].startswith("treatment-")
        assert "bug-cli-config-cache-001" not in manifest_text
        assert "intent-full" not in manifest_text
        masked_states.append((state["task_id"], state["condition"]))
        return _fake_runner(phase, repo, instructions, run_dir)

    report = run_continuation_suite(
        suite_dir,
        tasks=["bug-cli-config-cache-001"],
        conditions=["no-history", "intent-full"],
        runner="fake",
        model="gpt-test",
        reasoning_effort="low",
        seed=7,
        runner_func=masked_runner,
    )

    assert report["protocol"] == "continuation-only"
    assert report["errors"] == []
    assert report["completed_trials"] == 2
    assert report["planned_trials"] == 2
    assert report["cumulative_input_tokens"] == 200
    assert len(masked_states) == 2
    assert len(report["runs"]) == 2
    assert all(row["final_ok"] is True for row in report["runs"])
    assert {row["pair_id"] for row in report["runs"]} == {
        "pair-0001"
    }
    assert len({row["checkpoint_sha256"] for row in report["runs"]}) == 1
    assert all(row["session_a_elapsed_seconds"] == 0.0 for row in report["runs"])
    assert all(row["session_b_input_tokens"] == 100 for row in report["runs"])

    rows = {row["condition"]: row for row in report["runs"]}
    no_history_run = Path(rows["no-history"]["run"])
    intent_run = Path(rows["intent-full"]["run"])
    assert not (no_history_run / "session-b" / "repo" / ".intent").exists()
    assert not (intent_run / "session-b" / "repo" / ".intent").exists()

    for row in report["runs"]:
        context = (Path(row["run"]) / "session-b" / "context.md").read_text(encoding="utf-8")
        assert "Condition:" not in context
    intent_context = (intent_run / "session-b" / "context.md").read_text(encoding="utf-8")
    assert '"intents"' in intent_context
    assert '"mode"' not in intent_context

    manifest = json.loads((suite_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "intent-benchmark-suite-v2"
    assert manifest["protocol"] == "continuation-only"
    assert manifest["reasoning_effort"] == "low"
    assert manifest["completed_trials"] == 2
    assert manifest["checkpoints"]["bug-cli-config-cache-001"]["checkpoint_score"]["ok"] is True
    assert manifest["checkpoints"]["bug-cli-config-cache-001"]["semantic_fact_count"] > 0


def test_continuation_timeout_is_a_paired_task_failure_not_exclusion(tmp_path):
    calls = 0

    def timeout_then_finish(phase, repo, instructions, run_dir):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RunnerTimeout("fixed budget exceeded")
        return _fake_runner(phase, repo, instructions, run_dir)

    report = run_continuation_suite(
        tmp_path / "continuation-timeout",
        tasks=["bug-cli-config-cache-001"],
        conditions=["no-history", "intent-full"],
        runner="fake",
        model="gpt-test",
        reasoning_effort="low",
        runner_func=timeout_then_finish,
    )

    assert report["errors"] == []
    assert report["invalid_pair_count"] == 0
    assert report["missing_planned_trial_count"] == 0
    assert report["attempted_trials"] == 2
    assert report["completed_trials"] == 2
    assert len(report["task_failures"]) == 1
    assert sorted(row["final_ok"] for row in report["runs"]) == [False, True]
    comparison = report["statistics"]["pairing"]["comparisons"][0]
    assert comparison["complete_pairs"] == 1


def test_continuation_infrastructure_error_invalidates_whole_pair(tmp_path):
    def broken_runner(**_kwargs):
        raise BenchError("provider unavailable")

    report = run_continuation_suite(
        tmp_path / "continuation-infra",
        tasks=["bug-cli-config-cache-001"],
        conditions=["no-history", "intent-full"],
        runner="fake",
        model="gpt-test",
        reasoning_effort="low",
        runner_func=broken_runner,
    )

    assert report["invalid_pair_count"] == 1
    assert report["invalid_pair_ids"] == ["pair-0001"]
    assert report["missing_planned_trial_count"] == 0
    assert all(row["pair_valid"] is False for row in report["runs"])
    assert report["summary"] == []
    assert report["statistics"]["row_count"] == 0


def _fake_runner(phase, repo, instructions, run_dir):
    state = json.loads((Path(run_dir) / "run.json").read_text(encoding="utf-8"))
    task_id = state["task_id"]
    if state.get("protocol") == "continuation-only" and task_id.startswith("task-"):
        if (Path(repo) / "settings.py").is_file():
            task_id = "bug-cli-config-cache-001"
        else:
            raise AssertionError("Unknown frozen continuation fixture")
    task = load_task(task_id)
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
