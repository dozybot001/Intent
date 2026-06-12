"""Generic benchmark harness for Intent evaluation.

The harness does not call any model provider. It prepares reproducible task
repositories, renders context packets for Session B, and scores completed
repositories against task oracles.
"""

import difflib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from intent_cli import __version__


ROOT = Path(__file__).resolve().parent
TASK_DIR = ROOT / "tasks"
BENCHMARK_DATA_DIR = Path(".itt-benchmark")

CONDITIONS = {
    "no-history",
    "git-only",
    "chat-summary",
    "full-transcript",
    "intent-full",
}

ABLATIONS = {
    "no-intent",
    "no-snap",
    "no-decision",
    "no-why",
    "no-status",
    "no-relations",
}

DEFAULT_CONDITIONS = [
    "no-history",
    "git-only",
    "chat-summary",
    "intent-full",
    "full-transcript",
]

DEFAULT_TASKS = ["bug-cli-config-cache-001"]

TERMINAL_FAILURE_STATUSES = {"checkpoint_failed", "failed", "error"}


class BenchError(Exception):
    """User-facing benchmark error."""


def load_tasks():
    """Load all task specs, sorted by ID."""
    tasks = []
    for path in sorted(TASK_DIR.glob("*.json")):
        task = json.loads(path.read_text(encoding="utf-8"))
        task["_path"] = str(path)
        validate_task(task)
        tasks.append(task)
    return sorted(tasks, key=lambda t: t["id"])


def load_task(task_id):
    """Load one task by ID."""
    for task in load_tasks():
        if task["id"] == task_id:
            return task
    raise BenchError(f"Task not found: {task_id}")


def list_task_rows():
    """Return compact task metadata for CLI JSON output."""
    return [
        {
            "id": task["id"],
            "type": task["type"],
            "description": task["description"],
        }
        for task in load_tasks()
    ]


def materialize_task(task_id, stage, out_dir, force=False):
    """Materialize a task stage and return a JSON-serializable result."""
    task = load_task(task_id)
    out = materialize(task, stage, out_dir, force=force)
    return {
        "task": task["id"],
        "stage": stage,
        "out": str(out),
    }


def build_context(task_id, condition, ablation=None, out_path=None):
    """Build a context packet and optionally write it to disk."""
    task = load_task(task_id)
    text = render_context(task, condition, ablation)
    result = {
        "task": task["id"],
        "condition": condition,
        "ablation": ablation or "",
    }
    if out_path:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        result["out"] = str(path)
    else:
        result["content"] = text
    return result


def score_task_repo(task_id, repo_dir):
    """Score a completed repo for a task and return a result object."""
    task = load_task(task_id)
    result = score_repo_with_oracle(task, repo_dir, "oracle")
    result["task"] = task["id"]
    result["repo"] = str(Path(repo_dir))
    return result


