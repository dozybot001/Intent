from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional

from . import __version__
from .constants import EXIT_GENERAL_FAILURE, EXIT_SUCCESS
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

    snap_p = sub.add_parser("snap", help="Record a snap (adopted by default)")
    snap_p.add_argument("title")
    snap_p.add_argument("-m", "--message", help="Rationale for this snap")
    snap_p.add_argument("--candidate", action="store_true", help="Record as candidate without adopting")

    adopt_p = sub.add_parser("adopt", help="Adopt a candidate snap")
    adopt_p.add_argument("snap_id", nargs="?")
    adopt_p.add_argument("-m", "--message", help="Rationale for adoption")

    revert_p = sub.add_parser("revert", help="Revert the latest adopted snap")
    revert_p.add_argument("-m", "--message", help="Rationale for revert")

    sub.add_parser("suspend", help="Suspend the active intent")

    resume_p = sub.add_parser("resume", help="Resume a suspended intent")
    resume_p.add_argument("intent_id", nargs="?")

    done_p = sub.add_parser("done", help="Close the active intent")
    done_p.add_argument("intent_id", nargs="?")

    sub.add_parser("inspect", help="Machine-readable workspace snapshot")

    list_p = sub.add_parser("list", help="List objects")
    list_p.add_argument("type", choices=["intent", "snap"])

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
            snap, warnings = repo.create_snap(
                args.title,
                rationale=args.message,
                candidate=args.candidate,
            )
            emit(ok("snap", snap, warnings=warnings))
            return EXIT_SUCCESS

        if args.command == "adopt":
            snap, warnings = repo.adopt_snap(
                snap_id=args.snap_id,
                rationale=args.message,
            )
            emit(ok("adopt", snap, warnings=warnings))
            return EXIT_SUCCESS

        if args.command == "revert":
            snap, warnings = repo.revert_snap(rationale=args.message)
            emit(ok("revert", snap, warnings=warnings))
            return EXIT_SUCCESS

        if args.command == "suspend":
            intent, warnings = repo.suspend_intent()
            emit(ok("suspend", intent, warnings=warnings))
            return EXIT_SUCCESS

        if args.command == "resume":
            intent, warnings = repo.resume_intent(intent_id=args.intent_id)
            emit(ok("resume", intent, warnings=warnings))
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
    except Exception as error:
        emit({
            "ok": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(error),
                "details": {},
            },
        })
        return EXIT_GENERAL_FAILURE


if __name__ == "__main__":
    raise SystemExit(main())
