from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from . import __version__
from .constants import EXIT_SUCCESS
from .core import IntentRepository
from .distribution import (
    doctor_exit_code,
    doctor_report,
    format_doctor_text,
    format_integrations_text,
    format_setup_text,
    list_integrations,
    normalize_agent_name,
    setup_integration,
)
from .errors import IntentError
from .git import build_git_context, summarize_git
from .helpers import cli_action, write_result


def emit_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2))


def error_detail_lines(error: IntentError) -> list[str]:
    lines: list[str] = []
    candidates = error.details.get("candidate_checkpoints")
    if candidates:
        lines.append("Candidates:")
        for checkpoint in candidates:
            lines.append(f"- {checkpoint['id']}: {checkpoint['title']}")
    return lines


def emit_error(error: IntentError, *, as_json: bool) -> int:
    if as_json:
        emit_json(error.to_json())
    else:
        lines = [error.message, f"Error: {error.code}"]
        lines.extend(error_detail_lines(error))
        if error.suggested_fix:
            lines.append(f"Next: {error.suggested_fix}")
        print("\n".join(lines), file=sys.stderr)
    return error.exit_code


def workspace_result_fields(repo: IntentRepository) -> Dict[str, Any]:
    snapshot = repo.snapshot()
    return {
        "workspace_status": snapshot.state["workspace_status"],
        "workspace_status_reason": repo.workspace_status_reason(snapshot),
    }


def current_machine_next_action(repo: IntentRepository) -> Optional[Dict[str, Any]]:
    snapshot = repo.snapshot()
    return repo.next_action(snapshot, machine=True)


