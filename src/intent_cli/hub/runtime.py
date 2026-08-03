"""Local runtime config helpers for IntHub CLI commands."""

import os

from intent_cli.hub.credentials import global_api_base_url, load_access_token, normalize_api_base_url
from intent_cli.store import read_hub_config


def load_hub(base):
    return read_hub_config(base) or {}


def config_without_auth_token(config):
    """Return a persistence-safe copy; account tokens are never local config."""
    persisted = dict(config)
    persisted.pop("auth_token", None)
    return persisted


def sanitize_hub_config(config, auth_configured=None):
    sanitized = dict(config)
    sanitized.pop("auth_token", None)
    sanitized["auth_configured"] = (
        bool(os.getenv("INTHUB_TOKEN"))
        if auth_configured is None
        else bool(auth_configured)
    )
    return sanitized


def hub_api_base(base, args, hub=None):
    hub = load_hub(base) if hub is None else hub
    api_base_url = (
        getattr(args, "api_base_url", None)
        or hub.get("api_base_url")
        or global_api_base_url()
    )
    return normalize_api_base_url(api_base_url)


def hub_auth_token(base, args, api_base_url=None):
    token = getattr(args, "token", None)
    if token:
        return token
    env_token = os.getenv("INTHUB_TOKEN")
    if env_token:
        return env_token
    api_base_url = api_base_url or hub_api_base(base, args)
    return load_access_token(api_base_url)


def hub_auth_configured(api_base_url):
    """Report whether reusable account authentication is available."""
    return bool(os.getenv("INTHUB_TOKEN") or load_access_token(api_base_url))
