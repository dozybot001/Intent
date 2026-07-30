"""Continuation-only benchmark protocol with frozen Session A checkpoints."""

import hashlib
import json
import os
import platform
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from intent_cli import __version__
from intent_cli.commands.core import build_inspect_result
from intent_cli.benchmark.statistics import analyze_trial_rows
from intent_cli.benchmark.harness import (
    BenchError,
    CONDITIONS,
    DEFAULT_TASKS,
    REASONING_EFFORTS,
    RunnerTimeout,
    elapsed_seconds,
    extract_codex_usage,
    init_git_repo,
    invoke_runner,
    live_begin,
    live_record_runner_usage,
    live_report,
    live_score,
    load_task,
    materialize,
    minimal_codex_config_text,
    now_utc,
    read_live_state,
    render_context,
    score_repo_with_oracle,
    summarize_live_rows,
    summary_table,
    write_json,
    write_live_session_b_instructions,
    write_live_state,
)


DEFAULT_CONTINUATION_CONDITIONS = [
    "no-history",
    "git-only",
    "flat-facts-matched",
    "intent-full",
]


def default_continuation_out_dir():
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return Path(".itt-benchmark") / "runs" / f"continuation-{stamp}"


def run_continuation_suite(
    out_dir=None,
    *,
    tasks=None,
    conditions=None,
    repeat=1,
    runner="codex",
    model=None,
    reasoning_effort="low",
    stage="screening",
    confirmation_lock=None,
    seed=1729,
    max_pairs=None,
    max_total_input_tokens=None,
    max_total_wall_seconds=None,
    force=False,
    timeout=600,
    runner_func=None,
):
    """Run paired Session B trials from canonical Session A checkpoints."""
    task_ids = tasks or DEFAULT_TASKS
    condition_names = conditions or DEFAULT_CONTINUATION_CONDITIONS
    if repeat < 1:
        raise BenchError("repeat must be >= 1")
    if stage not in {"screening", "confirmation", "exploratory"}:
        raise BenchError(f"Unsupported study stage: {stage}")
    if reasoning_effort not in REASONING_EFFORTS:
        raise BenchError(f"Unsupported reasoning effort: {reasoning_effort}")
    real_codex = runner == "codex" and runner_func is None
    if real_codex and not model:
        raise BenchError("Continuation benchmarks require an explicit --model for reproducibility.")
    if real_codex and model != "gpt-5.6-terra":
        raise BenchError("This preregistered protocol requires --model gpt-5.6-terra.")
    if real_codex and reasoning_effort != "low":
        raise BenchError("This preregistered protocol requires --reasoning-effort low.")
    if real_codex and (timeout is None or timeout <= 0):
        raise BenchError("Continuation benchmarks require a positive per-trial --timeout.")
    if runner != "codex" and runner_func is None:
        raise BenchError(f"Unsupported runner: {runner}")
    if max_pairs is not None and max_pairs < 1:
        raise BenchError("max_pairs must be >= 1")
    if max_total_input_tokens is not None and max_total_input_tokens < 1:
        raise BenchError("max_total_input_tokens must be >= 1")
    if max_total_wall_seconds is not None and max_total_wall_seconds <= 0:
        raise BenchError("max_total_wall_seconds must be > 0")
    if not condition_names:
        raise BenchError("At least one condition is required.")
    if len(condition_names) != len(set(condition_names)):
        raise BenchError("Continuation benchmark conditions must be unique.")
    unsupported = [condition for condition in condition_names if condition not in CONDITIONS]
    if unsupported:
        raise BenchError(f"Unsupported condition: {unsupported[0]}")

    loaded_tasks = [freeze_task(load_task(task_id)) for task_id in task_ids]
    invalid_strata = [
        task["id"]
        for task in loaded_tasks
        if task.get("stratum") not in {"C0", "C1", "C2", "C3", "C4"}
    ]
    if invalid_strata:
        raise BenchError(f"Task has invalid or missing stratum: {invalid_strata[0]}")
    tasks_by_id = {task["id"]: task for task in loaded_tasks}
    confirmation_lock_result = verify_confirmation_lock(
        confirmation_lock,
        stage=stage,
        tasks=loaded_tasks,
        conditions=condition_names,
        repeat=repeat,
        seed=seed,
    )
    root = Path(out_dir) if out_dir else default_continuation_out_dir()
    _prepare_output_root(root, force=force)
    checkpoints_dir = root / "checkpoints"
    trials_dir = root / "trials"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    trials_dir.mkdir(parents=True, exist_ok=True)
    plan = build_trial_plan(
        task_ids,
        condition_names,
        repeat=repeat,
        seed=seed,
        max_pairs=max_pairs,
    )
    task_aliases = {
        pair["task"]: pair["task_alias"]
        for pair in plan["pairs"]
    }
    checkpoints = {
        task_id: prepare_canonical_checkpoint(
            tasks_by_id[task_id],
            checkpoints_dir / task_alias,
            write_metadata=False,
        )
        for task_id, task_alias in task_aliases.items()
    }
    parity = {
        task_id: validate_context_parity(tasks_by_id[task_id])
        for task_id in task_aliases
        if {"flat-facts-matched", "intent-full"}.issubset(condition_names)
    }
    masking_audit = {
        task_id: {
            condition: validate_label_masking(tasks_by_id[task_id], condition)
            for condition in condition_names
        }
        for task_id in task_aliases
    }
    environment = collect_environment_metadata(real_codex=real_codex)
    if real_codex and environment["source_dirty"]:
        raise BenchError(
            "Preregistered continuation runs require a clean committed Intent source revision."
        )
    manifest = build_continuation_manifest(
        root,
        task_ids=[pair["task_alias"] for pair in plan["pairs"]],
        conditions=[
            trial["treatment_alias"]
            for pair in plan["pairs"]
            for trial in pair["trials"]
        ],
        repeat=repeat,
        runner=runner,
        runner_isolation="clean-home" if runner == "codex" and runner_func is None else "injected-runner",
        model=model,
        reasoning_effort=reasoning_effort,
        seed=seed,
        max_pairs=max_pairs,
        max_total_input_tokens=max_total_input_tokens,
        max_total_wall_seconds=max_total_wall_seconds,
        timeout=timeout,
        plan=public_trial_plan(plan, decoded=False),
        checkpoints=None,
    )
    manifest["masking"] = "label-masked; representation remains inferable"
    manifest["stage"] = stage
    manifest["confirmation_lock"] = (
        {
            "verified": confirmation_lock_result["verified"],
            "sha256": confirmation_lock_result["sha256"],
        }
        if confirmation_lock_result
        else None
    )
    manifest["resource_cap_semantics"] = "soft thresholds checked at complete pair boundaries"
    write_json(root / "manifest.json", manifest)

    errors = []
    task_failures = []
    invalid_pair_ids = set()
    stopped_reason = None
    cumulative_input_tokens = 0
    started = time.perf_counter()
    completed_trials = 0
    attempted_trials = 0
    pair_failed = False
    for pair in plan["pairs"]:
        if max_total_input_tokens is not None and cumulative_input_tokens >= max_total_input_tokens:
            stopped_reason = "max_total_input_tokens"
            break
        if max_total_wall_seconds is not None and time.perf_counter() - started >= max_total_wall_seconds:
            stopped_reason = "max_total_wall_seconds"
            break

        prepared = []
        task = tasks_by_id[pair["task"]]
        checkpoint = checkpoints[pair["task"]]
        try:
            for trial in pair["trials"]:
                prepared.append(initialize_continuation_trial(
                    task=task,
                    condition=trial["condition"],
                    task_alias=pair["task_alias"],
                    treatment_alias=trial["treatment_alias"],
                    run_dir=trials_dir / trial["trial_id"],
                    checkpoint=checkpoint,
                    pair_id=pair["pair_id"],
                    repeat_index=pair["repeat_index"],
                    order_index=trial["order_index"],
                    model=model,
                    reasoning_effort=reasoning_effort,
                ))
        except BenchError as exc:
            invalidate_prepared_pair(prepared, str(exc))
            invalid_pair_ids.add(pair["pair_id"])
            errors.append({"pair_id": pair["pair_id"], "error": str(exc)})
            stopped_reason = "infrastructure_error"
            pair_failed = True
            break

        for trial, prepared_trial in zip(pair["trials"], prepared):
            try:
                attempted_trials += 1
                state = execute_continuation_trial(
                    task=task,
                    prepared=prepared_trial,
                    runner=runner,
                    model=model,
                    reasoning_effort=reasoning_effort,
                    timeout=timeout,
                    runner_func=runner_func,
                )
                completed_trials += 1
                usage = state.get("metrics", {}).get("session_b_usage", {})
                cumulative_input_tokens += usage.get("input_tokens", 0)
            except RunnerTimeout as exc:
                failed_usage = read_runner_usage_artifact(prepared_trial["run"])
                if failed_usage:
                    live_record_runner_usage(prepared_trial["run"], "b", failed_usage)
                    cumulative_input_tokens += failed_usage.get("input_tokens", 0)
                mark_timeout_task_failure(prepared_trial["run"], str(exc))
                completed_trials += 1
                task_failures.append({
                    "trial_id": trial["trial_id"],
                    "task": pair["task"],
                    "condition": trial["condition"],
                    "kind": "runner_timeout",
                    "error": str(exc),
                })
            except BenchError as exc:
                failed_usage = read_runner_usage_artifact(prepared_trial["run"])
                if failed_usage:
                    live_record_runner_usage(prepared_trial["run"], "b", failed_usage)
                    cumulative_input_tokens += failed_usage.get("input_tokens", 0)
                errors.append({
                    "trial_id": trial["trial_id"],
                    "task": pair["task"],
                    "condition": trial["condition"],
                    "error": str(exc),
                })
                invalidate_prepared_pair(prepared, str(exc))
                invalid_pair_ids.add(pair["pair_id"])
                stopped_reason = "infrastructure_error"
                pair_failed = True
                break
        if pair_failed:
            break

    missing_trial_ids = decode_trial_states(plan, tasks_by_id, checkpoints)
    snapshot_frozen_tasks(loaded_tasks, root / "tasks")
    for task_id, checkpoint in checkpoints.items():
        write_json(Path(checkpoint["repo"]).parent / "checkpoint.json", checkpoint)
    report = live_report(root)
    valid_rows = [row for row in report["runs"] if row.get("pair_valid", True)]
    report["summary"] = summarize_live_rows(valid_rows)
    report["table"] = summary_table(report["summary"])
    context_integrity = [
        {
            "run": row["run"],
            "matches_preflight": row.get("context_sha256")
            == masking_audit[row["task"]][row["condition"]]["context_sha256"],
        }
        for row in report["runs"]
    ]
    report["statistics"] = analyze_trial_rows(valid_rows)
    report["statistics_by_stratum"] = {
        stratum: analyze_trial_rows([row for row in valid_rows if row.get("stratum") == stratum])
        for stratum in ("C0", "C1", "C2", "C3", "C4")
        if any(row.get("stratum") == stratum for row in valid_rows)
    }
    efficacy_rows = [
        row for row in valid_rows
        if row.get("stratum") in {"C2", "C3"} and row.get("repeat_index") == 1
    ]
    report["efficacy_statistics_c2_c3"] = analyze_trial_rows(efficacy_rows)
    report["efficacy_statistics_c2_c3_all_repeats_sensitivity"] = analyze_trial_rows([
        row for row in valid_rows if row.get("stratum") in {"C2", "C3"}
    ])
    report.update({
        "protocol": "continuation-only",
        "out": str(root),
        "runner": runner,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "stage": stage,
        "confirmation_lock": confirmation_lock_result,
        "seed": seed,
        "completed_trials": completed_trials,
        "attempted_trials": attempted_trials,
        "planned_trials": plan["trial_count"],
        "expected_primary_efficacy_pairs": sum(
            1 for task in loaded_tasks if task.get("stratum") in {"C2", "C3"}
        ),
        "cumulative_input_tokens": cumulative_input_tokens,
        "stopped_reason": stopped_reason,
        "errors": errors,
        "invalid_pair_count": len(invalid_pair_ids),
        "invalid_pair_ids": sorted(invalid_pair_ids),
        "missing_planned_trial_count": len(missing_trial_ids),
        "missing_planned_trial_ids": missing_trial_ids,
        "task_failures": task_failures,
        "context_parity": parity,
        "label_masking_audit": masking_audit,
        "context_integrity": context_integrity,
        "environment": environment,
        "suite_wall_seconds": time.perf_counter() - started,
        "max_pair_boundary_overshoot_trials": len(condition_names),
        "manifest_path": str(root / "manifest.json"),
        "report_path": str(root / "report.json"),
        "tasks_dir": str(root / "tasks"),
        "trials_dir": str(trials_dir),
    })
    report["preregistered_assessment"] = assess_preregistered_result(
        stage,
        report,
        valid_rows=valid_rows,
    )
    write_json(root / "report.json", report)

    manifest["completed_at"] = now_utc()
    manifest["tasks"] = list(task_ids)
    manifest["conditions"] = list(condition_names)
    manifest["plan"] = public_trial_plan(plan, decoded=True)
    manifest["checkpoints"] = checkpoints
    manifest["context_parity"] = parity
    manifest["label_masking_audit"] = masking_audit
    manifest["environment"] = environment
    manifest["confirmation_lock"] = confirmation_lock_result
    manifest["completed_trials"] = completed_trials
    manifest["attempted_trials"] = attempted_trials
    manifest["cumulative_input_tokens"] = cumulative_input_tokens
    manifest["stopped_reason"] = stopped_reason
    if errors:
        manifest["status"] = "completed_with_errors"
    elif stopped_reason:
        manifest["status"] = "stopped_resource_cap"
    else:
        manifest["status"] = "completed"
    write_json(root / "manifest.json", manifest)
    return report


