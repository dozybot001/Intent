"""Where a project's .intent/ lives, including from a linked Git worktree."""

import subprocess
from pathlib import Path

from intent_cli import repo
from intent_cli.store_paths import WORKTREES
from intent_cli.store_schema import INTENT_DIR


def git_root():
    """Return git repo root as Path, or None."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(out.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _linked_worktree():
    """(main .intent/, worktree name, Git branch) inside a linked Git worktree, else None."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-dir", "--git-common-dir"],
            capture_output=True, text=True, check=True,
        ).stdout.split("\n")
        branch = subprocess.run(
            ["git", "branch", "--show-current"], capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    git_dir, common = Path(out[0]), Path(out[1])
    if git_dir == common:
        return None
    return common.parent / INTENT_DIR, git_dir.name, branch


def project_root(base):
    """The folder a project's .intent/ serves: for a linked worktree, that worktree."""
    return git_root() if Path(base).parent.name == WORKTREES else Path(base).parent


def intent_dir():
    """Find semantic storage independently; Git only supplies a default root."""
    current = Path.cwd()
    for parent in (current, *current.parents):
        candidate = parent / INTENT_DIR
        if candidate.exists() or candidate.is_symlink():
            return candidate
        if (parent / ".git").exists():
            break
    linked = _linked_worktree()
    if linked is not None:
        main, name, branch = linked
        return repo.attach_worktree(main, name, branch) if repo.is_repository(main) else main
    return (git_root() or current) / INTENT_DIR


def ensure_local_git_exclude(root, patterns=(f"{INTENT_DIR}/",)):
    """Exclude private local metadata through repository-local info/exclude."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-path", "info/exclude"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        path = Path(result.stdout.strip())
        if not path.is_absolute():
            path = root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        present = {line.strip().rstrip("/") for line in existing.splitlines()}
        missing = [pattern for pattern in patterns if pattern.rstrip("/") not in present]
        if not missing:
            return True
        with path.open("a", encoding="utf-8") as exclude_file:
            if existing and not existing.endswith("\n"):
                exclude_file.write("\n")
            exclude_file.write("\n".join(missing) + "\n")
        return True
    except (OSError, subprocess.CalledProcessError):
        return False