def base_write_parser(name: str, help_text: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--json", action="store_true", help=help_text)
    parser.add_argument("--id-only", action="store_true")
    parser.add_argument("--no-interactive", action="store_true")
    return parser


def base_read_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--json", action="store_true")
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="itt",
        description="Intent CLI records semantic history on top of Git.",
    )
    parser.add_argument("--version", action="version", version=f"intent-cli {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True, title="commands")

    version_parser = subparsers.add_parser("version", help="Show the CLI version")
    version_parser.add_argument("--json", action="store_true")

    init_parser = subparsers.add_parser("init", help="Initialize Intent in the current Git repository")
    init_parser.add_argument("--json", action="store_true")
    init_parser.add_argument("--no-interactive", action="store_true")

    start_parser = subparsers.add_parser(
        "start",
        parents=[base_write_parser("start", "Emit machine-readable JSON")],
        help="Create and activate an intent",
    )
    start_parser.add_argument("title")

    snap_parser = subparsers.add_parser(
        "snap",
        parents=[base_write_parser("snap", "Emit machine-readable JSON")],
        help="Create and select a candidate checkpoint",
    )
    snap_parser.add_argument("title")

    adopt_parser = subparsers.add_parser(
        "adopt",
        parents=[base_write_parser("adopt", "Emit machine-readable JSON")],
        help="Create an adoption record for a checkpoint",
    )
    adopt_parser.add_argument("-m", "--message")
    adopt_parser.add_argument("--because", default="")
    adopt_parser.add_argument("--checkpoint")
    adopt_parser.add_argument("--if-not-adopted", action="store_true")
    adopt_parser.add_argument("--link-git")

    revert_parser = subparsers.add_parser(
        "revert",
        parents=[base_write_parser("revert", "Emit machine-readable JSON")],
        help="Record a revert against the latest active adoption",
    )
    revert_parser.add_argument("-m", "--message")
    revert_parser.add_argument("--because", default="")

    status_parser = subparsers.add_parser("status", help="Show the current workspace summary")
    status_parser.add_argument("--json", action="store_true")

    inspect_parser = subparsers.add_parser("inspect", help="Return a machine-readable workspace snapshot")
    inspect_parser.add_argument("--json", action="store_true")

    log_parser = subparsers.add_parser("log", help="Show semantic history for humans")

    setup_parser = subparsers.add_parser(
        "setup",
        help="Install or stage agent-specific Intent setup assets from the local Intent checkout",
    )
    setup_parser.add_argument("agent_target", nargs="?")
    setup_parser.add_argument("--agent", dest="agent_flag")
    setup_parser.add_argument("--json", action="store_true")

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Verify local checkout-backed agent setup health and remaining manual steps",
    )
    doctor_parser.add_argument("--agent")
    doctor_parser.add_argument("--json", action="store_true")

    integrations_parser = subparsers.add_parser("integrations", help="Read integration metadata")
    integrations_subparsers = integrations_parser.add_subparsers(
        dest="integrations_command",
        required=True,
        title="integration commands",
    )
    integrations_subparsers.add_parser("list", parents=[base_read_parser()], help="List supported integrations")

    config_parser = subparsers.add_parser("config", help="Read workspace configuration")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True, title="config commands")
    config_subparsers.add_parser("show", parents=[base_read_parser()], help="Show the current config")

    checkpoint_parser = subparsers.add_parser("checkpoint", help="Read or manage checkpoints")
    checkpoint_subparsers = checkpoint_parser.add_subparsers(
        dest="checkpoint_command", required=True, title="checkpoint commands"
    )
    checkpoint_subparsers.add_parser("list", parents=[base_read_parser()], help="List checkpoints")
    checkpoint_show_parser = checkpoint_subparsers.add_parser("show", parents=[base_read_parser()], help="Show a checkpoint")
    checkpoint_show_parser.add_argument("checkpoint_id")
    checkpoint_create_parser = checkpoint_subparsers.add_parser(
        "create",
        parents=[base_write_parser("checkpoint create", "Emit machine-readable JSON")],
        help="Create a checkpoint",
    )
    checkpoint_create_parser.add_argument("--title", required=True)
    checkpoint_create_parser.add_argument("--select", action="store_true")
    select_parser = checkpoint_subparsers.add_parser(
        "select",
        parents=[base_write_parser("checkpoint select", "Emit machine-readable JSON")],
        help="Select the current checkpoint",
    )
    select_parser.add_argument("checkpoint_id")

    intent_parser = subparsers.add_parser("intent", help="Read or manage intents")
    intent_subparsers = intent_parser.add_subparsers(dest="intent_command", required=True, title="intent commands")
    intent_subparsers.add_parser("list", parents=[base_read_parser()], help="List intents")
    intent_show_parser = intent_subparsers.add_parser("show", parents=[base_read_parser()], help="Show an intent")
    intent_show_parser.add_argument("intent_id")
    intent_create_parser = intent_subparsers.add_parser(
        "create",
        parents=[base_write_parser("intent create", "Emit machine-readable JSON")],
        help="Create an intent",
    )
    intent_create_parser.add_argument("--title", required=True)
    intent_create_parser.add_argument("--activate", action="store_true")

    adoption_parser = subparsers.add_parser("adoption", help="Read or manage adoptions")
    adoption_subparsers = adoption_parser.add_subparsers(
        dest="adoption_command", required=True, title="adoption commands"
    )
    adoption_subparsers.add_parser("list", parents=[base_read_parser()], help="List adoptions")
    adoption_show_parser = adoption_subparsers.add_parser("show", parents=[base_read_parser()], help="Show an adoption")
    adoption_show_parser.add_argument("adoption_id")
    adoption_create_parser = adoption_subparsers.add_parser(
        "create",
        parents=[base_write_parser("adoption create", "Emit machine-readable JSON")],
        help="Create an adoption",
    )
    adoption_create_parser.add_argument("--title")
    adoption_create_parser.add_argument("--because", default="")
    adoption_create_parser.add_argument("--checkpoint")
    adoption_create_parser.add_argument("--if-not-adopted", action="store_true")
    adoption_create_parser.add_argument("--link-git")
    adoption_revert_parser = adoption_subparsers.add_parser(
        "revert",
        parents=[base_write_parser("adoption revert", "Emit machine-readable JSON")],
        help="Create a revert adoption record",
    )
    adoption_revert_parser.add_argument("--title")
    adoption_revert_parser.add_argument("--because", default="")

    run_parser = subparsers.add_parser("run", help="Read or manage runs")
    run_subparsers = run_parser.add_subparsers(dest="run_command", required=True, title="run commands")
    run_subparsers.add_parser("list", parents=[base_read_parser()], help="List runs")
    run_show_parser = run_subparsers.add_parser("show", parents=[base_read_parser()], help="Show a run")
    run_show_parser.add_argument("run_id")
    run_start_parser = run_subparsers.add_parser(
        "start",
        parents=[base_write_parser("run start", "Emit machine-readable JSON")],
        help="Start a run",
    )
    run_start_parser.add_argument("--title")
    run_subparsers.add_parser(
        "end",
        parents=[base_write_parser("run end", "Emit machine-readable JSON")],
        help="End the active run",
    )

    decide_parser = subparsers.add_parser(
        "decide",
        parents=[base_write_parser("decide", "Emit machine-readable JSON")],
        help="Record a decision",
    )
    decide_parser.add_argument("title")
    decide_parser.add_argument("--because", default="")
    decide_parser.add_argument("--adoption")

    decision_parser = subparsers.add_parser("decision", help="Read or manage decisions")
    decision_subparsers = decision_parser.add_subparsers(
        dest="decision_command", required=True, title="decision commands"
    )
    decision_subparsers.add_parser("list", parents=[base_read_parser()], help="List decisions")
    decision_show_parser = decision_subparsers.add_parser("show", parents=[base_read_parser()], help="Show a decision")
    decision_show_parser.add_argument("decision_id")
    decision_create_parser = decision_subparsers.add_parser(
        "create",
        parents=[base_write_parser("decision create", "Emit machine-readable JSON")],
        help="Create a decision",
    )
    decision_create_parser.add_argument("--title", required=True)
    decision_create_parser.add_argument("--because", default="")
    decision_create_parser.add_argument("--adoption")

    return parser


