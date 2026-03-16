from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .core import (
    EXIT_SUCCESS,
    IntentError,
    IntentRepository,
    build_git_context,
    object_brief,
    summarize_git,
    write_result,
)


def emit_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))


def emit_error(error: IntentError, *, as_json: bool) -> int:
    if as_json:
        emit_json(error.to_json())
    else:
        lines = [error.message, f"Error: {error.code}"]
        if error.suggested_fix:
            lines.append(f"Next: {error.suggested_fix}")
        print("\n".join(lines), file=sys.stderr)
    return error.exit_code


def base_write_parser(name: str, help_text: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--json", action="store_true", help=help_text)
    parser.add_argument("--id-only", action="store_true")
    parser.add_argument("--no-interactive", action="store_true")
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="itt")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--json", action="store_true")
    init_parser.add_argument("--no-interactive", action="store_true")

    start_parser = subparsers.add_parser("start", parents=[base_write_parser("start", "Emit machine-readable JSON")])
    start_parser.add_argument("title")

    snap_parser = subparsers.add_parser("snap", parents=[base_write_parser("snap", "Emit machine-readable JSON")])
    snap_parser.add_argument("title")

    adopt_parser = subparsers.add_parser("adopt", parents=[base_write_parser("adopt", "Emit machine-readable JSON")])
    adopt_parser.add_argument("-m", "--message")
    adopt_parser.add_argument("--because", default="")
    adopt_parser.add_argument("--checkpoint")
    adopt_parser.add_argument("--if-not-adopted", action="store_true")
    adopt_parser.add_argument("--link-git")

    revert_parser = subparsers.add_parser("revert", parents=[base_write_parser("revert", "Emit machine-readable JSON")])
    revert_parser.add_argument("-m", "--message")
    revert_parser.add_argument("--because", default="")

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--json", action="store_true")

    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("--json", action="store_true")

    log_parser = subparsers.add_parser("log")

    checkpoint_parser = subparsers.add_parser("checkpoint")
    checkpoint_subparsers = checkpoint_parser.add_subparsers(dest="checkpoint_command", required=True)
    checkpoint_create_parser = checkpoint_subparsers.add_parser(
        "create",
        parents=[base_write_parser("checkpoint create", "Emit machine-readable JSON")],
    )
    checkpoint_create_parser.add_argument("--title", required=True)
    checkpoint_create_parser.add_argument("--select", action="store_true")
    select_parser = checkpoint_subparsers.add_parser(
        "select",
        parents=[base_write_parser("checkpoint select", "Emit machine-readable JSON")],
    )
    select_parser.add_argument("checkpoint_id")

    intent_parser = subparsers.add_parser("intent")
    intent_subparsers = intent_parser.add_subparsers(dest="intent_command", required=True)
    intent_create_parser = intent_subparsers.add_parser(
        "create",
        parents=[base_write_parser("intent create", "Emit machine-readable JSON")],
    )
    intent_create_parser.add_argument("--title", required=True)
    intent_create_parser.add_argument("--activate", action="store_true")

    adoption_parser = subparsers.add_parser("adoption")
    adoption_subparsers = adoption_parser.add_subparsers(dest="adoption_command", required=True)
    adoption_create_parser = adoption_subparsers.add_parser(
        "create",
        parents=[base_write_parser("adoption create", "Emit machine-readable JSON")],
    )
    adoption_create_parser.add_argument("--title")
    adoption_create_parser.add_argument("--because", default="")
    adoption_create_parser.add_argument("--checkpoint")
    adoption_create_parser.add_argument("--if-not-adopted", action="store_true")
    adoption_create_parser.add_argument("--link-git")
    adoption_revert_parser = adoption_subparsers.add_parser(
        "revert",
        parents=[base_write_parser("adoption revert", "Emit machine-readable JSON")],
    )
    adoption_revert_parser.add_argument("--title")
    adoption_revert_parser.add_argument("--because", default="")

    return parser


