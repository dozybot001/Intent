"""Local runtime config helpers for IntHub CLI commands."""

import os
from urllib.parse import urlsplit

from intent_cli.hub.credentials import (
    GlobalHubConfigError,
    global_api_base_url,
    load_access_token,
    normalize_api_base_url,
)
from intent_cli.output import error
from intent_cli.store import read_hub_config

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def load_hub(base):
    return read_hub_config(base) or {}


def hub_api_base(base, args, hub=None):
    hub = load_hub(base) if hub is None else hub
    api_base_url = (
        getattr(args, "api_base_url", None)
        or hub.get("api_base_url")
        or global_api_base_url()
    )
    return normalize_api_base_url(api_base_url)


def _accepts_unscoped_token(args, api_base_url):
    """--token and INTHUB_TOKEN carry no endpoint of their own. Send them only
    where the user pointed: this command's --api-base-url, the user-level
    endpoint, or loopback; never to an endpoint named only by a project's
    (possibly shared) .intent/hub.json."""
    explicit = getattr(args, "api_base_url", None)
    try:
        if explicit and normalize_api_base_url(explicit) == api_base_url:
            return True
        if normalize_api_base_url(global_api_base_url()) == api_base_url:
            return True
    except GlobalHubConfigError:
        pass
    return urlsplit(api_base_url).hostname in LOOPBACK_HOSTS


def hub_auth_token(base, args, api_base_url=None):
    api_base_url = api_base_url or hub_api_base(base, args)
    token = getattr(args, "token", None) or os.getenv("INTHUB_TOKEN")
    if token:
        if not _accepts_unscoped_token(args, api_base_url):
            error(
                "TOKEN_ENDPOINT_MISMATCH",
                f"Refusing to send --token/INTHUB_TOKEN to {api_base_url}: only this project's .intent/hub.json names that endpoint.",
                suggested_fix=(
                    f"If you trust it, pass --api-base-url {api_base_url}, or store a token for it with "
                    f"`itt auth login --api-base-url {api_base_url}`."
                ),
            )
        return token
    # Credential-helper tokens are stored per endpoint, so they are already scoped.
    return load_access_token(api_base_url)


def hub_auth_configured(api_base_url):
    """Report whether reusable account authentication is available."""
    return bool(os.getenv("INTHUB_TOKEN") or load_access_token(api_base_url))
