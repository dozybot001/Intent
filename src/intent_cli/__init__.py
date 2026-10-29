"""Intent CLI — semantic history for agent-driven development."""

from importlib.metadata import PackageNotFoundError, version


def _resolve_version():
    try:
        # "intent-cli" on PyPI is an unrelated project.
        return version("intent-history")
    except PackageNotFoundError:
        return "0.0.0-dev"


__version__ = _resolve_version()
