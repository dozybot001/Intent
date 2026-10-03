"""Read-only IntHub web app."""

import os
from importlib.metadata import PackageNotFoundError, version


def product_version():
    """Use immutable image metadata, or installed-package metadata locally."""
    release_version = os.environ.get("INTHUB_VERSION")
    if release_version:
        return release_version
    try:
        return version("intent-cli")
    except PackageNotFoundError:
        return "Unavailable (unpackaged source)"