def default_benchmark_out_dir():
    """Return the default output directory for one automated benchmark suite."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    return BENCHMARK_DATA_DIR / "runs" / f"run-{stamp}"


def run_benchmark_suite(
    out_dir=None,
    *,
    tasks=None,
    conditions=None,
    repeat=1,
    runner="codex",
    model=None,
    force=False,
    timeout=None,
    runner_func=None,
):
    """Run an automated live benchmark suite and return the aggregate report."""
    task_ids = tasks or DEFAULT_TASKS
    condition_names = conditions or DEFAULT_CONDITIONS
    if repeat < 1:
        raise BenchError("repeat must be >= 1")
    if runner != "codex" and runner_func is None:
        raise BenchError(f"Unsupported runner: {runner}")
    loaded_tasks = [load_task(task_id) for task_id in task_ids]
    for condition in condition_names:
        _validate_context(condition)

    root = Path(out_dir) if out_dir else default_benchmark_out_dir()
    if root.exists():
        if not force:
            raise BenchError(f"Benchmark output already exists: {root}. Use --force to replace it.")
        if root.is_dir():
            shutil.rmtree(root)
        else:
            root.unlink()
    root.mkdir(parents=True, exist_ok=True)
    trials_dir = root / "trials"
    trials_dir.mkdir(parents=True, exist_ok=True)

    snapshot_task_specs(loaded_tasks, root / "tasks")
    runner_isolation = "clean-home" if runner == "codex" and runner_func is None else "injected-runner"
    manifest = build_suite_manifest(
        root,
        task_ids=[task["id"] for task in loaded_tasks],
        conditions=condition_names,
        repeat=repeat,
        runner=runner,
        runner_isolation=runner_isolation,
        model=model,
        timeout=timeout,
    )
    write_json(root / "manifest.json", manifest)

    errors = []
    for task in loaded_tasks:
        task_id = task["id"]
        for condition in condition_names:
            for index in range(1, repeat + 1):
                run_name = f"{task_id}__{condition}__r{index:02d}"
                run_dir = trials_dir / run_name
                try:
                    run_single_live_benchmark(
                        task_id,
                        condition,
                        run_dir,
                        runner=runner,
                        model=model,
                        timeout=timeout,
                        runner_func=runner_func,
                    )
                except BenchError as exc:
                    mark_live_error(run_dir, str(exc))
                    errors.append({
                        "run": str(run_dir),
                        "task": task_id,
                        "condition": condition,
                        "error": str(exc),
                    })

    report = live_report(root)
    report["out"] = str(root)
    report["runner"] = runner
    report["errors"] = errors
    report["manifest_path"] = str(root / "manifest.json")
    report["report_path"] = str(root / "report.json")
    report["tasks_dir"] = str(root / "tasks")
    report["trials_dir"] = str(trials_dir)
    manifest["completed_at"] = now_utc()
    manifest["status"] = "completed_with_errors" if errors else "completed"
    write_json(root / "manifest.json", manifest)
    write_json(root / "report.json", report)
    return report


def build_suite_manifest(root, *, task_ids, conditions, repeat, runner, runner_isolation, model, timeout):
    """Build the reproducibility manifest for one benchmark suite."""
    return {
        "schema": "intent-benchmark-suite-v1",
        "run_id": Path(root).name,
        "created_at": now_utc(),
        "status": "running",
        "intent_cli_version": __version__,
        "python": sys.version.split()[0],
        "runner": runner,
        "runner_isolation": runner_isolation,
        "model": model,
        "timeout": timeout,
        "tasks": list(task_ids),
        "conditions": list(conditions),
        "repeat": repeat,
        "paths": {
            "root": str(root),
            "tasks": str(Path(root) / "tasks"),
            "trials": str(Path(root) / "trials"),
            "manifest": str(Path(root) / "manifest.json"),
            "report": str(Path(root) / "report.json"),
        },
    }


def snapshot_task_specs(tasks, out_dir):
    """Copy the exact task specs used by a suite into its data directory."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        source = Path(task["_path"])
        (out / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def write_json(path, payload):
    """Write stable JSON for benchmark data artifacts."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def run_single_live_benchmark(
    task_id,
    condition,
    run_dir,
    *,
    runner="codex",
    model=None,
    timeout=None,
    runner_func=None,
):
    """Run one automated two-session benchmark trial."""
    live_start(task_id, condition, run_dir)
    run, state = read_live_state(run_dir)

    live_begin(run, "a")
    invoke_runner(
        runner,
        phase="a",
        repo=Path(state["paths"]["session_a_repo"]),
        instructions=Path(state["paths"]["session_a_instructions"]),
        run_dir=run,
        model=model,
        timeout=timeout,
        runner_func=runner_func,
    )
    checkpoint = live_checkpoint(run)
    if not checkpoint["scores"]["checkpoint"]["ok"]:
        return checkpoint

    live_handoff(run)
    _run, state = read_live_state(run)
    live_begin(run, "b")
    invoke_runner(
        runner,
        phase="b",
        repo=Path(state["paths"]["session_b_repo"]),
        instructions=Path(state["paths"]["session_b_instructions"]),
        run_dir=run,
        model=model,
        timeout=timeout,
        runner_func=runner_func,
    )
    return live_score(run)


def invoke_runner(
    runner,
    *,
    phase,
    repo,
    instructions,
    run_dir,
    model=None,
    timeout=None,
    runner_func=None,
):
    """Invoke an agent runner for one phase."""
    if runner_func is not None:
        runner_func(phase=phase, repo=repo, instructions=instructions, run_dir=run_dir)
        return
    if runner == "codex":
        run_codex_phase(phase, repo, instructions, run_dir, model=model, timeout=timeout)
        return
    raise BenchError(f"Unsupported runner: {runner}")


def run_codex_phase(phase, repo, instructions, run_dir, model=None, timeout=None):
    """Run Codex CLI non-interactively for one benchmark phase."""
    phase_dir = Path(run_dir) / f"session-{phase}"
    phase_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = phase_dir / "codex-events.jsonl"
    stderr_path = phase_dir / "codex-stderr.txt"
    last_message_path = phase_dir / "codex-last-message.md"

    cmd = [
        "codex",
        "exec",
        "-c",
        "shell_environment_policy.inherit=all",
        "--cd",
        str(repo),
        "--sandbox",
        "workspace-write",
        "--ephemeral",
        "--json",
        "--output-last-message",
        str(last_message_path),
        "--ignore-rules",
    ]
    if model:
        cmd.extend(["--model", model])
    cmd.append("-")

    prompt = Path(instructions).read_text(encoding="utf-8")
    try:
        with tempfile.TemporaryDirectory(prefix="intent-benchmark-codex-") as clean_root:
            env = benchmark_runner_env(Path(clean_root))
            result = subprocess.run(
                cmd,
                input=prompt,
                text=True,
                capture_output=True,
                timeout=timeout,
                env=env,
            )
    except FileNotFoundError as exc:
        raise BenchError("Codex CLI not found. Install Codex or use another runner.") from exc
    except subprocess.TimeoutExpired as exc:
        stdout_path.write_text(decode_process_output(exc.stdout), encoding="utf-8")
        stderr_path.write_text(decode_process_output(exc.stderr), encoding="utf-8")
        raise BenchError(f"Codex runner timed out in phase {phase}.") from exc

    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0:
        raise BenchError(
            f"Codex runner failed in phase {phase} with exit code {result.returncode}. See {stderr_path}"
        )


def decode_process_output(value):
    """Normalize subprocess output captured as either text or bytes."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def benchmark_runner_env(phase_dir):
    """Build a clean runner environment for one Codex phase."""
    clean_home = prepare_clean_codex_home(phase_dir)
    env = minimal_process_env()
    package_root = str(ROOT.parents[1])
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        [package_root] + ([existing] if existing else [])
    )
    env["HOME"] = str(clean_home["home"])
    env["CODEX_HOME"] = str(clean_home["codex_home"])
    return env