def handle_init(repo: IntentRepository, args: argparse.Namespace) -> int:
    repo.ensure_git()
    git_context, _ = build_git_context(repo.cwd)
    config, state = repo.init_workspace()
    if args.json:
        emit_json(
            write_result(
                "workspace",
                "init",
                None,
                {"config": config, "state": state},
                [],
                next_action={"command": 'itt start "Describe the problem"', "reason": "Workspace initialized"},
            )
        )
        return EXIT_SUCCESS

    print("Initialized Intent in .intent/")
    print(f"Git: {summarize_git(git_context)}")
    print('Next: itt start "Describe the problem"')
    return EXIT_SUCCESS


def handle_start(repo: IntentRepository, args: argparse.Namespace) -> int:
    intent, _, warnings = repo.create_intent(args.title)
    if args.id_only:
        print(intent["id"])
        return EXIT_SUCCESS
    if args.json:
        emit_json(
            write_result(
                "intent",
                "create",
                intent["id"],
                intent,
                warnings,
                next_action={"command": 'itt snap "First candidate"', "reason": "Intent created and activated"},
            )
        )
        return EXIT_SUCCESS

    print(f"Started intent {intent['id']}")
    print(f"Title: {intent['title']}")
    print("Status: intent_active")
    print('Next: itt snap "First candidate"')
    return EXIT_SUCCESS


def handle_snap(repo: IntentRepository, args: argparse.Namespace) -> int:
    checkpoint, _, warnings = repo.create_checkpoint(args.title)
    if args.id_only:
        print(checkpoint["id"])
        return EXIT_SUCCESS
    if args.json:
        emit_json(
            write_result(
                "checkpoint",
                "create",
                checkpoint["id"],
                checkpoint,
                warnings,
                next_action={"command": 'itt adopt -m "Adopt candidate"', "reason": "Checkpoint created and selected"},
            )
        )
        return EXIT_SUCCESS

    intent = repo.require_object("intent", checkpoint["intent_id"])
    print(f"Saved checkpoint {checkpoint['id']}")
    print(f"Intent: {intent['id']}  {intent['title']}")
    print(f"Checkpoint: {checkpoint['title']}")
    print(f"Git: {summarize_git(checkpoint['git'])}")
    print('Next: itt adopt -m "Adopt progressive disclosure layout"')
    return EXIT_SUCCESS


def handle_adopt(repo: IntentRepository, args: argparse.Namespace) -> int:
    adoption, _, warnings, noop = repo.create_adoption(
        args.message,
        args.checkpoint,
        args.because,
        args.if_not_adopted,
        args.link_git,
    )
    if args.id_only:
        print(adoption["id"])
        return EXIT_SUCCESS
    if args.json:
        if noop:
            emit_json(
                write_result(
                    "adoption",
                    "create",
                    adoption["id"],
                    adoption,
                    warnings,
                    next_action={"command": "itt log", "reason": "Checkpoint was already adopted"},
                    state_changed=False,
                    noop=True,
                    reason="Checkpoint already adopted",
                )
            )
        else:
            emit_json(
                write_result(
                    "adoption",
                    "create",
                    adoption["id"],
                    adoption,
                    warnings,
                    next_action={"command": "itt log", "reason": "Adoption recorded"},
                )
            )
        return EXIT_SUCCESS

    checkpoint = repo.require_object("checkpoint", adoption["checkpoint_id"])
    intent = repo.require_object("intent", adoption["intent_id"])
    print(f"Adopted checkpoint {checkpoint['id']}")
    print(f"Intent: {intent['id']}  {intent['title']}")
    print(f"Adoption: {adoption['id']}  {adoption['title']}")
    print(f"Git: {adoption['git'].get('head') or 'no-commit'}")
    print("Next: itt log")
    return EXIT_SUCCESS


