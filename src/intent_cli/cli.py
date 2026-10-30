"""Intent CLI — parser and command dispatch."""

import argparse
import os
import sys

from intent_cli import __version__
from intent_cli.output import error, set_format
from intent_cli.store import (
    CHECKPOINT_FIELDS,
    InvalidObjectIdError,
    StorageSecurityError,
    StoredObjectIntegrityError,
    StoredObjectParseError,
    StoredObjectSchemaError,
    StoredObjectWriteConflictError,
    UnsafeStoragePathError,
    WorkspaceBusyError,
)
from intent_cli.hub.credentials import CredentialStoreError, GlobalHubConfigError
from intent_cli.commands.auth import cmd_auth_login, cmd_auth_logout, cmd_auth_status
from intent_cli.commands.maintenance import cmd_maintenance
from intent_cli.maintenance import MaintenanceError
from intent_cli.maintenance_hooks import HOSTS
from intent_cli.hub.restore import PullApplyError
from intent_cli.commands.core import (
    cmd_decision_create,
    cmd_decision_deprecate,
    cmd_doctor,
    cmd_init,
    cmd_inspect,
    cmd_log,
    cmd_show,
    cmd_intent_activate,
    cmd_intent_cancel,
    cmd_intent_create,
    cmd_intent_done,
    cmd_intent_relate,
    cmd_intent_suspend,
    cmd_intent_unrelate,
    cmd_snap_create,
    cmd_version,
)
from intent_cli.commands.hub import cmd_hub_start
from intent_cli.commands.shared import cmd_push, cmd_pull, cmd_status, cmd_remote, cmd_link, cmd_hub_status


RELATION_FLAGS = (
    ("--part-of", "part_of", "this goal is a part of ID: ID is not complete until it is done or dropped"),
    ("--derived-from", "derived_from", "this goal arose while working on ID, which does not need it"),
    ("--succeeds", "succeeds", "this goal takes over ID's aim: next stage, new approach or merged duplicate"),
    ("--depends-on", "depends_on", "this goal cannot proceed until ID is done"),
    ("--conflicts-with", "conflicts_with", "this goal and ID cannot both be achieved as stated"),
)


def _invoke(command, args):
    """Run one command and keep storage-safety failures in the JSON contract."""
    try:
        command(args)
    except MaintenanceError as exc:
        error(exc.code, str(exc))
    except PullApplyError as exc:
        error(
            "PULL_APPLY_FAILED", str(exc),
            details={"recovery_required": exc.recovery_required, "committed": exc.committed},
        )
    except InvalidObjectIdError as exc:
        error(
            "INVALID_OBJECT_ID",
            str(exc),
            details={"object_type": exc.object_type, "id": exc.obj_id},
        )
    except UnsafeStoragePathError as exc:
        error(
            "UNSAFE_STORAGE",
            str(exc),
            details={"path": str(exc.path)},
        )
    except StoredObjectParseError as exc:
        error(
            "STORAGE_PARSE_ERROR",
            str(exc),
            details={"path": str(exc.path)},
        )
    except StoredObjectSchemaError as exc:
        details = {"path": str(exc.path)}
        if exc.field is not None:
            details["field"] = exc.field
        error(
            "STORAGE_SCHEMA_ERROR",
            str(exc),
            details=details,
        )
    except StoredObjectIntegrityError as exc:
        error(
            "STORAGE_INTEGRITY_ERROR",
            str(exc),
            details={"path": str(exc.path)},
        )
    except StoredObjectWriteConflictError as exc:
        error(
            "STORAGE_WRITE_CONFLICT",
            str(exc),
            details={
                "path": str(exc.path),
                "conflicts": exc.conflicts,
            },
        )
    except WorkspaceBusyError as exc:
        error(
            "WORKSPACE_BUSY",
            "Another Intent command is writing to this workspace.",
            details={"owner": exc.owner},
            suggested_fix="Wait for that command to finish, then retry.",
        )
    except StorageSecurityError as exc:
        error(
            "STORAGE_SECURITY_ERROR",
            str(exc),
        )
    except GlobalHubConfigError as exc:
        error(
            "GLOBAL_CONFIG_ERROR",
            str(exc),
        )
    except CredentialStoreError as exc:
        error(
            "CREDENTIAL_STORE_ERROR",
            str(exc),
            suggested_fix=(
                "Configure a Git credential helper (for example osxkeychain, "
                "manager, or libsecret) and retry."
            ),
        )
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        # Keep unexpected failures inside the error contract; ITT_DEBUG shows the traceback.
        if os.getenv("ITT_DEBUG"):
            raise
        error(
            "INTERNAL_ERROR",
            f"{type(exc).__name__}: {exc}",
            suggested_fix="Re-run with ITT_DEBUG=1 for a traceback and report it at https://github.com/dozybot001/Intent/issues",
        )


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


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser that preserves the CLI's stdout JSON error contract."""

    def error(self, message):
        error(
            "INVALID_INPUT",
            message,
            details={"usage": self.format_usage().strip()},
        )


