"""Intent CLI — parser and command dispatch."""

import argparse
import sys

from intent_cli.benchmark.harness import ABLATIONS, CONDITIONS
from intent_cli.commands.benchmark import (
    cmd_benchmark_context,
    cmd_benchmark_list,
    cmd_benchmark_live_begin,
    cmd_benchmark_live_checkpoint,
    cmd_benchmark_live_handoff,
    cmd_benchmark_live_report,
    cmd_benchmark_live_score,
    cmd_benchmark_live_start,
    cmd_benchmark_materialize,
    cmd_benchmark_run,
    cmd_benchmark_score,
)
from intent_cli.commands.core import (
    cmd_decision_create,
    cmd_decision_deprecate,
    cmd_doctor,
    cmd_init,
    cmd_inspect,
    cmd_intent_activate,
    cmd_intent_create,
    cmd_intent_done,
    cmd_intent_suspend,
    cmd_snap_create,
    cmd_version,
)
from intent_cli.commands.hub import cmd_hub_link, cmd_hub_start, cmd_hub_sync


def _ensure_utf8_stdio():
    """Force UTF-8 on stdout/stderr so Windows doesn't fall back to GBK."""
    import io
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
        elif stream.encoding and stream.encoding.lower().replace("-", "") != "utf8":
            setattr(sys, stream_name, io.TextIOWrapper(
                stream.buffer, encoding="utf-8", errors="backslashreplace",
            ))


