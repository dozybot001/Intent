"""Global IntHub endpoint and account credential helpers."""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


OFFICIAL_INTHUB_API_BASE_URL = "https://inthub.tenon.asia"
CREDENTIAL_USERNAME = "intent-cli"


class GlobalHubConfigError(RuntimeError):
    """Raised when the non-secret global Hub config cannot be read or written."""


class CredentialStoreError(RuntimeError):
    """Raised when Git's configured credential helper cannot persist a token."""


def normalize_api_base_url(value):
    """Validate and normalize an IntHub HTTP(S) API base URL."""
    if not isinstance(value, str) or not value.strip():
        raise GlobalHubConfigError("IntHub API base URL must be a non-empty string.")
    raw = value.strip()
    if any(ord(char) < 32 or ord(char) == 127 for char in raw):
        raise GlobalHubConfigError("IntHub API base URL contains control characters.")
    try:
        parsed = urlsplit(raw)
        _ = parsed.port
    except ValueError as exc:
        raise GlobalHubConfigError("IntHub API base URL is invalid.") from exc
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise GlobalHubConfigError("IntHub API base URL must use http or https.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise GlobalHubConfigError(
            "IntHub API base URL must not contain credentials, a query, or a fragment."
        )
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def global_config_path():
    """Return the user-level, non-secret Intent config path."""
    override = os.getenv("INTENT_CONFIG_HOME")
    if override:
        root = Path(override).expanduser()
    elif os.name == "nt" and os.getenv("APPDATA"):
        root = Path(os.environ["APPDATA"]) / "Intent"
    else:
        xdg_root = os.getenv("XDG_CONFIG_HOME")
        root = (
            Path(xdg_root).expanduser() / "intent"
            if xdg_root
            else Path.home() / ".config" / "intent"
        )
    return root / "config.json"


def read_global_hub_config():
    """Read global non-secret Hub defaults."""
    path = global_config_path()
    if not path.exists():
        return {}
    if path.is_symlink():
        raise GlobalHubConfigError(f"Global Intent config must not be a symlink: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GlobalHubConfigError(f"Could not read global Intent config: {path}") from exc
    if not isinstance(data, dict):
        raise GlobalHubConfigError("Global Intent config must contain a JSON object.")
    api_base_url = data.get("api_base_url")
    if api_base_url is not None:
        data["api_base_url"] = normalize_api_base_url(api_base_url)
    return data


def write_global_hub_config(api_base_url):
    """Atomically persist the global endpoint without storing credentials."""
    path = global_config_path()
    if path.is_symlink():
        raise GlobalHubConfigError(f"Global Intent config must not be a symlink: {path}")
    api_base_url = normalize_api_base_url(api_base_url)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = json.dumps(
        {"api_base_url": api_base_url},
        indent=2,
        ensure_ascii=False,
    ) + "\n"
    fd = None
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".config.", dir=str(path.parent))
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as config_file:
            fd = None
            config_file.write(payload)
            config_file.flush()
            os.fsync(config_file.fileno())
        os.replace(temporary, path)
        temporary = None
        if os.name != "nt":
            os.chmod(path, 0o600)
    except OSError as exc:
        raise GlobalHubConfigError(f"Could not write global Intent config: {path}") from exc
    finally:
        if fd is not None:
            os.close(fd)
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def global_api_base_url():
    """Return the configured global endpoint or the official service."""
    return read_global_hub_config().get("api_base_url", OFFICIAL_INTHUB_API_BASE_URL)


def _credential_request(api_base_url, token=None):
    parsed = urlsplit(normalize_api_base_url(api_base_url))
    fields = [
        f"protocol={parsed.scheme}",
        f"host={parsed.netloc}",
        f"username={CREDENTIAL_USERNAME}",
    ]
    if token is not None:
        fields.append(f"password={token}")
    return "\n".join(fields) + "\n\n"


def _run_git_credential(action, request):
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    result = subprocess.run(
        ["git", "credential", action],
        input=request,
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    return result


def load_access_token(api_base_url):
    """Load an account token through Git's configured credential helper."""
    try:
        result = _run_git_credential("fill", _credential_request(api_base_url))
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator and key == "password":
            return value or None
    return None


def store_access_token(api_base_url, token):
    """Store an account token through Git's configured credential helper."""
    if not isinstance(token, str) or not token:
        raise CredentialStoreError("An IntHub account token is required.")
    if any(ord(char) < 32 or ord(char) == 127 for char in token):
        raise CredentialStoreError("IntHub account token contains control characters.")
    request = _credential_request(api_base_url, token)
    try:
        result = _run_git_credential("approve", request)
    except (OSError, subprocess.SubprocessError) as exc:
        raise CredentialStoreError("Could not invoke Git's credential helper.") from exc
    if result.returncode != 0 or load_access_token(api_base_url) != token:
        raise CredentialStoreError(
            "Git's credential helper did not persist the IntHub account token."
        )


def erase_access_token(api_base_url):
    """Remove the account token from Git's configured credential helper."""
    try:
        result = _run_git_credential("reject", _credential_request(api_base_url))
    except (OSError, subprocess.SubprocessError) as exc:
        raise CredentialStoreError("Could not invoke Git's credential helper.") from exc
    if result.returncode != 0:
        raise CredentialStoreError("Git's credential helper could not remove the token.")
