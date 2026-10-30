"""Read-only IntHub web app."""

import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

# The app stays split by job in source and reaches the browser whole: sixty small
# requests made a first visit take seconds, and this needs no build step.
BUNDLES = {
    "/app.js": ("js", "application/javascript; charset=utf-8"),
    "/styles.css": ("css", "text/css; charset=utf-8"),
}


def bundle(static_dir, folder):
    """Every part of one bundle, in the order its order.txt lists them."""
    parts = Path(static_dir) / folder
    names = (parts / "order.txt").read_text(encoding="utf-8").split()
    return "\n".join((parts / name).read_text(encoding="utf-8") for name in names).encode("utf-8")


def product_version():
    """Use immutable image metadata, or installed-package metadata locally."""
    release_version = os.environ.get("INTHUB_VERSION")
    if release_version:
        return release_version
    try:
        return version("intent-history")
    except PackageNotFoundError:
        return "Unavailable (unpackaged source)"