def main():
    _ensure_utf8_stdio()
    parser = argparse.ArgumentParser(prog="itt", description="Intent CLI")
    sub = parser.add_subparsers(dest="command")

    # version / init / inspect / doctor
    sub.add_parser("version")
    sub.add_parser("init")
    sub.add_parser("inspect")
    sub.add_parser("doctor")

    # --- hub ---
    p_hub = sub.add_parser("hub")
    s_hub = p_hub.add_subparsers(dest="sub")

    p = s_hub.add_parser("start")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--no-open", action="store_true")

    p = s_hub.add_parser("link")
    p.add_argument("--project-name", default=None)
    p.add_argument("--api-base-url", default=None)
    p.add_argument("--token", default=None)

    p = s_hub.add_parser("sync")
    p.add_argument("--api-base-url", default=None)
    p.add_argument("--token", default=None)
    p.add_argument("--dry-run", action="store_true")

    # --- benchmark ---
    p_benchmark = sub.add_parser(
        "benchmark",
        description="Run the automated benchmark. Omit the debug command to run the suite.",
    )
    p_benchmark.add_argument("--out", default=None)
    p_benchmark.add_argument("--runner", choices=["codex"], default="codex")
    p_benchmark.add_argument("--tasks", default=None, help="Comma-separated task IDs")
    p_benchmark.add_argument("--conditions", default=None, help="Comma-separated conditions")
    p_benchmark.add_argument("--repeat", type=int, default=1)
    p_benchmark.add_argument("--model", default=None)
    p_benchmark.add_argument("--timeout", type=float, default=None)
    p_benchmark.add_argument("--force", action="store_true")
    s_benchmark = p_benchmark.add_subparsers(dest="sub")

    s_benchmark.add_parser("list")

    p = s_benchmark.add_parser("materialize")
    p.add_argument("--task", required=True)
    p.add_argument("--stage", choices=["base", "after_a"], default="after_a")
    p.add_argument("--out", required=True)
    p.add_argument("--force", action="store_true")

    p = s_benchmark.add_parser("context")
    p.add_argument("--task", required=True)
    p.add_argument("--condition", choices=sorted(CONDITIONS), required=True)
    p.add_argument("--ablation", choices=sorted(ABLATIONS), default=None)
    p.add_argument("--out", default=None)

    p = s_benchmark.add_parser("score")
    p.add_argument("--task", required=True)
    p.add_argument("--repo", required=True)

    p_live = s_benchmark.add_parser("live")
    s_live = p_live.add_subparsers(dest="live_sub")

    p = s_live.add_parser("start")
    p.add_argument("--task", required=True)
    p.add_argument("--condition", choices=sorted(CONDITIONS), required=True)
    p.add_argument("--ablation", choices=sorted(ABLATIONS), default=None)
    p.add_argument("--out", required=True)
    p.add_argument("--force", action="store_true")

    p = s_live.add_parser("begin")
    p.add_argument("--run", required=True)
    p.add_argument("--phase", choices=["a", "b"], required=True)

    p = s_live.add_parser("checkpoint")
    p.add_argument("--run", required=True)

    p = s_live.add_parser("handoff")
    p.add_argument("--run", required=True)

    p = s_live.add_parser("score")
    p.add_argument("--run", required=True)

    p = s_live.add_parser("report")
    p.add_argument("--runs", required=True)

    # --- intent ---
    p_intent = sub.add_parser("intent")
    s_intent = p_intent.add_subparsers(dest="sub")

    p = s_intent.add_parser("create")
    p.add_argument("what", metavar="WHAT")
    p.add_argument("--why", default="")
    p.add_argument("--origin", default=None, metavar="LABEL")

    p = s_intent.add_parser("activate")
    p.add_argument("id", nargs="?")

    p = s_intent.add_parser("suspend")
    p.add_argument("id", nargs="?")

    p = s_intent.add_parser("done")
    p.add_argument("id", nargs="?")

    # --- snap ---
    p_snap = sub.add_parser("snap")
    s_snap = p_snap.add_subparsers(dest="sub")

    p = s_snap.add_parser("create")
    p.add_argument("what", metavar="WHAT")
    p.add_argument("--intent", default=None)
    p.add_argument("--why", default="")
    p.add_argument("--origin", default=None, metavar="LABEL")

    # --- decision ---
    p_decision = sub.add_parser("decision")
    s_decision = p_decision.add_subparsers(dest="sub")

    p = s_decision.add_parser("create")
    p.add_argument("what", metavar="WHAT")
    p.add_argument("--why", default="")
    p.add_argument("--origin", default=None, metavar="LABEL")

    p = s_decision.add_parser("deprecate")
    p.add_argument("id")
    p.add_argument("--reason", default="")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    dispatch_global = {
        "version": cmd_version,
        "init": cmd_init,
        "inspect": cmd_inspect,
        "doctor": cmd_doctor,
    }
    if args.command in dispatch_global:
        dispatch_global[args.command](args)
        return

    if args.command == "benchmark" and getattr(args, "sub", None) == "live" and not getattr(args, "live_sub", None):
        p_live.print_help()
        sys.exit(1)

    if args.command == "benchmark" and not getattr(args, "sub", None):
        cmd_benchmark_run(args)
        return

    if not getattr(args, "sub", None):
        {
            "hub": p_hub,
            "intent": p_intent,
            "snap": p_snap,
            "decision": p_decision,
        }[args.command].print_help()
        sys.exit(1)

    dispatch = {
        ("hub", "start"):              cmd_hub_start,
        ("hub", "link"):               cmd_hub_link,
        ("hub", "sync"):               cmd_hub_sync,
        ("benchmark", "list"):         cmd_benchmark_list,
        ("benchmark", "materialize"):  cmd_benchmark_materialize,
        ("benchmark", "context"):      cmd_benchmark_context,
        ("benchmark", "score"):        cmd_benchmark_score,
        ("benchmark", ("live", "start")):       cmd_benchmark_live_start,
        ("benchmark", ("live", "begin")):       cmd_benchmark_live_begin,
        ("benchmark", ("live", "checkpoint")):  cmd_benchmark_live_checkpoint,
        ("benchmark", ("live", "handoff")):     cmd_benchmark_live_handoff,
        ("benchmark", ("live", "score")):       cmd_benchmark_live_score,
        ("benchmark", ("live", "report")):      cmd_benchmark_live_report,
        ("intent", "create"):          cmd_intent_create,
        ("intent", "activate"):        cmd_intent_activate,
        ("intent", "suspend"):         cmd_intent_suspend,
        ("intent", "done"):            cmd_intent_done,
        ("snap", "create"):            cmd_snap_create,
        ("decision", "create"):        cmd_decision_create,
        ("decision", "deprecate"):     cmd_decision_deprecate,
    }
    dispatch_key = (args.command, (args.sub, args.live_sub)) if args.command == "benchmark" and args.sub == "live" else (args.command, args.sub)
    dispatch[dispatch_key](args)
