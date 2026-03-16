"""Intent CLI package."""

from importlib import metadata


PACKAGE_NAME = "intent-cli"

try:
    __version__ = metadata.version(PACKAGE_NAME)
except metadata.PackageNotFoundError:
    __version__ = "0.1.0"
