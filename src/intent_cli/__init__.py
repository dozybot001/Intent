"""Intent CLI — semantic history for agent-driven development."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("intent-cli-python")
except PackageNotFoundError:
    __version__ = "0.0.0"
