"""Intent CLI — semantic history for agent-driven development."""

import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _read_source_version():
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if not pyproject.exists():
        return None
    text = pyproject.read_text(encoding="utf-8")
    in_project = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "[project]":
            in_project = True
            continue
        if in_project and stripped.startswith("["):
            break
        if in_project:
            match = re.match(r'version\s*=\s*"([^"]+)"', stripped)
            if match:
                return match.group(1)
    return None


def _resolve_version():
    source_version = _read_source_version()
    if source_version is not None:
        return source_version
    try:
        return version("intent-cli")
    except PackageNotFoundError:
        return "0.0.0"


__version__ = _resolve_version()
