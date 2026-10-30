"""Global IntHub account authentication commands."""

import getpass
import os
import platform
import socket
import sys
import time
import webbrowser

from intent_cli.hub.client import http_json
from intent_cli.hub.credentials import (
    credentials_file,
    erase_access_token,
    global_api_base_url,
    load_access_token,
    normalize_api_base_url,
    store_access_token,
    write_global_hub_config,
)
from intent_cli.output import error, success


def _api_base(args):
    return normalize_api_base_url(
        getattr(args, "api_base_url", None) or global_api_base_url()
    )


def _can_open_browser():
    """False where webbrowser would fall back to a text browser, or open one nobody sees."""
    if os.getenv("SSH_CONNECTION") or os.getenv("SSH_TTY"):
        return False
    return sys.platform in {"darwin", "win32"} or bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))


def _device_name():
    """How the token will read in Settings. macOS often reports an IP address as the host name."""
    host = socket.gethostname().removesuffix(".local")
    if not host or host.replace(".", "").isdigit():
        host = {"Darwin": "macOS"}.get(platform.system()) or platform.system() or "this computer"
    return f"itt on {host}"


def _browser_login(api_base_url):
    """Sign in as `gh auth login` does: a code here, approved in a browser. None on a hub without it."""
    started = http_json(
        "POST",
        f"{api_base_url}/api/v1/auth/device/start",
        {"name": _device_name()},
        missing_ok=True,
    )
    if started is None:
        return None
    url = f"{api_base_url}{started['verification_path']}"
    print(f"Open {url} and enter this code:\n\n    {started['user_code']}\n", file=sys.stderr)
    if _can_open_browser():
        webbrowser.open(url)
    print("Waiting for approval… Press Ctrl-C to cancel.", file=sys.stderr)
    deadline = time.monotonic() + started["expires_in"]
    try:
        while time.monotonic() < deadline:
            time.sleep(started["interval"])
            result = http_json(
                "POST",
                f"{api_base_url}/api/v1/auth/device/poll",
                {"device_code": started["device_code"]},
                attempts=3,
            )
            if result["status"] == "approved":
                return result["token"]
            if result["status"] == "denied":
                error("AUTH_DENIED", "The sign-in was cancelled in the browser.")
            if result["status"] != "pending":
                break
    except KeyboardInterrupt:
        error("AUTH_CANCELLED", "Sign-in cancelled.")
    error(
        "AUTH_EXPIRED",
        "The sign-in code expired before it was approved.",
        suggested_fix="Run `itt auth login` again.",
    )


def _login_token(args, api_base_url):
    token = getattr(args, "token", None) or os.getenv("INTHUB_TOKEN")
    if not token and sys.stdin.isatty():
        token = _browser_login(api_base_url) or getpass.getpass("IntHub account token: ")
    if not token:
        error(
            "AUTH_REQUIRED",
            "Signing in needs a terminal, or an access token.",
            suggested_fix=(
                "Run `itt auth login` in your own terminal and approve the code in the browser, "
                "or set INTHUB_TOKEN to a token from Settings on IntHub."
            ),
        )
    return token


def cmd_auth_login(args):
    api_base_url = _api_base(args)
    token = _login_token(args, api_base_url)
    projects = http_json("GET", f"{api_base_url}/api/v1/projects", token=token)
    previous_token = load_access_token(api_base_url)
    credential_store = store_access_token(api_base_url, token)
    try:
        write_global_hub_config(api_base_url)
    except Exception:
        try:
            if previous_token:
                store_access_token(api_base_url, previous_token)
            else:
                erase_access_token(api_base_url)
        except Exception:
            pass
        raise
    success(
        "auth.login",
        {
            "api_base_url": api_base_url,
            "authenticated": True,
            "credential_store": credential_store,
            **({"credential_path": str(credentials_file())} if credential_store == "file" else {}),
            "project_count": len(projects.get("projects", [])),
        },
    )


def cmd_auth_status(args):
    api_base_url = _api_base(args)
    explicit = getattr(args, "token", None)
    environment = os.getenv("INTHUB_TOKEN")
    stored = None if explicit or environment else load_access_token(api_base_url)
    token = explicit or environment or stored
    source = (
        "command"
        if explicit
        else "environment"
        if environment
        else "credential-helper"
    )
    if not token:
        success(
            "auth.status",
            {"api_base_url": api_base_url, "authenticated": False, "token_source": None},
        )
        return
    projects = http_json("GET", f"{api_base_url}/api/v1/projects", token=token)
    success(
        "auth.status",
        {
            "api_base_url": api_base_url,
            "authenticated": True,
            "token_source": source,
            "project_count": len(projects.get("projects", [])),
        },
    )


def cmd_auth_logout(args):
    api_base_url = _api_base(args)
    configured = load_access_token(api_base_url) is not None
    erase_access_token(api_base_url)
    environment_active = bool(os.getenv("INTHUB_TOKEN"))
    warnings = [
        "The account token remains valid on IntHub until it expires or is revoked in the Web UI."
    ]
    if environment_active:
        warnings.append(
            "INTHUB_TOKEN is still set and takes precedence over stored credentials."
        )
    success(
        "auth.logout",
        {
            "api_base_url": api_base_url,
            "credential_removed": configured,
            "environment_token_active": environment_active,
        },
        warnings,
    )