def minimal_process_env():
    """Keep only environment needed to launch Codex and run local Python code."""
    keep = {
        "PATH",
        "PYTHONPATH",
        "LANG",
        "LC_ALL",
        "SSL_CERT_FILE",
        "REQUESTS_CA_BUNDLE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "no_proxy",
    }
    return {key: value for key, value in os.environ.items() if key in keep}


def prepare_clean_codex_home(phase_dir):
    """Create a per-phase clean HOME/CODEX_HOME with auth and minimal config only."""
    phase_dir = Path(phase_dir)
    home = phase_dir / "runner-home"
    codex_home = home / ".codex"
    codex_home.mkdir(parents=True, exist_ok=True)

    source_codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    source_auth = source_codex_home / "auth.json"
    if not source_auth.is_file():
        raise BenchError(f"Codex auth not found: {source_auth}")
    shutil.copy2(source_auth, codex_home / "auth.json")

    source_config = source_codex_home / "config.toml"
    minimal_config = minimal_codex_config_text(
        source_config.read_text(encoding="utf-8") if source_config.is_file() else ""
    )
    (codex_home / "config.toml").write_text(minimal_config, encoding="utf-8")
    return {"home": home, "codex_home": codex_home}


def minimal_codex_config_text(source):
    """Return config needed for model/provider auth, without global agent state."""
    top_level = extract_top_level_config(
        source,
        {
            "model_provider",
            "model",
            "model_reasoning_effort",
            "disable_response_storage",
            "service_tier",
        },
    )
    provider = parse_toml_string_value(top_level.get("model_provider", ""))
    provider_section = extract_toml_section(source, f"model_providers.{provider}") if provider else []
    lines = []
    lines.extend(top_level.values())
    lines.extend([
        'approval_policy = "never"',
        'sandbox_mode = "workspace-write"',
        "",
    ])
    if provider_section:
        lines.extend(provider_section)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def extract_top_level_config(source, allowed_keys):
    """Extract selected top-level TOML assignments before the first section."""
    result = {}
    for raw_line in source.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("["):
            break
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in allowed_keys:
            result[key] = stripped
    return result


def extract_toml_section(source, section_name):
    """Extract one TOML section by exact header name."""
    header = f"[{section_name}]"
    lines = []
    in_section = False
    for raw_line in source.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_section:
                break
            in_section = stripped == header
        if in_section:
            lines.append(raw_line.rstrip())
    return lines


def parse_toml_string_value(line):
    """Parse the simple quoted string values used by Codex config keys."""
    if not line or "=" not in line:
        return ""
    value = line.split("=", 1)[1].strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1]
    return value


def intent_cli_command():
    """Return a command prefix that works from an installed package or source checkout."""
    return f"{shlex.quote(sys.executable)} -m intent_cli"


