"""Intent CLI — semantic history for agent-driven development."""

from importlib.metadata import PackageNotFoundError, version


def _resolve_version():
    try:
        return version("intent-cli")
    except PackageNotFoundError:
        return "0.0.0-dev"


__version__ = _resolve_version()
