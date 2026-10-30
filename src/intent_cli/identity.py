"""Who is recording and on which commit, read the way Git reads them.

A developer with Git configured has nothing to set up. ITT_AUTHOR_NAME and
ITT_AUTHOR_EMAIL override the identity; GIT_AUTHOR_NAME and GIT_AUTHOR_EMAIL
apply next, as they do for a commit. Semantic recording never depends on Git:
anything Git cannot answer is simply left out.
"""

import os
import re
import subprocess

FIELD_MAX_CHARS = 200
_IDENTITY = {
    "name": (("ITT_AUTHOR_NAME", "GIT_AUTHOR_NAME"), "user.name"),
    "email": (("ITT_AUTHOR_EMAIL", "GIT_AUTHOR_EMAIL"), "user.email"),
}
MISSING = ("No author identity, so new objects will not say who recorded them. "
           "Set one with: git config --global user.name NAME; git config --global user.email EMAIL")
COMMIT = re.compile(r"[0-9a-f]{40}([0-9a-f]{24})?")
REPOSITORY_HOSTS = r"github\.com|gitlab\.com|gitee\.com"
_REPOSITORY_PATH = r"((?:[\w.-]+/)+[\w.-]+?)(?:\.git)?/?"
_REMOTE = re.compile(rf"(?:https://(?:[^@/]+@)?|ssh://git@|git@)({REPOSITORY_HOSTS})[:/]{_REPOSITORY_PATH}")
REPOSITORY = re.compile(rf"https://(?:{REPOSITORY_HOSTS})/(?:[\w.-]+/)+[\w.-]+")


def _git(*args):
    try:
        return subprocess.run(["git", *args], capture_output=True, encoding="utf-8", errors="replace", timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None


def _git_value(*args):
    result = _git(*args)
    return result.stdout.strip() if result is not None and result.returncode == 0 else ""


def author(environ=None):
    """Return {"name", "email"} with whatever is known; empty when nothing is."""
    env = os.environ if environ is None else environ
    identity = {}
    for field, (names, key) in _IDENTITY.items():
        declared = next((env[name].strip() for name in names if (env.get(name) or "").strip()), "")
        value = declared or _git_value("config", "--get", key)
        if value:
            identity[field] = value[:FIELD_MAX_CHARS]
    return identity


def commit():
    """Return the commit being worked on; "dirty" marks uncommitted changes to tracked files."""
    sha = _git_value("rev-parse", "--verify", "HEAD")
    if not COMMIT.fullmatch(sha):
        return {}
    changes = _git("diff", "--quiet", "HEAD", "--")
    return {"commit": sha, "dirty": True} if changes is not None and changes.returncode == 1 else {"commit": sha}


def repository():
    """Return the origin remote as a browsable URL on a known host, without credentials."""
    match = _REMOTE.fullmatch(_git_value("config", "--get", "remote.origin.url"))
    return f"https://{match.group(1)}/{match.group(2)}" if match else None
