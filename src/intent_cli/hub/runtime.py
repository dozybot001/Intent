"""Local runtime config helpers for IntHub CLI commands."""

import os

from intent_cli.output import error
from intent_cli.store import read_hub_config


def load_hub(base):
    return read_hub_config(base) or {}


def sanitize_hub_config(config):
    sanitized = dict(config)
    token = sanitized.pop("auth_token", None)
    sanitized["auth_configured"] = bool(token)
    return sanitized


def hub_api_base(base, args):
    hub = load_hub(base)
    api_base_url = getattr(args, "api_base_url", None) or hub.get("api_base_url")
    if not api_base_url:
        error(
            "HUB_NOT_CONFIGURED",
            "IntHub API base URL is not configured.",
            suggested_fix="Run: itt hub login --api-base-url http://127.0.0.1:8000",
        )
    return api_base_url.rstrip("/")


def hub_auth_token(base, args):
    hub = load_hub(base)
    token = getattr(args, "token", None)
    if token:
        return token
    env_token = os.getenv("INTHUB_TOKEN")
    if env_token:
        return env_token
    return hub.get("auth_token")