def handle_revert(repo: IntentRepository, args: argparse.Namespace) -> int:
    adoption, _, warnings = repo.revert_adoption(args.message, args.because)
    if args.id_only:
        print(adoption["id"])
        return EXIT_SUCCESS
    if args.json:
        emit_json(
            write_result(
                "adoption",
                "revert",
                adoption["id"],
                adoption,
                warnings,
                next_action={"command": "itt log", "reason": "Revert recorded"},
            )
        )
        return EXIT_SUCCESS

    checkpoint = repo.require_object("checkpoint", adoption["checkpoint_id"])
    intent = repo.require_object("intent", adoption["intent_id"])
    reverted = adoption["reverts_adoption_id"] or "unknown"
    print(f"Reverted adoption {reverted}")
    print(f"Intent: {intent['id']}  {intent['title']}")
    print(f"Checkpoint: {checkpoint['id']}  {checkpoint['title']}")
    print(f"Adoption: {adoption['id']}  {adoption['title']}")
    print("Next: itt log")
    return EXIT_SUCCESS


def handle_status(repo: IntentRepository, args: argparse.Namespace) -> int:
    if args.json:
        emit_json(repo.status_json())
    else:
        print(repo.render_status_text())
    return EXIT_SUCCESS


def handle_inspect(repo: IntentRepository, args: argparse.Namespace) -> int:
    emit_json(repo.inspect_json())
    return EXIT_SUCCESS


def handle_log(repo: IntentRepository, args: argparse.Namespace) -> int:
    print(repo.render_log_text())
    return EXIT_SUCCESS


def normalize_canonical_args(args: argparse.Namespace) -> argparse.Namespace:
    if args.command == "intent" and args.intent_command == "create":
        args.command = "start"
        args.title = args.title
        return args

    if args.command == "checkpoint" and args.checkpoint_command == "create":
        args.command = "snap"
        args.title = args.title
        return args

    if args.command == "adoption" and args.adoption_command == "create":
        args.command = "adopt"
        args.message = args.title
        return args

    if args.command == "adoption" and args.adoption_command == "revert":
        args.command = "revert"
        args.message = args.title
        return args

    return args


def handle_checkpoint_select(repo: IntentRepository, args: argparse.Namespace) -> int:
    checkpoint, _, warnings = repo.select_checkpoint(args.checkpoint_id)
    if args.id_only:
        print(checkpoint["id"])
        return EXIT_SUCCESS
    if args.json:
        emit_json(
            write_result(
                "checkpoint",
                "select",
                checkpoint["id"],
                checkpoint,
                warnings,
                next_action={"command": 'itt adopt -m "Adopt candidate"', "reason": "Checkpoint selected"},
            )
        )
        return EXIT_SUCCESS

    print(f"Selected checkpoint {checkpoint['id']}")
    print(f"Checkpoint: {checkpoint['title']}")
    print('Next: itt adopt -m "Adopt candidate"')
    return EXIT_SUCCESS


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args = normalize_canonical_args(args)
    repo = IntentRepository(Path.cwd())
    wants_json = bool(getattr(args, "json", False))

    try:
        if args.command == "init":
            return handle_init(repo, args)
        if args.command == "start":
            return handle_start(repo, args)
        if args.command == "snap":
            return handle_snap(repo, args)
        if args.command == "adopt":
            return handle_adopt(repo, args)
        if args.command == "revert":
            return handle_revert(repo, args)
        if args.command == "status":
            return handle_status(repo, args)
        if args.command == "inspect":
            return handle_inspect(repo, args)
        if args.command == "log":
            return handle_log(repo, args)
        if args.command == "checkpoint" and args.checkpoint_command == "select":
            return handle_checkpoint_select(repo, args)
        parser.error("unknown command")
        return 2
    except IntentError as error:
        return emit_error(error, as_json=wants_json)


if __name__ == "__main__":
    raise SystemExit(main())
