"""Where a project's .intent/ lives, including from a linked Git worktree."""

import subprocess
from pathlib import Path

from intent_cli import repo
from intent_cli.repo_checkout import attach_worktree, is_live, worktree_dir
from intent_cli.store_lock import workspace_write_lock
from intent_cli.store_paths import is_linked
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


def _git_lines(*args):
    try:
        return subprocess.run(["git", *args], capture_output=True, encoding="utf-8", errors="replace",
                              check=True).stdout.splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def _linked_worktree():
    """(main .intent/, Git's directory for this worktree, its name, Git branch), or None.

    Git names the main worktree itself. A bare repository has none, and with
    --separate-git-dir Git names its own directory instead, so in both cases each
    worktree keeps its own .intent/.
    """
    dirs = _git_lines("rev-parse", "--git-dir", "--git-common-dir")
    if len(dirs) < 2:
        return None
    git_dir, common = (Path.cwd() / dirs[0]).resolve(), (Path.cwd() / dirs[1]).resolve()
    if git_dir == common:
        return None
    listing = _git_lines("worktree", "list", "--porcelain")
    if not listing or not listing[0].startswith("worktree ") or "bare" in listing[1:3]:
        return None
    main = Path(listing[0][len("worktree "):])
    if not (main / ".git").exists():
        return None
    branch = _git_lines("branch", "--show-current")
    return main / INTENT_DIR, git_dir, git_dir.name, branch[0] if branch else ""


def project_root(base):
    """The folder a project's .intent/ serves: for a linked worktree, that worktree."""
    return git_root() if is_linked(base) else Path(base).parent


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
        main, git_dir, name, branch = linked
        if not repo.is_repository(main):
            return main
        if is_live(worktree_dir(main, name)):
            return worktree_dir(main, name)
        with workspace_write_lock(main, operation="worktree.attach"):
            return attach_worktree(main, git_dir, name, branch)
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
