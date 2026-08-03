"""Intent CLI — parser and command dispatch."""

import argparse
import sys

from intent_cli.output import error
from intent_cli.store import (
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
from intent_cli.commands.core import (
    cmd_decision_create,
    cmd_decision_deprecate,
    cmd_doctor,
    cmd_init,
    cmd_inspect,
    cmd_intent_activate,
    cmd_intent_cancel,
    cmd_intent_create,
    cmd_intent_done,
    cmd_intent_suspend,
    cmd_snap_create,
    cmd_version,
)
from intent_cli.commands.hub import (
    cmd_hub_link,
    cmd_hub_start,
    cmd_hub_status,
    cmd_hub_sync,
    cmd_push,
)


def _invoke(command, args):
    """Run one command and keep storage-safety failures in the JSON contract."""
    try:
        command(args)
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
    except WorkspaceBusyError:
        error(
            "WORKSPACE_BUSY",
            "Another Intent command is writing to this workspace.",
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
    parser = JsonArgumentParser(prog="itt", description="Intent CLI")
    sub = parser.add_subparsers(dest="command")

    # version / init / inspect / doctor
    sub.add_parser("version")
    sub.add_parser("init")
    p = sub.add_parser("inspect")
    p.add_argument("--intent", default=None, metavar="ID")
    p.add_argument("--history", type=int, default=None, metavar="N")
    sub.add_parser("doctor")

    # --- account auth / Git-style push ---
    p_auth = sub.add_parser("auth")
    s_auth = p_auth.add_subparsers(dest="sub")

    p = s_auth.add_parser("login")
    p.add_argument("--api-base-url", default=None)
    p.add_argument("--token", default=None)

    p = s_auth.add_parser("status")
    p.add_argument("--api-base-url", default=None)
    p.add_argument("--token", default=None)

    p = s_auth.add_parser("logout")
    p.add_argument("--api-base-url", default=None)

    p = sub.add_parser("push")
    p.add_argument("--api-base-url", default=None)
    p.add_argument("--token", default=None)
    p.add_argument("--dry-run", action="store_true")

    # --- hub ---
    p_hub = sub.add_parser("hub")
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

    p = s_intent.add_parser("cancel")
    p.add_argument("id", nargs="?")
    p.add_argument("--reason", default="")

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
        error(
            "INVALID_INPUT",
            "A command is required.",
            details={"usage": parser.format_usage().strip()},
        )

    dispatch_global = {
        "version": cmd_version,
        "init": cmd_init,
        "inspect": cmd_inspect,
        "doctor": cmd_doctor,
        "push": cmd_push,
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
        }[args.command]
        error(
            "INVALID_INPUT",
            f"A subcommand is required for {args.command!r}.",
            details={"usage": command_parser.format_usage().strip()},
        )

    dispatch = {
        ("hub", "start"):              cmd_hub_start,
        ("hub", "status"):             cmd_hub_status,
        ("hub", "link"):               cmd_hub_link,
        ("hub", "sync"):               cmd_hub_sync,
        ("auth", "login"):             cmd_auth_login,
        ("auth", "status"):            cmd_auth_status,
        ("auth", "logout"):            cmd_auth_logout,
        ("intent", "create"):          cmd_intent_create,
        ("intent", "activate"):        cmd_intent_activate,
        ("intent", "suspend"):         cmd_intent_suspend,
        ("intent", "done"):            cmd_intent_done,
        ("intent", "cancel"):          cmd_intent_cancel,
        ("snap", "create"):            cmd_snap_create,
        ("decision", "create"):        cmd_decision_create,
        ("decision", "deprecate"):     cmd_decision_deprecate,
    }
    _invoke(dispatch[(args.command, args.sub)], args)
