from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .constants import EXIT_GENERAL_FAILURE, EXIT_INVALID_INPUT
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


def build_git_context(cwd: Path, explicit_ref: Optional[str] = None) -> Tuple[Dict[str, Any], List[str]]:
    branch = git_branch(cwd)
    working_tree = git_working_tree(cwd)
    warnings: List[str] = []

    if explicit_ref:
        head = git_head(cwd, explicit_ref)
        if not head:
            raise IntentError(
                EXIT_INVALID_INPUT,
                "INVALID_INPUT",
                "Git ref could not be resolved.",
                details={"ref": explicit_ref},
                suggested_fix="Pass a valid ref to --link-git",
            )
        linkage_quality = "explicit_ref"
    else:
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


def summarize_git(git: Dict[str, Any]) -> str:
    branch = git.get("branch") or "unknown"
    head = git.get("head") or "no-commit"
    working_tree = git.get("working_tree")
    if working_tree == "dirty":
        return f"{branch} @ {head} (dirty)"
    return f"{branch} @ {head}"
