"""Benchmark command handlers."""

from intent_cli.benchmark.continuation import run_continuation_suite
from intent_cli.benchmark.harness import (
    BenchError,
    build_context,
    list_task_rows,
    live_begin,
    live_checkpoint,
    live_handoff,
    live_report,
    live_score,
    live_start,
    materialize_task,
    run_benchmark_suite,
    score_task_repo,
)
from intent_cli.output import error, success


def _run(action):
    try:
        return action()
    except BenchError as exc:
        error(
            "BENCHMARK_ERROR",
            str(exc),
            suggested_fix="Run: itt benchmark list",
        )


def _split_csv(value):
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def cmd_benchmark_run(args):
    run_suite = run_continuation_suite if args.protocol == "continuation" else run_benchmark_suite
    continuation_options = {
        "stage": args.stage,
        "confirmation_lock": args.confirmation_lock,
        "seed": args.seed,
        "max_pairs": args.max_pairs,
        "max_total_input_tokens": args.max_total_input_tokens,
        "max_total_wall_seconds": args.max_total_wall_seconds,
    } if args.protocol == "continuation" else {}
    result = _run(
        lambda: run_suite(
            out_dir=args.out,
            tasks=_split_csv(args.tasks),
            conditions=_split_csv(args.conditions),
            repeat=args.repeat,
            runner=args.runner,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            force=args.force,
            timeout=args.timeout,
            **continuation_options,
        )
    )
    success("benchmark.run", result)


def cmd_benchmark_list(_args):
    result = _run(lambda: {"tasks": list_task_rows()})
    success("benchmark.list", result)


def cmd_benchmark_materialize(args):
    result = _run(
        lambda: materialize_task(
            task_id=args.task,
            stage=args.stage,
            out_dir=args.out,
            force=args.force,
        )
    )
    success("benchmark.materialize", result)


def cmd_benchmark_context(args):
    result = _run(
        lambda: build_context(
            task_id=args.task,
            condition=args.condition,
            ablation=args.ablation,
            out_path=args.out,
        )
    )
    if args.out:
        success("benchmark.context", result)
    else:
        print(result["content"], end="")


def cmd_benchmark_score(args):
    result = _run(lambda: score_task_repo(args.task, args.repo))
    success("benchmark.score", result)


def cmd_benchmark_live_start(args):
    result = _run(
        lambda: live_start(
            task_id=args.task,
            condition=args.condition,
            out_dir=args.out,
            ablation=args.ablation,
            force=args.force,
        )
    )
    success("benchmark.live.start", result)


def cmd_benchmark_live_begin(args):
    result = _run(lambda: live_begin(args.run, args.phase))
    success("benchmark.live.begin", result)


def cmd_benchmark_live_checkpoint(args):
    result = _run(lambda: live_checkpoint(args.run))
    success("benchmark.live.checkpoint", result)


def cmd_benchmark_live_handoff(args):
    result = _run(lambda: live_handoff(args.run))
    success("benchmark.live.handoff", result)


def cmd_benchmark_live_score(args):
    result = _run(lambda: live_score(args.run))
    success("benchmark.live.score", result)


def cmd_benchmark_live_report(args):
    result = _run(lambda: live_report(args.runs))
    success("benchmark.live.report", result)
