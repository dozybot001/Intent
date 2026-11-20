"""Intent CLI — Semantic Git for the vibe coding era."""

from importlib.metadata import PackageNotFoundError, version


def _resolve_version():
    try:
        # "intent-cli" on PyPI is an unrelated project.
        return version("intent-history")
    except PackageNotFoundError:
        return "0.0.0-dev"


__version__ = _resolve_version()
PUBLISHER = "Tenon AI"
WEBSITE = "https://tenonai.cn/"


def version_lines(number=__version__):
    """What `itt --version` and `itt version` print in a terminal."""
    return [f"itt {number}", f"Publisher: {PUBLISHER} ({WEBSITE})"]