def build_trial_plan(task_ids, conditions, *, repeat, seed, max_pairs=None):
    """Create complete repeat waves with Latin-rotated condition positions."""
    if not task_ids:
        raise BenchError("At least one task is required.")
    if max_pairs is not None and max_pairs % len(task_ids) != 0:
        raise BenchError("max_pairs must end on a complete task wave.")
    rng = random.Random(seed)
    alias_order = list(task_ids)
    rng.shuffle(alias_order)
    task_aliases = {
        task_id: f"task-{index:03d}"
        for index, task_id in enumerate(alias_order, start=1)
    }
    base_conditions = list(conditions)
    rng.shuffle(base_conditions)
    pairs = []
    for repeat_index in range(1, repeat + 1):
        wave_tasks = list(task_ids)
        rng.shuffle(wave_tasks)
        for wave_position, task_id in enumerate(wave_tasks):
            rotation = (wave_position + repeat_index - 1) % len(base_conditions)
            ordered_conditions = base_conditions[rotation:] + base_conditions[:rotation]
            pairs.append({
                "task": task_id,
                "task_alias": task_aliases[task_id],
                "repeat_index": repeat_index,
                "wave_index": repeat_index,
                "pair_id": f"pair-{len(pairs) + 1:04d}",
                "ordered_conditions": ordered_conditions,
            })
    if max_pairs is not None:
        pairs = pairs[:max_pairs]

    order_index = 0
    for pair in pairs:
        pair["trials"] = []
        for condition in pair.pop("ordered_conditions"):
            order_index += 1
            pair["trials"].append({
                "trial_id": f"trial-{order_index:04d}",
                "condition": condition,
                "treatment_alias": f"treatment-{rng.getrandbits(48):012x}",
                "order_index": order_index,
            })
    return {
        "pairs": pairs,
        "pair_count": len(pairs),
        "trial_count": order_index,
    }


