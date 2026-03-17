from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

from . import __version__
from .constants import EXIT_SUCCESS
from .core import IntentRepository
from .errors import IntentError


def emit(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))


def ok(action: str, result: Any, **extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"ok": True, "action": action, "result": result}
    payload.update(extra)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="itt",
        description="Intent CLI — semantic history for agents.",
    )
    parser.add_argument("--version", action="version", version=f"intent-cli {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, title="commands")

    sub.add_parser("version", help="Show version")

    sub.add_parser("init", help="Initialize Intent in the current Git repository")

    start_p = sub.add_parser("start", help="Create and activate an intent")
    start_p.add_argument("title")

    snap_p = sub.add_parser("snap", help="Record a checkpoint (adopted by default)")
    snap_p.add_argument("title")
    snap_p.add_argument("-m", "--message", help="Rationale for this checkpoint")
    snap_p.add_argument("--candidate", action="store_true", help="Record as candidate without adopting")

    adopt_p = sub.add_parser("adopt", help="Adopt a candidate checkpoint")
    adopt_p.add_argument("checkpoint_id", nargs="?")
    adopt_p.add_argument("-m", "--message", help="Rationale for adoption")

    revert_p = sub.add_parser("revert", help="Revert the latest adopted checkpoint")
    revert_p.add_argument("-m", "--message", help="Rationale for revert")

    done_p = sub.add_parser("done", help="Close the active intent")
    done_p.add_argument("intent_id", nargs="?")

    sub.add_parser("inspect", help="Machine-readable workspace snapshot")

    list_p = sub.add_parser("list", help="List objects")
    list_p.add_argument("type", choices=["intent", "checkpoint"])

    show_p = sub.add_parser("show", help="Show a single object by ID")
    show_p.add_argument("id")

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo = IntentRepository(Path.cwd())

    try:
        if args.command == "version":
            emit(ok("version", {"version": __version__}))
            return EXIT_SUCCESS

        if args.command == "init":
            repo.ensure_git()
            config, state = repo.init_workspace()
            emit(ok("init", {"config": config, "state": state}))
            return EXIT_SUCCESS

        if args.command == "start":
            intent, warnings = repo.create_intent(args.title)
            emit(ok("start", intent, warnings=warnings))
            return EXIT_SUCCESS

        if args.command == "snap":
            checkpoint, warnings = repo.create_checkpoint(
                args.title,
                rationale=args.message,
                candidate=args.candidate,
            )
            emit(ok("snap", checkpoint, warnings=warnings))
            return EXIT_SUCCESS

        if args.command == "adopt":
            checkpoint, warnings = repo.adopt_checkpoint(
                checkpoint_id=args.checkpoint_id,
                rationale=args.message,
            )
            emit(ok("adopt", checkpoint, warnings=warnings))
            return EXIT_SUCCESS

        if args.command == "revert":
            checkpoint, warnings = repo.revert_checkpoint(rationale=args.message)
            emit(ok("revert", checkpoint, warnings=warnings))
            return EXIT_SUCCESS

        if args.command == "done":
            intent, warnings = repo.close_intent(intent_id=args.intent_id)
            emit(ok("done", intent, warnings=warnings))
            return EXIT_SUCCESS

        if args.command == "inspect":
            emit(repo.inspect())
            return EXIT_SUCCESS

        if args.command == "list":
            items = repo.list_objects(args.type)
            emit(ok("list", items, count=len(items)))
            return EXIT_SUCCESS

        if args.command == "show":
            obj = repo.show_object(args.id)
            emit(ok("show", obj))
            return EXIT_SUCCESS

        parser.error("unknown command")
        return 2

    except IntentError as error:
        emit(error.to_json())
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
