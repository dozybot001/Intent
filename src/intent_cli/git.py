from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .constants import EXIT_GENERAL_FAILURE
from .errors import IntentError


def run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )


def ensure_git_worktree(cwd: Path) -> None:
    result = run_git(cwd, "rev-parse", "--is-inside-work-tree")
    if result.returncode != 0 or result.stdout.strip() != "true":
        raise IntentError(
            EXIT_GENERAL_FAILURE,
            "GIT_STATE_INVALID",
            "Intent requires a Git repository",
            suggested_fix="git init",
        )


def git_branch(cwd: Path) -> str:
    result = run_git(cwd, "branch", "--show-current")
    if result.returncode == 0:
        value = result.stdout.strip()
        if value:
            return value
    result = run_git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return "unknown"


def git_head(cwd: Path, ref: str = "HEAD") -> Optional[str]:
    result = run_git(cwd, "rev-parse", "--short", ref)
    if result.returncode == 0:
        value = result.stdout.strip()
        return value or None
    return None


def git_working_tree(cwd: Path) -> str:
    result = run_git(cwd, "status", "--porcelain")
    if result.returncode != 0:
        return "unknown"
    return "clean" if not result.stdout.strip() else "dirty"


def build_git_context(cwd: Path) -> Tuple[Dict[str, Any], List[str]]:
    branch = git_branch(cwd)
    working_tree = git_working_tree(cwd)
    warnings: List[str] = []

    head = git_head(cwd)
    if head and working_tree == "clean":
        linkage_quality = "stable_commit"
    else:
        linkage_quality = "working_tree_context"
        if not head:
            warnings.append("Git HEAD could not be resolved; recording working tree context only.")

    if working_tree == "dirty":
        warnings.append("Git working tree is dirty; recording working tree context.")

    return (
        {
            "branch": branch,
            "head": head,
            "working_tree": working_tree,
            "linkage_quality": linkage_quality,
        },
        warnings,
    )