def freeze_task(task):
    """Detach a validated task from its mutable source file."""
    payload = {key: value for key, value in task.items() if key != "_path"}
    frozen = json.loads(json.dumps(payload, ensure_ascii=False))
    semantic_payload = semantic_graph_payload(frozen.get("intent_context", {}))
    frozen["atomic_fact_ledger"] = atomic_fact_ledger(semantic_payload)
    return frozen


def verify_confirmation_lock(path, *, stage, tasks, conditions, repeat, seed):
    """Require an exact preregistered holdout lock before confirmation can run."""
    if stage != "confirmation":
        if path:
            raise BenchError("--confirmation-lock only applies to --stage confirmation.")
        return None
    if not path:
        raise BenchError("--stage confirmation requires --confirmation-lock LOCK.json.")
    lock_path = Path(path)
    if not lock_path.is_file():
        raise BenchError(f"Confirmation lock not found: {lock_path}")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("schema") != "intent-benchmark-confirmation-lock-v1":
        raise BenchError("Unsupported confirmation lock schema.")
    expected_tasks = {task["id"]: task_spec_sha256(task) for task in tasks}
    checks = {
        "tasks": lock.get("tasks") == expected_tasks,
        "conditions": lock.get("conditions") == list(conditions),
        "repeat": lock.get("repeat") == repeat,
        "seed": lock.get("seed") == seed,
        "model": lock.get("model") == "gpt-5.6-terra",
        "reasoning_effort": lock.get("reasoning_effort") == "low",
    }
    prereg = Path(__file__).resolve().parents[3] / "docs" / "benchmarks" / "continuation-benchmark-preregistration.md"
    prereg_sha = hashlib.sha256(prereg.read_bytes()).hexdigest() if prereg.is_file() else None
    checks["preregistration"] = lock.get("preregistration_sha256") == prereg_sha
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise BenchError(f"Confirmation lock mismatch: {failed[0]}")
    return {
        "path": str(lock_path.resolve()),
        "sha256": hashlib.sha256(lock_path.read_bytes()).hexdigest(),
        "verified": True,
        "checks": checks,
    }