def live_start(task_id, condition, out_dir, ablation=None, force=False):
    """Create a live two-session benchmark run directory."""
    task = load_task(task_id)
    _validate_context(condition, ablation)
    run = Path(out_dir)
    if run.exists():
        if not force:
            raise BenchError(f"Run directory already exists: {run}. Use --force to replace it.")
        if run.is_dir():
            shutil.rmtree(run)
        else:
            run.unlink()

    session_a_repo = run / "session-a" / "repo"
    materialize(task, "base", session_a_repo)
    init_git_repo(session_a_repo)
    state = {
        "schema": "intent-benchmark-live-v1",
        "task_id": task["id"],
        "condition": condition,
        "ablation": ablation or "",
        "status": "started",
        "created_at": now_utc(),
        "paths": {
            "session_a_repo": str(session_a_repo),
            "session_a_instructions": str(run / "session-a" / "instructions.md"),
            "session_b_repo": str(run / "session-b" / "repo"),
            "session_b_context": str(run / "session-b" / "context.md"),
            "session_b_instructions": str(run / "session-b" / "instructions.md"),
        },
        "events": {},
        "scores": {},
    }
    write_live_state(run, state)
    write_live_session_a_instructions(run, task, state)
    return public_live_state(run, state)


def live_begin(run_dir, phase):
    """Record the beginning of Session A or Session B."""
    run, state = read_live_state(run_dir)
    if phase not in {"a", "b"}:
        raise BenchError(f"Unsupported live phase: {phase}")
    key = f"session_{phase}_started_at"
    state["events"][key] = now_utc()
    write_live_state(run, state)
    return public_live_state(run, state)


def live_checkpoint(run_dir):
    """Score Session A checkpoint and record elapsed time."""
    run, state = read_live_state(run_dir)
    task = load_task(state["task_id"])
    repo = Path(state["paths"]["session_a_repo"])
    result = score_repo_with_oracle(task, repo, "checkpoint_oracle")
    now = now_utc()
    state["events"]["checkpoint_at"] = now
    state["scores"]["checkpoint"] = result
    started = state["events"].get("session_a_started_at")
    if started:
        state["metrics"] = state.get("metrics", {})
        state["metrics"]["session_a_elapsed_seconds"] = elapsed_seconds(started, now)
    state["status"] = "checkpointed" if result["ok"] else "checkpoint_failed"
    write_live_state(run, state)
    return public_live_state(run, state)


def live_handoff(run_dir):
    """Create Session B repo and context from a completed Session A."""
    run, state = read_live_state(run_dir)
    task = load_task(state["task_id"])
    started = monotonic_now()

    session_a_repo = Path(state["paths"]["session_a_repo"])
    session_b_repo = Path(state["paths"]["session_b_repo"])
    if session_b_repo.exists():
        shutil.rmtree(session_b_repo)
    shutil.copytree(session_a_repo, session_b_repo)

    context = render_live_context(task, state, session_a_repo)
    context_path = Path(state["paths"]["session_b_context"])
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(context, encoding="utf-8")
    write_live_session_b_instructions(run, task, state)

    now = now_utc()
    state["events"]["handoff_at"] = now
    state["metrics"] = state.get("metrics", {})
    state["metrics"]["handoff_elapsed_seconds"] = monotonic_now() - started
    state["metrics"]["handoff_chars"] = len(context)
    state["status"] = "handoff_ready"
    write_live_state(run, state)
    return public_live_state(run, state)


def live_score(run_dir):
    """Score Session B final repo and record elapsed time."""
    run, state = read_live_state(run_dir)
    task = load_task(state["task_id"])
    repo = Path(state["paths"]["session_b_repo"])
    result = score_repo_with_oracle(task, repo, "oracle")
    now = now_utc()
    state["events"]["final_score_at"] = now
    state["scores"]["final"] = result
    started = state["events"].get("session_b_started_at")
    if started:
        state["metrics"] = state.get("metrics", {})
        state["metrics"]["session_b_elapsed_seconds"] = elapsed_seconds(started, now)
    metrics = state.get("metrics", {})
    total_parts = [
        metrics.get("session_a_elapsed_seconds"),
        metrics.get("handoff_elapsed_seconds"),
        metrics.get("session_b_elapsed_seconds"),
    ]
    if all(part is not None for part in total_parts):
        metrics["total_elapsed_seconds"] = sum(total_parts)
    state["status"] = "done" if result["ok"] else "failed"
    write_live_state(run, state)
    return public_live_state(run, state)


