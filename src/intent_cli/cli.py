"""Intent CLI — parser and command dispatch."""

import argparse
import sys

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

    # --- intent ---
    p_intent = sub.add_parser("intent")
    s_intent = p_intent.add_subparsers(dest="sub")

    p = s_intent.add_parser("create")
    p.add_argument("what", metavar="WHAT")
    p.add_argument("--query", default="")
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
    p.add_argument("--query", default="")
    p.add_argument("--why", required=True)
    p.add_argument("--next", default="", dest="next_step")
    p.add_argument("--origin", default=None, metavar="LABEL")

    # --- decision ---
    p_decision = sub.add_parser("decision")
    s_decision = p_decision.add_subparsers(dest="sub")

    p = s_decision.add_parser("create")
    p.add_argument("what", metavar="WHAT")
    p.add_argument("--query", default="")
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
        ("intent", "create"):          cmd_intent_create,
        ("intent", "activate"):        cmd_intent_activate,
        ("intent", "suspend"):         cmd_intent_suspend,
        ("intent", "done"):            cmd_intent_done,
        ("snap", "create"):            cmd_snap_create,
        ("decision", "create"):        cmd_decision_create,
        ("decision", "deprecate"):     cmd_decision_deprecate,
    }
    dispatch[(args.command, args.sub)](args)
