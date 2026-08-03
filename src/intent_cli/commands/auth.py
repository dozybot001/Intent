"""Global IntHub account authentication commands."""

import getpass
import os
import sys

from intent_cli.hub.client import http_json
from intent_cli.hub.credentials import (
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


def _login_token(args):
    token = getattr(args, "token", None) or os.getenv("INTHUB_TOKEN")
    if not token and sys.stdin.isatty():
        token = getpass.getpass("IntHub account token: ")
    if not token:
        error(
            "AUTH_REQUIRED",
            "An IntHub account token is required.",
            suggested_fix=(
                "Create a CLI token in IntHub, then run `itt auth login` and paste it "
                "at the prompt, or set INTHUB_TOKEN for this command."
            ),
        )
    return token


def cmd_auth_login(args):
    api_base_url = _api_base(args)
    token = _login_token(args)
    projects = http_json("GET", f"{api_base_url}/api/v1/projects", token=token)
    previous_token = load_access_token(api_base_url)
    store_access_token(api_base_url, token)
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
            "credential_store": "git-credential-helper",
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