def main():
    _ensure_utf8_stdio()
    argv = sys.argv[1:]
    if "--json" in argv:
        argv = [arg for arg in argv if arg != "--json"]
        set_format("json")
    parser = JsonArgumentParser(
        prog="itt",
        description="Intent: semantic history for agent-driven development. "
                    "Records goals (intents), verified checkpoints (snaps) and durable decisions.",
        epilog="Output is readable text in a terminal and JSON for agents and pipes; "
               "pass --json (or set ITT_FORMAT=json) to force JSON.",
    )
    parser.add_argument("--version", action="version", version=f"itt {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # version / init / inspect / doctor
    sub.add_parser("version", help="print the CLI version")
    p = sub.add_parser("init", help="start recording semantic history in this project")
    p.add_argument("--host", choices=HOSTS, default=None, help="agent whose hooks to install (default: the agent in use, or ask)")
    p = sub.add_parser("inspect", help="show open goals, their latest checkpoints and decisions")
    p.add_argument("--intent", default=None, metavar="ID", help="focus on one open intent")
    p.add_argument("--history", type=int, default=None, metavar="N", help="with --intent: include its last N snaps")
    p = sub.add_parser("log", help="list snaps, newest first")
    p.add_argument("--intent", default=None, metavar="ID", help="only snaps of this intent")
    p.add_argument("-n", "--max-count", type=int, default=20, metavar="N", help="show at most N snaps (default 20)")
    p.add_argument("--all", action="store_true", help="show every snap")
    p = sub.add_parser("show", help="show one intent, snap or decision")
    p.add_argument("id", metavar="ID")
    sub.add_parser("doctor", help="check the history for integrity problems")
    p = sub.add_parser("status", help="compare local history with its remote")
    p.add_argument("--local", action="store_true")
    p.add_argument("--project", default=None)
    p.add_argument("--api-base-url", default=None)
    p.add_argument("--token", default=None)
    p_remote = sub.add_parser("remote", help="show or set the IntHub remote")
    s_remote = p_remote.add_subparsers(dest="sub")
    p_remote.add_argument("-v", action="store_true")
    p = s_remote.add_parser("add")
    p.add_argument("name")
    p.add_argument("url")
    p.add_argument("--project", default=None)

    p_maintenance = sub.add_parser("maintenance", help="turn per-turn agent recording on or off")
    s_maintenance = p_maintenance.add_subparsers(dest="sub")
    for name in ("status", "on", "off"):
        s_maintenance.add_parser(name).add_argument("--host", choices=HOSTS, default=None)
    p = s_maintenance.add_parser("close")
    p.add_argument("outcome", choices=("recorded", "no-op", "failed"))
    p.add_argument("--turn", required=True)
    p.add_argument("--reason", default="")
    p.add_argument("--objects", nargs="+", default=None)
    p = s_maintenance.add_parser("hook")
    p.add_argument("--host", choices=HOSTS, default="codex")
    p.add_argument("--root", default=None)

    # --- account auth / Git-style push ---
    p_auth = sub.add_parser("auth", help="sign in to IntHub with an access token")
    s_auth = p_auth.add_subparsers(dest="sub")

    p = s_auth.add_parser("login")
    p.add_argument("--api-base-url", default=None)
    p.add_argument("--token", default=None)

    p = s_auth.add_parser("status")
    p.add_argument("--api-base-url", default=None)
    p.add_argument("--token", default=None)

    p = s_auth.add_parser("logout")
    p.add_argument("--api-base-url", default=None)

    p = sub.add_parser("push", help="publish local history to the remote")
    p.add_argument("--project", default=None)
    p.add_argument("--api-base-url", default=None)
    p.add_argument("--token", default=None)
    p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("pull", help="update local history from the remote")
    p.add_argument("--project", default=None)
    p.add_argument("--api-base-url", default=None)
    p.add_argument("--token", default=None)
    p.add_argument("--dry-run", action="store_true")

    # --- hub ---
    p_hub = sub.add_parser("hub", help="run IntHub locally (hub start)")
    s_hub = p_hub.add_subparsers(dest="sub")

    p = s_hub.add_parser("start")
    p.add_argument("--port", type=int, default=None)
    p.add_argument("--no-open", action="store_true")

    p = s_hub.add_parser("status")
    p.add_argument("--api-base-url", default=None)

    p = s_hub.add_parser("link")
    p.add_argument("--project-name", default=None)
    p.add_argument("--api-base-url", default=None)
    p.add_argument("--token", default=None)

    p = s_hub.add_parser("sync")
    p.add_argument("--api-base-url", default=None)
    p.add_argument("--token", default=None)
    p.add_argument("--dry-run", action="store_true")

    # --- intent ---
    p_intent = sub.add_parser("intent", help="create goals and change their status")
    s_intent = p_intent.add_subparsers(dest="sub")

    p = s_intent.add_parser("create")
    p.add_argument("what", metavar="WHAT")
    p.add_argument("--why", default="")
    p.add_argument("--origin", default=None, metavar="LABEL")
    parent = p.add_mutually_exclusive_group()
    for flag, dest, text in RELATION_FLAGS:
        if dest in ("part_of", "derived_from"):
            parent.add_argument(flag, dest=dest, default=None, metavar="ID", help=text)
        else:
            p.add_argument(flag, dest=dest, action="append", default=None, metavar="ID", help=f"{text} (repeatable)")

    p = s_intent.add_parser("relate", help="record how this intent relates to another")
    p.add_argument("id", metavar="INTENT")
    kinds = p.add_mutually_exclusive_group(required=True)
    for flag, dest, text in RELATION_FLAGS:
        kinds.add_argument(flag, dest=dest, default=None, metavar="ID", help=text)

    p = s_intent.add_parser("unrelate", help="withdraw the active relation between two intents")
    p.add_argument("id", metavar="INTENT")
    p.add_argument("other", metavar="OTHER")

    p = s_intent.add_parser("activate")
    p.add_argument("id", nargs="?")

    p = s_intent.add_parser("suspend")
    p.add_argument("id", nargs="?")

    into_help = "the intent that carries this goal on; records that it succeeds this one"
    p = s_intent.add_parser("done")
    p.add_argument("id", nargs="?")
    p.add_argument("--into", default=None, metavar="ID", help=into_help)

    p = s_intent.add_parser("cancel")
    p.add_argument("id", nargs="?")
    p.add_argument("--reason", default="")
    p.add_argument("--into", default=None, metavar="ID", help=into_help)

    # --- snap ---
    p_snap = sub.add_parser("snap", help="record a verified checkpoint")
    s_snap = p_snap.add_subparsers(dest="sub")

    p = s_snap.add_parser("create")
    p.add_argument("what", metavar="WHAT")
    p.add_argument("--intent", default=None)
    p.add_argument("--why", default="")
    p.add_argument("--origin", default=None, metavar="LABEL")
    for name in CHECKPOINT_FIELDS:
        p.add_argument(f"--{name}", default=None, metavar="TEXT")

    # --- decision ---
    p_decision = sub.add_parser("decision", help="record or retire a durable decision")
    s_decision = p_decision.add_subparsers(dest="sub")

    p = s_decision.add_parser("create")
    p.add_argument("what", metavar="WHAT")
    p.add_argument("--why", default="")
    p.add_argument("--origin", default=None, metavar="LABEL")
    p.add_argument("--from", dest="source", default=None, metavar="ID", help="the intent this decision came from (omit for a project-level decision)")

    p = s_decision.add_parser("deprecate")
    p.add_argument("id")
    p.add_argument("--reason", default="")

    args = parser.parse_args(argv)
    if args.command == "maintenance" and getattr(args, "sub", None) == "hook":
        set_format("json")  # host protocol, never human text

    if args.command is None:
        error(
            "INVALID_INPUT",
            "A command is required.",
            details={"usage": parser.format_usage().strip()},
        )

    dispatch_global = {
        "version": cmd_version,
        "init": cmd_init,
        "inspect": cmd_inspect,
        "log": cmd_log,
        "show": cmd_show,
        "doctor": cmd_doctor,
        "push": cmd_push,
        "pull": cmd_pull,
        "status": cmd_status,
        "remote": cmd_remote,
    }
    if args.command in dispatch_global:
        _invoke(dispatch_global[args.command], args)
        return

    if not getattr(args, "sub", None):
        command_parser = {
            "hub": p_hub,
            "auth": p_auth,
            "intent": p_intent,
            "snap": p_snap,
            "decision": p_decision,
            "maintenance": p_maintenance,
        }[args.command]
        error(
            "INVALID_INPUT",
            f"A subcommand is required for {args.command!r}.",
            details={"usage": command_parser.format_usage().strip()},
        )

    dispatch = {
        ("hub", "start"):              cmd_hub_start,
        ("hub", "status"):             cmd_hub_status,
        ("hub", "link"):               cmd_link,
        ("hub", "sync"):               cmd_push,
        ("auth", "login"):             cmd_auth_login,
        ("auth", "status"):            cmd_auth_status,
        ("auth", "logout"):            cmd_auth_logout,
        ("intent", "create"):          cmd_intent_create,
        ("intent", "activate"):        cmd_intent_activate,
        ("intent", "suspend"):         cmd_intent_suspend,
        ("intent", "done"):            cmd_intent_done,
        ("intent", "cancel"):          cmd_intent_cancel,
        ("intent", "relate"):          cmd_intent_relate,
        ("intent", "unrelate"):        cmd_intent_unrelate,
        ("snap", "create"):            cmd_snap_create,
        ("decision", "create"):        cmd_decision_create,
        ("decision", "deprecate"):     cmd_decision_deprecate,
    }
    if args.command == "maintenance":
        _invoke(cmd_maintenance, args)
        return
    _invoke(dispatch[(args.command, args.sub)], args)