def handle_init(repo: IntentRepository, args: argparse.Namespace) -> int:
    repo.ensure_git()
    git_context, _ = build_git_context(repo.cwd)
    config, state = repo.init_workspace()
    if args.json:
        workspace_fields = workspace_result_fields(repo)
        emit_json(
            write_result(
                "workspace",
                "init",
                None,
                {"config": config, "state": state},
                [],
                next_action=cli_action(["start", "Describe the problem"], "Workspace initialized"),
                **workspace_fields,
            )
        )
        return EXIT_SUCCESS

    print("Initialized Intent in .intent/")
    print(f"Git: {summarize_git(git_context)}")
    print('Next: itt start "Describe the problem"')
    return EXIT_SUCCESS


def handle_version(args: argparse.Namespace) -> int:
    if args.json:
        emit_json(
            {
                "ok": True,
                "object": "version",
                "version": __version__,
            }
        )
        return EXIT_SUCCESS

    print(f"intent-cli {__version__}")
    return EXIT_SUCCESS


def handle_start(repo: IntentRepository, args: argparse.Namespace) -> int:
    intent, _, warnings = repo.create_intent(args.title)
    if args.id_only:
        print(intent["id"])
        return EXIT_SUCCESS
    if args.json:
        workspace_fields = workspace_result_fields(repo)
        emit_json(
            write_result(
                "intent",
                "create",
                intent["id"],
                intent,
                warnings,
                next_action=cli_action(["snap", "First candidate"], "Intent created and activated"),
                **workspace_fields,
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
        workspace_fields = workspace_result_fields(repo)
        emit_json(
            write_result(
                "checkpoint",
                "create",
                checkpoint["id"],
                checkpoint,
                warnings,
                next_action=cli_action(
                    ["adopt", "--checkpoint", checkpoint["id"], "-m", "Adopt candidate"],
                    "Checkpoint created and selected",
                ),
                **workspace_fields,
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
        workspace_fields = workspace_result_fields(repo)
        if noop:
            emit_json(
                write_result(
                    "adoption",
                    "create",
                    adoption["id"],
                    adoption,
                    warnings,
                    next_action=cli_action(["log"], "Checkpoint was already adopted"),
                    state_changed=False,
                    noop=True,
                    reason="Checkpoint already adopted",
                    **workspace_fields,
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
                    next_action=cli_action(["log"], "Adoption recorded"),
                    **workspace_fields,
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
        workspace_fields = workspace_result_fields(repo)
        emit_json(
            write_result(
                "adoption",
                "revert",
                adoption["id"],
                adoption,
                warnings,
                next_action=cli_action(["log"], "Revert recorded"),
                **workspace_fields,
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


def handle_run_start(repo: IntentRepository, args: argparse.Namespace) -> int:
    run, _, warnings = repo.create_run(args.title)
    if args.id_only:
        print(run["id"])
        return EXIT_SUCCESS
    if args.json:
        workspace_fields = workspace_result_fields(repo)
        emit_json(
            write_result(
                "run",
                "start",
                run["id"],
                run,
                warnings,
                next_action=current_machine_next_action(repo),
                **workspace_fields,
            )
        )
        return EXIT_SUCCESS

    print(f"Started run {run['id']}")
    print(f"Title: {run['title']}")
    next_action = current_machine_next_action(repo)
    if next_action:
        print(f"Next: {next_action['command']}")
    return EXIT_SUCCESS


def handle_run_end(repo: IntentRepository, args: argparse.Namespace) -> int:
    run, _, warnings = repo.end_run()
    if args.id_only:
        print(run["id"])
        return EXIT_SUCCESS
    if args.json:
        workspace_fields = workspace_result_fields(repo)
        emit_json(
            write_result(
                "run",
                "end",
                run["id"],
                run,
                warnings,
                next_action=current_machine_next_action(repo),
                **workspace_fields,
            )
        )
        return EXIT_SUCCESS

    print(f"Ended run {run['id']}")
    print(f"Title: {run['title']}")
    next_action = current_machine_next_action(repo)
    if next_action:
        print(f"Next: {next_action['command']}")
    return EXIT_SUCCESS


def handle_decide(repo: IntentRepository, args: argparse.Namespace) -> int:
    decision, _, warnings = repo.create_decision(args.title, args.because, args.adoption)
    if args.id_only:
        print(decision["id"])
        return EXIT_SUCCESS
    if args.json:
        workspace_fields = workspace_result_fields(repo)
        emit_json(
            write_result(
                "decision",
                "create",
                decision["id"],
                decision,
                warnings,
                next_action=current_machine_next_action(repo),
                **workspace_fields,
            )
        )
        return EXIT_SUCCESS

    print(f"Recorded decision {decision['id']}")
    print(f"Title: {decision['title']}")
    if decision.get("adoption_id"):
        print(f"Adoption: {decision['adoption_id']}")
    next_action = current_machine_next_action(repo)
    if next_action:
        print(f"Next: {next_action['command']}")
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


def resolve_setup_agent(args: argparse.Namespace) -> str:
    target = args.agent_target
    flag = args.agent_flag
    if target and flag and target.lower() != flag.lower():
        raise IntentError(
            2,
            "INVALID_INPUT",
            "Conflicting setup targets were provided.",
            details={"agent_target": target, "agent_flag": flag},
            suggested_fix="Use either a positional target or --agent, but not both.",
        )
    return normalize_agent_name(flag or target or "auto")


def handle_setup(args: argparse.Namespace) -> int:
    requested_agent = resolve_setup_agent(args)
    result, warnings, state_changed, noop, reason = setup_integration(requested_agent)
    next_action = None
    if result["selected_agent"] is None:
        next_action = cli_action(["integrations", "list"], "Inspect detected agents and explicit setup options")
    elif result.get("install_mode") == "skill_dir":
        next_action = cli_action(["doctor", "--agent", result["selected_agent"]], "Verify the installed skill")

    if args.json:
        emit_json(
            write_result(
                "integration",
                "setup",
                result["selected_agent"],
                result,
                warnings,
                next_action=next_action,
                state_changed=state_changed,
                noop=noop,
                reason=reason,
            )
        )
        return EXIT_SUCCESS

    print(format_setup_text(result, reason))
    return EXIT_SUCCESS


def handle_doctor(args: argparse.Namespace) -> int:
    payload = doctor_report(args.agent)
    if args.json:
        emit_json(
            {
                "ok": payload["healthy"],
                "object": "doctor",
                "action": "check",
                "result": payload,
                "warnings": payload["warnings"],
            }
        )
    else:
        print(format_doctor_text(payload))
    return doctor_exit_code(payload)


def handle_integrations_list(args: argparse.Namespace) -> int:
    payload = list_integrations()
    if args.json:
        emit_json(
            {
                "ok": True,
                "object": "integration",
                "action": "list",
                "result": payload,
            }
        )
    else:
        print(format_integrations_text(payload))
    return EXIT_SUCCESS


def handle_config_show(repo: IntentRepository, args: argparse.Namespace) -> int:
    config = repo.show_config()
    if args.json:
        emit_json(
            {
                "ok": True,
                "object": "config",
                "action": "show",
                "result": config,
            }
        )
    else:
        print(repo.render_config_text())
    return EXIT_SUCCESS


def handle_object_list(repo: IntentRepository, args: argparse.Namespace, object_name: str) -> int:
    items = repo.list_view(object_name)
    if args.json:
        emit_json(
            {
                "ok": True,
                "object": object_name,
                "action": "list",
                "count": len(items),
                "items": items,
            }
        )
    else:
        print(repo.render_object_list_text(object_name))
    return EXIT_SUCCESS


def handle_object_show(
    repo: IntentRepository,
    args: argparse.Namespace,
    object_name: str,
    object_id: str,
) -> int:
    payload = repo.show_view(object_name, object_id)
    if args.json:
        emit_json(
            {
                "ok": True,
                "object": object_name,
                "action": "show",
                "result": payload,
            }
        )
    else:
        print(repo.render_object_show_text(object_name, object_id))
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

    if args.command == "decision" and args.decision_command == "create":
        args.command = "decide"
        args.title = args.title
        return args

    return args


def handle_checkpoint_select(repo: IntentRepository, args: argparse.Namespace) -> int:
    checkpoint, _, warnings = repo.select_checkpoint(args.checkpoint_id)
    if args.id_only:
        print(checkpoint["id"])
        return EXIT_SUCCESS
    if args.json:
        workspace_fields = workspace_result_fields(repo)
        emit_json(
            write_result(
                "checkpoint",
                "select",
                checkpoint["id"],
                checkpoint,
                warnings,
                next_action=cli_action(
                    ["adopt", "--checkpoint", checkpoint["id"], "-m", "Adopt candidate"],
                    "Checkpoint selected",
                ),
                **workspace_fields,
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
        if args.command == "version":
            return handle_version(args)
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
        if args.command == "run" and args.run_command == "start":
            return handle_run_start(repo, args)
        if args.command == "run" and args.run_command == "end":
            return handle_run_end(repo, args)
        if args.command == "run" and args.run_command == "list":
            return handle_object_list(repo, args, "run")
        if args.command == "run" and args.run_command == "show":
            return handle_object_show(repo, args, "run", args.run_id)
        if args.command == "decide":
            return handle_decide(repo, args)
        if args.command == "decision" and args.decision_command == "list":
            return handle_object_list(repo, args, "decision")
        if args.command == "decision" and args.decision_command == "show":
            return handle_object_show(repo, args, "decision", args.decision_id)
        if args.command == "status":
            return handle_status(repo, args)
        if args.command == "inspect":
            return handle_inspect(repo, args)
        if args.command == "log":
            return handle_log(repo, args)
        if args.command == "setup":
            return handle_setup(args)
        if args.command == "doctor":
            return handle_doctor(args)
        if args.command == "integrations" and args.integrations_command == "list":
            return handle_integrations_list(args)
        if args.command == "config" and args.config_command == "show":
            return handle_config_show(repo, args)
        if args.command == "intent" and args.intent_command == "list":
            return handle_object_list(repo, args, "intent")
        if args.command == "intent" and args.intent_command == "show":
            return handle_object_show(repo, args, "intent", args.intent_id)
        if args.command == "checkpoint" and args.checkpoint_command == "list":
            return handle_object_list(repo, args, "checkpoint")
        if args.command == "checkpoint" and args.checkpoint_command == "show":
            return handle_object_show(repo, args, "checkpoint", args.checkpoint_id)
        if args.command == "checkpoint" and args.checkpoint_command == "select":
            return handle_checkpoint_select(repo, args)
        if args.command == "adoption" and args.adoption_command == "list":
            return handle_object_list(repo, args, "adoption")
        if args.command == "adoption" and args.adoption_command == "show":
            return handle_object_show(repo, args, "adoption", args.adoption_id)
        parser.error("unknown command")
        return 2
    except IntentError as error:
        return emit_error(error, as_json=wants_json)


if __name__ == "__main__":
    raise SystemExit(main())