def live_report(runs_dir):
    """Aggregate live benchmark runs under a directory."""
    root = Path(runs_dir)
    rows = []
    for path in live_run_state_paths(root):
        state = json.loads(path.read_text(encoding="utf-8"))
        metrics = state.get("metrics", {})
        final = state.get("scores", {}).get("final", {})
        checkpoint = state.get("scores", {}).get("checkpoint", {})
        final_ok = final.get("ok")
        if final_ok is None and state.get("status") in TERMINAL_FAILURE_STATUSES:
            final_ok = False
        rows.append({
            "run": str(path.parent),
            "task": state.get("task_id", ""),
            "condition": state.get("condition", ""),
            "ablation": state.get("ablation", ""),
            "status": state.get("status", ""),
            "error": state.get("error"),
            "checkpoint_ok": checkpoint.get("ok"),
            "final_ok": final_ok,
            "final_score": final.get("score"),
            "final_total": final.get("total"),
            "session_a_elapsed_seconds": metrics.get("session_a_elapsed_seconds"),
            "handoff_elapsed_seconds": metrics.get("handoff_elapsed_seconds"),
            "handoff_chars": metrics.get("handoff_chars"),
            "repeated_investigation": metrics.get("repeated_investigation"),
            "violations": metrics.get("violations"),
            "session_b_elapsed_seconds": metrics.get("session_b_elapsed_seconds"),
            "total_elapsed_seconds": metrics.get("total_elapsed_seconds"),
        })
    summary = summarize_live_rows(rows)
    return {
        "runs": rows,
        "summary": summary,
        "table": summary_table(summary),
    }


def live_run_state_paths(root):
    """Return run.json files from the suite layout or legacy live layout."""
    root = Path(root)
    trials = root / "trials"
    scan_root = trials if trials.is_dir() else root
    return sorted(scan_root.glob("*/run.json"))


def summarize_live_rows(rows):
    grouped = {}
    for row in rows:
        key = condition_key(row)
        grouped.setdefault(key, []).append(row)

    summary = []
    for key, items in sorted(grouped.items()):
        final_values = [item.get("final_ok") for item in items if item.get("final_ok") is not None]
        successes = sum(1 for value in final_values if value)
        summary.append({
            "condition": key,
            "runs": len(items),
            "success_rate": successes / len(final_values) if final_values else None,
            "avg_total_elapsed_seconds": average_present(item.get("total_elapsed_seconds") for item in items),
            "avg_session_b_elapsed_seconds": average_present(item.get("session_b_elapsed_seconds") for item in items),
            "avg_handoff_chars": average_present(item.get("handoff_chars") for item in items),
            "repeated_investigation": None,
            "violations": None,
        })

    add_relative_labels(summary, "avg_total_elapsed_seconds", "total_time")
    add_relative_labels(summary, "avg_session_b_elapsed_seconds", "session_b_time")
    add_relative_labels(summary, "avg_handoff_chars", "handoff_chars")
    return summary


def condition_key(row):
    condition = row.get("condition", "")
    ablation = row.get("ablation", "")
    return f"{condition}:{ablation}" if ablation else condition


def average_present(values):
    present = [value for value in values if value is not None]
    return sum(present) / len(present) if present else None


