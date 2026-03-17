"""Intent CLI package."""

from importlib import metadata
from pathlib import Path
import re
from typing import Optional


PACKAGE_NAME = "git-intent"
REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
VERSION_PATTERN = re.compile(r'^version\s*=\s*"([^"]+)"\s*$', re.MULTILINE)


def version_from_checkout() -> Optional[str]:
    if not PYPROJECT_PATH.exists():
        return None
    match = VERSION_PATTERN.search(PYPROJECT_PATH.read_text(encoding="utf-8"))
    if not match:
        return None
    return match.group(1)


__version__ = version_from_checkout()
if __version__ is None:
    try:
        __version__ = metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        __version__ = "0.3.2"