def public_trial_plan(plan, *, decoded):
    """Return a manifest-safe plan, decoding real labels only after all trials."""
    pairs = []
    for pair in plan["pairs"]:
        row = {
            "pair_id": pair["pair_id"],
            "task": pair["task"] if decoded else pair["task_alias"],
            "task_alias": pair["task_alias"],
            "repeat_index": pair["repeat_index"],
            "wave_index": pair["wave_index"],
            "trials": [],
        }
        for trial in pair["trials"]:
            row["trials"].append({
                "trial_id": trial["trial_id"],
                "condition": trial["condition"] if decoded else trial["treatment_alias"],
                "treatment_alias": trial["treatment_alias"],
                "order_index": trial["order_index"],
            })
        pairs.append(row)
    return {
        "pairs": pairs,
        "pair_count": plan["pair_count"],
        "trial_count": plan["trial_count"],
    }


def validate_context_parity(task, *, max_length_ratio=1.10):
    """Reject matched treatments that differ in facts or exceed the length budget."""
    expected_payload = task_semantic_payload(task)
    with tempfile.TemporaryDirectory(prefix="intent-benchmark-parity-") as temp_root:
        fixture = Path(temp_root)
        write_intent_fixture(fixture, expected_payload)
        inspected = build_inspect_result(fixture / ".intent", full=True)
    product_payload = {
        "intents": inspected["intents"],
        "snaps": inspected["snaps"],
        "decisions": inspected["decisions"],
    }
    if product_payload != expected_payload:
        raise BenchError(f"Product graph parity failed for {task['id']}.")

    expected_ledger = task.get("atomic_fact_ledger") or atomic_fact_ledger(expected_payload)
    product_ledger = atomic_fact_ledger(product_payload)
    if product_ledger != expected_ledger:
        raise BenchError(f"Atomic fact ledger round-trip failed for {task['id']}.")
    fact_rows = matched_fact_rows(expected_payload)
    flat = render_matched_flat_context(task)
    graph = render_continuation_context(task, "intent-full")
    for label, context in (("flat", flat), ("graph", graph)):
        for forbidden in (task["id"], "flat-facts-matched", "intent-full", "Condition:"):
            if forbidden in context:
                raise BenchError(
                    f"{label} context leaks benchmark label {forbidden!r} for {task['id']}."
                )
    shorter = min(len(flat), len(graph))
    ratio = max(len(flat), len(graph)) / shorter if shorter else float("inf")
    if ratio > max_length_ratio:
        raise BenchError(
            f"Matched context length ratio {ratio:.3f} exceeds {max_length_ratio:.3f} for {task['id']}."
        )
    fact_bytes = json.dumps(
        fact_rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "fact_coverage": {
            "flat-facts-matched": len(fact_rows) / len(expected_ledger) if expected_ledger else 1.0,
            "intent-full": len(product_ledger) / len(expected_ledger) if expected_ledger else 1.0,
        },
        "semantic_fact_count": len(fact_rows),
        "semantic_facts_sha256": hashlib.sha256(fact_bytes).hexdigest(),
        "flat_chars": len(flat),
        "intent_chars": len(graph),
        "max_to_min_char_ratio": ratio,
        "char_ratio_limit": max_length_ratio,
    }


