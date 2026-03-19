"""Intent CLI — parser and command dispatch."""

import argparse
import sys

from intent_cli.commands.core import (
    cmd_decision_attach,
    cmd_decision_create,
    cmd_decision_deprecate,
    cmd_decision_list,
    cmd_decision_show,
    cmd_doctor,
    cmd_init,
    cmd_inspect,
    cmd_intent_activate,
    cmd_intent_create,
    cmd_intent_done,
    cmd_intent_list,
    cmd_intent_show,
    cmd_intent_suspend,
    cmd_snap_create,
    cmd_snap_feedback,
    cmd_snap_list,
    cmd_snap_revert,
    cmd_snap_show,
    cmd_version,
)
from intent_cli.commands.hub import cmd_hub_link, cmd_hub_login, cmd_hub_sync


def main():
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

    p = s_hub.add_parser("login")
    p.add_argument("--api-base-url", default=None)
    p.add_argument("--token", default=None)

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
    p.add_argument("title")
    p.add_argument("--query", default="")
    p.add_argument("--rationale", default="")

    p = s_intent.add_parser("list")
    p.add_argument("--status", default=None)
    p.add_argument("--decision", default=None)

    p = s_intent.add_parser("show")
    p.add_argument("id")

    p = s_intent.add_parser("activate")
    p.add_argument("id")

    p = s_intent.add_parser("suspend")
    p.add_argument("id")

    p = s_intent.add_parser("done")
    p.add_argument("id")

    # --- snap ---
    p_snap = sub.add_parser("snap")
    s_snap = p_snap.add_subparsers(dest="sub")

    p = s_snap.add_parser("create")
    p.add_argument("title")
    p.add_argument("--intent", required=True)
    p.add_argument("--query", default="")
    p.add_argument("--rationale", default="")
    p.add_argument("--summary", default="")
    p.add_argument("--feedback", default="")

    p = s_snap.add_parser("list")
    p.add_argument("--intent", default=None)
    p.add_argument("--status", default=None)

    p = s_snap.add_parser("show")
    p.add_argument("id")

    p = s_snap.add_parser("feedback")
    p.add_argument("id")
    p.add_argument("feedback")

    p = s_snap.add_parser("revert")
    p.add_argument("id")

    # --- decision ---
    p_decision = sub.add_parser("decision")
    s_decision = p_decision.add_subparsers(dest="sub")

    p = s_decision.add_parser("create")
    p.add_argument("title")
    p.add_argument("--rationale", default="")

    p = s_decision.add_parser("list")
    p.add_argument("--status", default=None)
    p.add_argument("--intent", default=None)

    p = s_decision.add_parser("show")
    p.add_argument("id")

    p = s_decision.add_parser("deprecate")
    p.add_argument("id")

    p = s_decision.add_parser("attach")
    p.add_argument("id")
    p.add_argument("--intent", required=True)

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
        ("hub", "login"):              cmd_hub_login,
        ("hub", "link"):               cmd_hub_link,
        ("hub", "sync"):               cmd_hub_sync,
        ("intent", "create"):          cmd_intent_create,
        ("intent", "list"):            cmd_intent_list,
        ("intent", "show"):            cmd_intent_show,
        ("intent", "activate"):        cmd_intent_activate,
        ("intent", "suspend"):         cmd_intent_suspend,
        ("intent", "done"):            cmd_intent_done,
        ("snap", "create"):            cmd_snap_create,
        ("snap", "list"):              cmd_snap_list,
        ("snap", "show"):              cmd_snap_show,
        ("snap", "feedback"):          cmd_snap_feedback,
        ("snap", "revert"):            cmd_snap_revert,
        ("decision", "create"):        cmd_decision_create,
        ("decision", "list"):          cmd_decision_list,
        ("decision", "show"):          cmd_decision_show,
        ("decision", "deprecate"):     cmd_decision_deprecate,
        ("decision", "attach"):        cmd_decision_attach,
    }
    dispatch[(args.command, args.sub)](args)