def add_relative_labels(summary, source_key, target_key):
    values = sorted(item[source_key] for item in summary if item[source_key] is not None)
    if not values:
        for item in summary:
            item[target_key] = None
        return
    low_cut = values[max(0, len(values) // 3 - 1)]
    high_cut = values[min(len(values) - 1, (2 * len(values)) // 3)]
    for item in summary:
        value = item[source_key]
        if value is None:
            item[target_key] = None
        elif value <= low_cut:
            item[target_key] = "low"
        elif value >= high_cut:
            item[target_key] = "high"
        else:
            item[target_key] = "medium"


def summary_table(summary):
    """Return a compact report table shaped like the benchmark design note."""
    return [
        {
            "condition": item["condition"],
            "success": format_success_rate(item["success_rate"]),
            "total_time": item.get("total_time"),
            "b_time": item.get("session_b_time"),
            "handoff_chars": item.get("handoff_chars"),
            "repeated_investigation": item.get("repeated_investigation"),
            "violations": item.get("violations"),
        }
        for item in summary
    ]


def format_success_rate(value):
    if value is None:
        return None
    return f"{round(value * 100)}%"


def validate_task(task):
    """Validate the minimal task schema used by this harness."""
    required = [
        "id",
        "type",
        "description",
        "repo",
        "session_a",
        "session_b",
        "intent_context",
        "checkpoint_oracle",
        "oracle",
    ]
    missing = [key for key in required if key not in task]
    if missing:
        raise BenchError(f"Task {task.get('id', '<unknown>')} missing fields: {', '.join(missing)}")
    if "files" not in task["repo"]:
        raise BenchError(f"Task {task['id']} missing repo.files")
    if "changes" not in task["session_a"]:
        raise BenchError(f"Task {task['id']} missing session_a.changes")


def _validate_context(condition, ablation=None):
    if condition not in CONDITIONS:
        raise BenchError(f"Unsupported condition: {condition}")
    if ablation and condition != "intent-full":
        raise BenchError("Ablations only apply to intent-full.")
    if ablation and ablation not in ABLATIONS:
        raise BenchError(f"Unsupported ablation: {ablation}")


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def monotonic_now():
    return time.perf_counter()


def elapsed_seconds(start_iso, end_iso):
    start = datetime.fromisoformat(start_iso)
    end = datetime.fromisoformat(end_iso)
    return (end - start).total_seconds()


def read_live_state(run_dir):
    run = Path(run_dir)
    path = run / "run.json"
    if not path.is_file():
        raise BenchError(f"Live benchmark run not found: {run}")
    return run, json.loads(path.read_text(encoding="utf-8"))


def mark_live_error(run_dir, message):
    """Persist a terminal error for a live run when automation fails mid-run."""
    path = Path(run_dir) / "run.json"
    if not path.is_file():
        return
    state = json.loads(path.read_text(encoding="utf-8"))
    state["status"] = "error"
    state["error"] = message
    state.setdefault("events", {})["error_at"] = now_utc()
    write_live_state(Path(run_dir), state)


def write_live_state(run, state):
    run.mkdir(parents=True, exist_ok=True)
    (run / "run.json").write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def public_live_state(run, state):
    return {
        "run": str(run),
        "task": state.get("task_id", ""),
        "condition": state.get("condition", ""),
        "ablation": state.get("ablation", ""),
        "status": state.get("status", ""),
        "paths": state.get("paths", {}),
        "events": state.get("events", {}),
        "metrics": state.get("metrics", {}),
        "scores": state.get("scores", {}),
    }


def write_live_session_a_instructions(run, task, state):
    path = Path(state["paths"]["session_a_instructions"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_session_a_instructions(task, state), encoding="utf-8")


def write_live_session_b_instructions(run, task, state):
    path = Path(state["paths"]["session_b_instructions"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_session_b_instructions(task, state), encoding="utf-8")


def render_session_a_instructions(task, state):
    repo = state["paths"]["session_a_repo"]
    condition = state["condition"]
    lines = [
        "# Intent Benchmark Session A",
        "",
        f"Work only in this repository: `{repo}`.",
        "",
        "Complete Phase A only, then stop. Do not implement the final Session B fix.",
        "",
        "## Phase A Goal",
        "",
        task["session_a"]["goal"],
        "",
        "## Stop Rule",
        "",
        "Stop immediately after the checkpoint work is complete. Do not explain extra work.",
        "When the checkpoint is complete, send exactly this final response and exit: `PHASE_A_DONE`.",
        "Do not keep running tests, watching files, or waiting for follow-up instructions after that final response.",
    ]
    if condition == "chat-summary":
        lines.extend([
            "",
            "## Handoff Summary",
            "",
            "Before stopping, write `.benchmark/handoff-summary.md` with a concise summary of what you learned, what changed, and what Session B should do next.",
        ])
    elif condition == "full-transcript":
        lines.extend([
            "",
            "## Transcript Capture",
            "",
            "Before stopping, write `.benchmark/transcript.md` with a detailed transcript-style account of the work and findings.",
        ])
    elif condition == "intent-full":
        cli = intent_cli_command()
        lines.extend([
            "",
            "## Intent Recording",
            "",
            "Before stopping, initialize Intent if needed and record semantic history for the checkpoint.",
            f"Use `{cli} init`, then create one active intent and at least one snap with the same `{cli}` command prefix.",
            "Create a decision only when the task contains a long-lived constraint.",
            "Leave the intent active because Session B will continue it.",
        ])
    return "\n".join(lines).rstrip() + "\n"


def render_session_b_instructions(task, state):
    return "\n".join([
        "# Intent Benchmark Session B",
        "",
        f"Work only in this repository: `{state['paths']['session_b_repo']}`.",
        f"Read the handoff context first: `{state['paths']['session_b_context']}`.",
        "",
        "Continue from the checkpoint and complete the task.",
        "When the task is complete, send exactly this final response and exit: `PHASE_B_DONE`.",
        "Do not keep running tests, watching files, or waiting for follow-up instructions after that final response.",
        "",
        "## Session B Goal",
        "",
        task["session_b"]["goal"],
        "",
    ])


def render_live_context(task, state, session_a_repo):
    condition = state["condition"]
    ablation = state.get("ablation") or None
    _validate_context(condition, ablation)
    lines = [
        f"# Live Benchmark Context: {task['id']}",
        "",
        f"Condition: `{condition}`",
    ]
    if ablation:
        lines.append(f"Ablation: `{ablation}`")
    lines.extend([
        "",
        "## Session B Goal",
        "",
        task["session_b"]["goal"],
        "",
    ])

    if condition == "no-history":
        lines.extend([
            "## Available History",
            "",
            "No Session A history is available. Use only the repository state and Session B goal.",
        ])
    elif condition == "git-only":
        lines.extend([
            "## Diff From Session A",
            "",
            "```diff",
            live_repo_diff(task, session_a_repo) or "(no diff)",
            "```",
        ])
    elif condition == "chat-summary":
        lines.extend([
            "## Session A Summary",
            "",
            read_required_handoff_file(session_a_repo, "handoff-summary.md"),
        ])
    elif condition == "full-transcript":
        lines.extend([
            "## Session A Transcript",
            "",
            read_required_handoff_file(session_a_repo, "transcript.md"),
        ])
    elif condition == "intent-full":
        lines.extend(render_intent_context(load_live_intent_context(session_a_repo), ablation))

    return "\n".join(lines).rstrip() + "\n"


def read_required_handoff_file(repo, filename):
    path = Path(repo) / ".benchmark" / filename
    if not path.is_file():
        raise BenchError(f"Missing handoff file for live benchmark: {path}")
    return path.read_text(encoding="utf-8").strip()


def load_live_intent_context(repo):
    base = Path(repo) / ".intent"
    if not base.is_dir():
        raise BenchError("intent-full live handoff requires .intent/ in Session A repo.")

    intents = read_object_dir(base / "intents")
    snaps = read_object_dir(base / "snaps")
    decisions = read_object_dir(base / "decisions")
    active = [obj for obj in intents if obj.get("status") == "active"]
    intent = active[0] if active else (intents[0] if intents else None)
    if intent is None:
        raise BenchError("intent-full live handoff requires at least one intent.")

    snap_ids = set(intent.get("snap_ids", []))
    decision_ids = set(intent.get("decision_ids", []))
    return {
        "intent": intent,
        "snaps": [snap for snap in snaps if snap.get("id") in snap_ids or snap.get("intent_id") == intent["id"]],
        "decisions": [decision for decision in decisions if decision.get("id") in decision_ids],
    }


def read_object_dir(path):
    if not path.is_dir():
        return []
    return [
        json.loads(file.read_text(encoding="utf-8"))
        for file in sorted(path.glob("*.json"))
    ]


def stage_files(task, stage):
    """Return a path->content mapping for base or after_a state."""
    if stage not in {"base", "after_a"}:
        raise BenchError(f"Unsupported stage: {stage}")

    files = dict(task["repo"]["files"])
    if stage == "after_a":
        for path, content in task["session_a"].get("changes", {}).items():
            if content is None:
                files.pop(path, None)
            else:
                files[path] = content
    return files


def materialize(task, stage, out_dir, force=False):
    """Write a task repo stage to disk."""
    out = Path(out_dir)
    if out.exists():
        if not force:
            raise BenchError(f"Output already exists: {out}. Use --force to replace it.")
        if out.is_dir():
            shutil.rmtree(out)
        else:
            out.unlink()
    out.mkdir(parents=True, exist_ok=True)

    for rel_path, content in stage_files(task, stage).items():
        target = out / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return out


def init_git_repo(repo):
    """Initialize a small git repo so intent-full can run itt init."""
    subprocess.run(["git", "init"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.name", "intent-benchmark"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "intent-benchmark@example.com"],
        cwd=repo,
        capture_output=True,
        check=True,
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "base"],
        cwd=repo,
        capture_output=True,
        check=True,
    )


def unified_repo_diff(task):
    """Return a unified diff from base to the prebaked after_a state."""
    base = stage_files(task, "base")
    after = stage_files(task, "after_a")
    return unified_file_map_diff(base, after)


def live_repo_diff(task, repo_dir):
    """Return a unified diff from base to the live repo state."""
    return unified_file_map_diff(stage_files(task, "base"), read_repo_files(repo_dir))


def read_repo_files(repo_dir):
    """Read text files from a live task repo, excluding benchmark metadata."""
    root = Path(repo_dir)
    files = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] in {".git", ".intent", ".benchmark"}:
            continue
        try:
            files[str(rel)] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return files


def unified_file_map_diff(base, after):
    """Return a unified diff between two path->content mappings."""
    chunks = []

    for rel_path in sorted(set(base) | set(after)):
        before = base.get(rel_path, "")
        current = after.get(rel_path, "")
        if before == current:
            continue
        before_lines = before.splitlines()
        current_lines = current.splitlines()
        chunks.extend(
            difflib.unified_diff(
                before_lines,
                current_lines,
                fromfile=f"a/{rel_path}",
                tofile=f"b/{rel_path}",
                lineterm="",
            )
        )
        chunks.append("")

    return "\n".join(chunks).strip()


def render_context(task, condition, ablation=None):
    """Render a Session B context packet."""
    _validate_context(condition, ablation)

    lines = [
        f"# Benchmark Context: {task['id']}",
        "",
        f"Condition: `{condition}`",
    ]
    if ablation:
        lines.append(f"Ablation: `{ablation}`")

    lines.extend([
        "",
        "## Session B Goal",
        "",
        task["session_b"]["goal"],
        "",
    ])

    if condition == "no-history":
        lines.extend([
            "## Available History",
            "",
            "No Session A history is available. Use only the repository state and Session B goal.",
        ])
    elif condition == "git-only":
        lines.extend([
            "## Commit Message",
            "",
            task["session_a"].get("commit_message", "(none)"),
            "",
            "## Diff From Session A",
            "",
            "```diff",
            unified_repo_diff(task) or "(no diff)",
            "```",
        ])
    elif condition == "chat-summary":
        lines.extend([
            "## Session A Summary",
            "",
            task["session_a"].get("chat_summary", "(none)"),
        ])
    elif condition == "full-transcript":
        lines.extend([
            "## Session A Transcript",
            "",
            task["session_a"].get("transcript", "(none)"),
        ])
    elif condition == "intent-full":
        lines.extend(render_intent_context(task["intent_context"], ablation))

    return "\n".join(lines).rstrip() + "\n"


def _field(obj, key, ablation):
    if ablation == "no-snap" and key == "snap_ids":
        return None
    if ablation == "no-decision" and key == "decision_ids":
        return None
    if ablation == "no-why" and key == "why":
        return None
    if ablation == "no-status" and key == "status":
        return None
    if ablation == "no-relations" and (key.endswith("_ids") or key == "intent_id"):
        return None
    return obj.get(key)


def render_intent_context(ctx, ablation=None):
    """Render Intent-style objects, optionally ablated."""
    lines = ["## Intent Context", ""]

    if ablation != "no-intent":
        intent = ctx.get("intent", {})
        lines.extend(["### Intent", ""])
        for key in ("id", "status", "what", "why", "snap_ids", "decision_ids"):
            value = _field(intent, key, ablation)
            if value in (None, [], ""):
                continue
            lines.append(f"- `{key}`: {_format_value(value)}")
        lines.append("")

    if ablation != "no-snap":
        lines.extend(["### Snaps", ""])
        snaps = ctx.get("snaps", [])
        if not snaps:
            lines.append("(none)")
        for snap in snaps:
            parts = []
            for key in ("id", "what", "why", "intent_id"):
                value = _field(snap, key, ablation)
                if value not in (None, [], ""):
                    parts.append(f"{key}={_format_value(value)}")
            lines.append(f"- {'; '.join(parts)}")
        lines.append("")

    if ablation != "no-decision":
        lines.extend(["### Decisions", ""])
        decisions = ctx.get("decisions", [])
        if not decisions:
            lines.append("(none)")
        for decision in decisions:
            parts = []
            for key in ("id", "status", "what", "why", "intent_ids"):
                value = _field(decision, key, ablation)
                if value not in (None, [], ""):
                    parts.append(f"{key}={_format_value(value)}")
            lines.append(f"- {'; '.join(parts)}")
        lines.append("")

    return lines


def _format_value(value):
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def score_repo(task, repo_dir):
    """Score a completed Session B repository against a task oracle."""
    return score_repo_with_oracle(task, repo_dir, "oracle")


def score_repo_with_oracle(task, repo_dir, oracle_key):
    """Score a repository against a named task oracle."""
    repo = Path(repo_dir)
    if not repo.is_dir():
        raise BenchError(f"Repository directory not found: {repo}")
    oracle = task.get(oracle_key, {})
    if not oracle:
        raise BenchError(f"Task {task['id']} missing {oracle_key}.")
    checks = []

    for check in oracle.get("must_contain", []):
        checks.append(_check_contains(repo, check, expected=True))
    for check in oracle.get("must_not_contain", []):
        checks.append(_check_contains(repo, check, expected=False))

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    return {
        "ok": passed == total,
        "score": passed,
        "total": total,
        "checks": checks,
    }


def _check_contains(repo, check, expected):
    rel_path = check["path"]
    needle = check["text"]
    path = repo / rel_path
    content = path.read_text(encoding="utf-8") if path.exists() else ""
    found = needle in content
    passed = found if expected else not found
    return {
        "passed": passed,
        "kind": "must_contain" if expected else "must_not_contain",
        "path": rel_path,
        "text": needle,
        "reason": check.get("reason", ""),
    }