def validate_label_masking(task, condition):
    context = render_continuation_context(task, condition)
    forbidden = (task["id"], condition, f"Condition: `{condition}`")
    leaked = [label for label in forbidden if label and label in context]
    if leaked:
        raise BenchError(f"Context label masking failed for {task['id']}: {leaked[0]!r}")
    return {
        "context_sha256": sha256_text(context),
        "context_chars": len(context),
        "label_leaks": [],
    }


def snapshot_frozen_tasks(tasks, out_dir):
    """Persist the in-memory frozen specs only after model execution ends."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        write_json(out / f"{task['id']}.json", task)


def assess_preregistered_result(stage, report, *, valid_rows):
    """Apply fixed thresholds without turning screening into confirmation."""
    efficacy = report["efficacy_statistics_c2_c3"]
    conditions = efficacy.get("conditions", {})
    intent = conditions.get("intent-full", {}).get("success", {})
    flat = conditions.get("flat-facts-matched", {}).get("success", {})
    comparison = next(
        (
            row for row in efficacy.get("pairing", {}).get("comparisons", [])
            if {row["condition_a"], row["condition_b"]}
            == {"intent-full", "flat-facts-matched"}
        ),
        None,
    )
    effect = None
    intent_only = None
    flat_only = None
    one_sided_p = None
    complete_pairs = 0
    if comparison:
        complete_pairs = comparison["complete_pairs"]
        if comparison["condition_a"] == "intent-full":
            effect = comparison["success_rate_difference_a_minus_b"]
            intent_only = comparison["condition_a_only_pass"]
            flat_only = comparison["condition_b_only_pass"]
            one_sided_p = comparison["mcnemar_exact_one_sided_p_a_greater"]
        else:
            raw = comparison["success_rate_difference_a_minus_b"]
            effect = -raw if raw is not None else None
            intent_only = comparison["condition_b_only_pass"]
            flat_only = comparison["condition_a_only_pass"]
            one_sided_p = comparison["mcnemar_exact_one_sided_p_b_greater"]

    c4_intent_rows = [
        row for row in valid_rows
        if row.get("stratum") == "C4"
        and row.get("condition") == "intent-full"
        and row.get("repeat_index") == 1
    ]
    c4_safe = all(row.get("final_ok") is True for row in c4_intent_rows) if c4_intent_rows else None
    thresholds = {
        "intent_success_at_least_75_percent": (
            intent.get("rate") is not None and intent["rate"] >= 0.75
        ),
        "intent_minus_flat_at_least_10pp": effect is not None and effect >= 0.10,
        "one_sided_exact_mcnemar_p_at_most_0_05": (
            one_sided_p is not None and one_sided_p <= 0.05
        ),
        "no_invalid_pairs": report.get("invalid_pair_count") == 0,
        "cohort_fully_attempted": (
            report.get("attempted_trials") == report.get("planned_trials")
        ),
        "cohort_fully_completed": (
            report.get("completed_trials") == report.get("planned_trials")
        ),
        "no_missing_planned_trials": report.get("missing_planned_trial_count") == 0,
        "no_infrastructure_errors": not report.get("errors"),
        "no_early_stop": report.get("stopped_reason") is None,
        "all_primary_efficacy_pairs_present": (
            complete_pairs == report.get("expected_primary_efficacy_pairs")
        ),
        "confirmation_lock_verified": (
            report.get("confirmation_lock", {}).get("verified") is True
            if report.get("confirmation_lock")
            else False
        ),
        "all_contexts_match_preflight": all(
            row.get("matches_preflight") is True
            for row in report.get("context_integrity", [])
        ),
        "matched_context_parity_passes": all(
            row.get("max_to_min_char_ratio", float("inf"))
            <= row.get("char_ratio_limit", 0)
            for row in report.get("context_parity", {}).values()
        ),
        "evaluator_read_isolation_active": report.get("environment", {}).get(
            "evaluator_read_isolation"
        ) == "darwin-sandbox-exec",
        "c4_has_no_intent_history_failure": c4_safe,
    }
    all_observed = complete_pairs > 0 and c4_safe is not None
    passes = all_observed and all(value is True for value in thresholds.values())
    return {
        "stage": stage,
        "claim_status": (
            "screening_only_no_confirmatory_claim"
            if stage == "screening"
            else (
                "confirmatory_thresholds_met" if passes else "confirmatory_thresholds_not_met"
            )
            if stage == "confirmation"
            else "exploratory_only_no_confirmatory_claim"
        ),
        "complete_c2_c3_pairs": complete_pairs,
        "intent_success_rate": intent.get("rate"),
        "flat_success_rate": flat.get("rate"),
        "intent_minus_flat_success_rate": effect,
        "intent_only_success_pairs": intent_only,
        "flat_only_success_pairs": flat_only,
        "mcnemar_exact_one_sided_p_intent_greater": one_sided_p,
        "c4_intent_safe": c4_safe,
        "thresholds": thresholds,
        "confirmatory_pass": passes if stage == "confirmation" else None,
    }


def read_runner_usage_artifact(run_dir):
    path = Path(run_dir) / "session-b" / "codex-events.jsonl"
    if not path.is_file():
        return None
    return extract_codex_usage(path.read_text(encoding="utf-8"))


def mark_timeout_task_failure(run_dir, message):
    """Persist a fixed-budget timeout as a strict task failure, not exclusion."""
    run, state = read_live_state(run_dir)
    now = now_utc()
    state["status"] = "failed"
    state["error"] = message
    state.setdefault("events", {})["final_score_at"] = now
    state.setdefault("scores", {})["final"] = {
        "ok": False,
        "score": 0,
        "total": 1,
        "checks": [{
            "passed": False,
            "kind": "runner_timeout",
            "path": "(runner)",
            "text": message,
            "reason": "The agent did not finish within the fixed per-trial budget.",
        }],
    }
    started = state.get("events", {}).get("session_b_started_at")
    if started:
        state.setdefault("metrics", {})["session_b_elapsed_seconds"] = elapsed_seconds(started, now)
    metrics = state.setdefault("metrics", {})
    parts = [
        metrics.get("session_a_elapsed_seconds"),
        metrics.get("handoff_elapsed_seconds"),
        metrics.get("session_b_elapsed_seconds"),
    ]
    if all(value is not None for value in parts):
        metrics["total_elapsed_seconds"] = sum(parts)
    write_live_state(run, state)


def invalidate_prepared_pair(prepared, message):
    """Exclude every member of a pair after one infrastructure failure."""
    for trial in prepared:
        run, state = read_live_state(trial["run"])
        state["pair_valid"] = False
        state["status"] = "invalid_infrastructure"
        state["error"] = message
        state.setdefault("events", {})["invalidated_at"] = now_utc()
        write_live_state(run, state)


def decode_trial_states(plan, tasks_by_id, checkpoints):
    """Reveal task and condition labels only after no model calls remain."""
    missing = []
    for pair in plan["pairs"]:
        task = tasks_by_id[pair["task"]]
        checkpoint = checkpoints[pair["task"]]
        for trial in pair["trials"]:
            run = Path(checkpoint["repo"]).parents[2] / "trials" / trial["trial_id"]
            state_path = run / "run.json"
            if not state_path.is_file():
                missing.append(trial["trial_id"])
                continue
            _run, state = read_live_state(run)
            state["task_id"] = task["id"]
            state["condition"] = trial["condition"]
            state["stratum"] = task["stratum"]
            state.setdefault("scores", {})["checkpoint"] = checkpoint["checkpoint_score"]
            state.setdefault("events", {})["labels_decoded_at"] = now_utc()
            write_live_state(run, state)
    return missing


def prepare_canonical_checkpoint(task, checkpoint_dir, *, write_metadata=True):
    """Materialize and validate one frozen after-A repository per task."""
    root = Path(checkpoint_dir)
    repo = root / "repo"
    materialize(task, "after_a", repo)
    init_git_repo(repo)

    checkpoint_score = score_repo_with_oracle(task, repo, "checkpoint_oracle")
    if not checkpoint_score["ok"]:
        raise BenchError(f"Canonical checkpoint failed for {task['id']}.")
    final_score = score_repo_with_oracle(task, repo, "oracle")
    if final_score["ok"]:
        raise BenchError(f"Canonical checkpoint already passes the final oracle for {task['id']}.")

    fact_rows = matched_fact_rows(task_semantic_payload(task))
    fact_bytes = json.dumps(
        fact_rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    metadata = {
        "task": task["id"],
        "repo": str(repo),
        "task_sha256": task_spec_sha256(task),
        "checkpoint_sha256": tree_sha256(repo),
        "checkpoint_git_head": git_repo_output(repo, "rev-parse", "HEAD"),
        "checkpoint_git_tree": git_repo_output(repo, "rev-parse", "HEAD^{tree}"),
        "checkpoint_git_objects_sha256": sha256_text(
            git_repo_output(repo, "rev-list", "--objects", "--all") or ""
        ),
        "checkpoint_git_status_sha256": sha256_text(
            git_repo_output(repo, "status", "--porcelain=v1") or ""
        ),
        "semantic_facts_sha256": hashlib.sha256(fact_bytes).hexdigest(),
        "semantic_fact_count": len(fact_rows),
        "checkpoint_score": checkpoint_score,
        "final_precondition_score": final_score,
    }
    if write_metadata:
        write_json(root / "checkpoint.json", metadata)
    return metadata


def initialize_continuation_trial(
    *,
    task,
    condition,
    task_alias,
    treatment_alias,
    run_dir,
    checkpoint,
    pair_id,
    repeat_index,
    order_index,
    model,
    reasoning_effort,
):
    """Prepare one label-masked Session B trial without invoking a model."""
    run = Path(run_dir)
    repo = run / "session-b" / "repo"
    context_path = run / "session-b" / "context.md"
    instructions_path = run / "session-b" / "instructions.md"
    shutil.copytree(Path(checkpoint["repo"]), repo)
    if tree_sha256(repo) != checkpoint["checkpoint_sha256"]:
        raise BenchError(f"Frozen checkpoint hash mismatch for {task['id']}.")
    if git_repo_output(repo, "rev-parse", "HEAD") != checkpoint["checkpoint_git_head"]:
        raise BenchError(f"Frozen checkpoint Git HEAD mismatch for {task['id']}.")
    if git_repo_output(repo, "rev-parse", "HEAD^{tree}") != checkpoint["checkpoint_git_tree"]:
        raise BenchError(f"Frozen checkpoint Git tree mismatch for {task['id']}.")
    objects = git_repo_output(repo, "rev-list", "--objects", "--all") or ""
    if sha256_text(objects) != checkpoint["checkpoint_git_objects_sha256"]:
        raise BenchError(f"Frozen checkpoint Git object mismatch for {task['id']}.")
    status = git_repo_output(repo, "status", "--porcelain=v1") or ""
    if sha256_text(status) != checkpoint["checkpoint_git_status_sha256"]:
        raise BenchError(f"Frozen checkpoint Git status mismatch for {task['id']}.")

    handoff_started = time.perf_counter()
    context = render_continuation_context(task, condition)
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(context, encoding="utf-8")
    state = {
        "schema": "intent-benchmark-trial-v2",
        "protocol": "continuation-only",
        "task_id": task_alias,
        "condition": treatment_alias,
        "task_alias": task_alias,
        "treatment_alias": treatment_alias,
        "ablation": "",
        "pair_id": pair_id,
        "repeat_index": repeat_index,
        "order_index": order_index,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "status": "handoff_ready",
        "pair_valid": True,
        "created_at": now_utc(),
        "checkpoint_sha256": checkpoint["checkpoint_sha256"],
        "task_sha256": checkpoint["task_sha256"],
        "context_sha256": hashlib.sha256(context.encode("utf-8")).hexdigest(),
        "paths": {
            "session_b_repo": str(repo),
            "session_b_context": str(context_path),
            "session_b_instructions": str(instructions_path),
        },
        "events": {},
        "scores": {},
        "metrics": {
            "session_a_elapsed_seconds": 0.0,
            "handoff_elapsed_seconds": time.perf_counter() - handoff_started,
            "handoff_chars": len(context),
        },
    }
    write_live_state(run, state)
    write_live_session_b_instructions(run, task, state)
    return {
        "run": run,
        "repo": repo,
        "instructions": instructions_path,
    }


def execute_continuation_trial(
    *,
    task,
    prepared,
    runner,
    model,
    reasoning_effort,
    timeout,
    runner_func,
):
    """Invoke and score one already-prepared Session B trial."""
    run = prepared["run"]
    repo = prepared["repo"]
    instructions_path = prepared["instructions"]
    live_begin(run, "b")
    usage = invoke_runner(
        runner,
        phase="b",
        repo=repo,
        instructions=instructions_path,
        run_dir=run,
        model=model,
        reasoning_effort=reasoning_effort,
        timeout=timeout,
        runner_func=runner_func,
        expose_intent_cli=False,
        isolate_evaluator=True,
    )
    if usage:
        live_record_runner_usage(run, "b", usage)
    return live_score(run, task=task)


def render_continuation_context(task, condition):
    """Build a label-masked packet; intent-full uses inspect in an external fixture."""
    if condition == "flat-facts-matched":
        return render_matched_flat_context(task)
    if condition != "intent-full":
        rendered = render_context(task, condition, disclose_condition=False)
        return rendered.replace(
            f"# Continuation Context: {task['id']}",
            "# Continuation Context",
            1,
        )

    with tempfile.TemporaryDirectory(prefix="intent-benchmark-inspect-") as temp_root:
        fixture = Path(temp_root)
        write_intent_fixture(fixture, task_semantic_payload(task))
        inspected = build_inspect_result(fixture / ".intent", full=True)
    payload = {
        "intents": inspected["intents"],
        "snaps": inspected["snaps"],
        "decisions": inspected["decisions"],
    }
    return "\n".join([
        "# Continuation Context",
        "",
        "## Session B Goal",
        "",
        task["session_b"]["goal"],
        "",
        "## Semantic History",
        "",
        "```json",
        json.dumps(payload, indent=2, ensure_ascii=False),
        "```",
        "",
    ])


def render_matched_flat_context(task):
    """Render every graph field as an ungrouped fact without dropping content."""
    payload = task_semantic_payload(task)
    lines = [
        "# Continuation Context",
        "",
        "## Session B Goal",
        "",
        task["session_b"]["goal"],
        "",
        "## Semantic History",
        "",
    ]
    for fact_id, subject_field, value in matched_fact_rows(payload):
        rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
        lines.append(f"- `{fact_id}`: {subject_field} = {rendered}")
    return "\n".join(lines).rstrip() + "\n"


def semantic_graph_payload(context):
    """Normalize task objects into the same three collections exposed by inspect --full."""
    intents = context.get("intents")
    if intents is None:
        one = context.get("intent")
        intents = [one] if one else []

    def normalize(rows, object_name):
        normalized = []
        for row in rows:
            payload = dict(row)
            payload.setdefault("object", object_name)
            normalized.append(payload)
        return sorted(normalized, key=lambda row: row.get("id", ""))

    return {
        "intents": normalize(intents, "intent"),
        "snaps": normalize(context.get("snaps", []), "snap"),
        "decisions": normalize(context.get("decisions", []), "decision"),
    }


def atomic_fact_ledger(payload):
    """Enumerate every model-visible graph field into one canonical ledger."""
    rows = []
    for collection in ("intents", "snaps", "decisions"):
        object_type = collection[:-1] if collection != "intents" else "intent"
        for index, obj in enumerate(payload.get(collection, []), start=1):
            object_id = obj.get("id", f"{object_type}-{index:03d}")
            for key in sorted(obj):
                rows.append({
                    "id": f"F{len(rows) + 1:03d}",
                    "object_type": object_type,
                    "object_id": object_id,
                    "field": key,
                    "value": obj[key],
                    "model_visible": True,
                })
    return rows


def semantic_graph_from_ledger(ledger):
    """Reconstruct the product graph exclusively from frozen atomic facts."""
    objects = {"intent": {}, "snap": {}, "decision": {}}
    for fact in ledger:
        if not fact.get("model_visible", False):
            continue
        object_type = fact["object_type"]
        object_id = fact["object_id"]
        objects[object_type].setdefault(object_id, {})[fact["field"]] = fact["value"]
    return {
        "intents": [objects["intent"][key] for key in sorted(objects["intent"])],
        "snaps": [objects["snap"][key] for key in sorted(objects["snap"])],
        "decisions": [objects["decision"][key] for key in sorted(objects["decision"])],
    }


def task_semantic_payload(task):
    ledger = task.get("atomic_fact_ledger")
    if ledger:
        return semantic_graph_from_ledger(ledger)
    return semantic_graph_payload(task.get("intent_context", {}))


def matched_fact_rows(payload):
    """Return the atomic field ledger shared by matched-flat and graph views."""
    return [
        (fact["id"], f"{fact['object_id']}.{fact['field']}", fact["value"])
        for fact in atomic_fact_ledger(payload)
        if fact.get("model_visible", False)
    ]


def write_intent_fixture(repo, context):
    """Materialize task semantic objects so inspect --full reads the product format."""
    base = Path(repo) / ".intent"
    for subdir in ("intents", "snaps", "decisions"):
        (base / subdir).mkdir(parents=True, exist_ok=True)

    objects = semantic_graph_payload(context)
    for subdir, rows in objects.items():
        for row in rows:
            payload = dict(row)
            path = base / subdir / f"{payload['id']}.json"
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def build_continuation_manifest(
    root,
    *,
    task_ids,
    conditions,
    repeat,
    runner,
    runner_isolation,
    model,
    reasoning_effort,
    seed,
    max_pairs,
    max_total_input_tokens,
    max_total_wall_seconds,
    timeout,
    plan,
    checkpoints,
):
    return {
        "schema": "intent-benchmark-suite-v2",
        "protocol": "continuation-only",
        "created_at": now_utc(),
        "status": "running",
        "intent_cli_version": __version__,
        "runner": runner,
        "runner_isolation": runner_isolation,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "seed": seed,
        "tasks": list(task_ids),
        "conditions": list(conditions),
        "repeat": repeat,
        "max_pairs": max_pairs,
        "max_total_input_tokens": max_total_input_tokens,
        "max_total_wall_seconds": max_total_wall_seconds,
        "timeout": timeout,
        "plan": plan,
        "checkpoints": checkpoints,
        "paths": {
            "root": str(root),
            "checkpoints": str(Path(root) / "checkpoints"),
            "tasks": str(Path(root) / "tasks"),
            "trials": str(Path(root) / "trials"),
            "manifest": str(Path(root) / "manifest.json"),
            "report": str(Path(root) / "report.json"),
        },
    }


def task_spec_sha256(task):
    payload = {key: value for key, value in task.items() if key != "_path"}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def collect_environment_metadata(*, real_codex):
    """Collect non-secret source and runner fingerprints for reproduction."""
    source_root = Path(__file__).resolve().parents[3]

    def git_output(*args):
        result = subprocess.run(
            ["git", *args],
            cwd=source_root,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    status = git_output("status", "--porcelain=v1")
    diff = git_output("diff", "--binary", "HEAD")
    prereg = source_root / "docs" / "benchmarks" / "continuation-benchmark-preregistration.md"
    source_codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    config_path = source_codex_home / "config.toml"
    config_text = config_path.read_text(encoding="utf-8") if config_path.is_file() else ""
    minimal_config = minimal_codex_config_text(config_text)

    codex_version = None
    if real_codex:
        try:
            result = subprocess.run(
                ["codex", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                codex_version = result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            codex_version = None

    return {
        "source_commit": git_output("rev-parse", "HEAD"),
        "source_dirty": bool(status),
        "source_status_sha256": sha256_text(status or ""),
        "source_diff_sha256": sha256_text(diff or ""),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "codex_cli": codex_version,
        "evaluator_read_isolation": (
            "darwin-sandbox-exec"
            if real_codex and sys.platform == "darwin"
            else "injected-runner"
        ),
        "runner_config_sha256": sha256_text(minimal_config),
        "preregistration_sha256": (
            hashlib.sha256(prereg.read_bytes()).hexdigest() if prereg.is_file() else None
        ),
    }


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def git_repo_output(repo, *args):
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise BenchError(f"Git command failed while freezing checkpoint: {' '.join(args)}")
    return result.stdout.strip()


def tree_sha256(repo):
    digest = hashlib.sha256()
    root = Path(repo)
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if rel.parts and rel.parts[0] in {".git", ".intent", ".benchmark"}:
            continue
        digest.update(str(rel).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _prepare_output_root(root, force=False):
    if root.exists():
        if not force:
            raise BenchError(f"Benchmark output already exists: {root}. Use --force to replace it.")
        if root.is_dir():
            shutil.rmtree(root)
        else:
            root.unlink()
    root.mkdir(parents=True, exist_ok=True)
