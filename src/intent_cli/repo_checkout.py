"""Moving the working copy: switching, fast-forwarding, linked worktrees, merge state, migration.

Every change to the working copy runs under a marker file. A move or a merge moves a ref or
HEAD last, and if it dies the next command to take the lock puts the working copy back on HEAD,
whichever side of that last step it stopped. A write command names the working copy it found
in the marker and is put back to that, so changes it did not make survive. A revision never
records half a command or one branch's objects on another, and a killed command is simply run again.
"""

import json
import secrets
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from intent_cli import repo
from intent_cli.store_errors import StoredObjectIntegrityError
from intent_cli.store_paths import WORKTREES, _safe_object_path, shared_root
from intent_cli.store_schema import SUBDIRS, validate_object_id

BACKUPS = "backups"
MERGE_STATE = "MERGE_STATE.json"
WRITE_MARKER = "WRITING"
WORKTREE_TOKEN = "WORKTREE_TOKEN"
GIT_DIR_FILE = "GIT_DIR"
GIT_MARKER = "intent-worktree"


def _object_path(base, obj_id):
    kind = obj_id.split("-", 1)[0] if isinstance(obj_id, str) else None
    validate_object_id(kind, obj_id)
    return _safe_object_path(base, kind, obj_id)


def _versions(base, revision):
    """Every object version of a revision. Read before anything moves, so a damaged one stops the move here."""
    return {obj_id: repo.read_version(base, digest) for obj_id, digest in repo.tree_at(base, revision).items()}


def _apply(base, versions):
    present = repo.working_copy(base)
    for obj_id in present.keys() - versions.keys():
        _object_path(base, obj_id).unlink()
    for obj_id, raw in versions.items():
        if present.get(obj_id) != raw:
            repo.replace_file(_object_path(base, obj_id), raw)


def checkout(base, revision):
    """Make the working copy match a revision: rewrite what differs, remove what it lacks."""
    _apply(base, _versions(base, revision))


def begin_write(base, saved=""):
    repo.replace_file(Path(base) / WRITE_MARKER, saved.encode("ascii"))


def begin_command(base):
    begin_write(base, repo.save_worktree(base))


def end_write(base):
    (Path(base) / WRITE_MARKER).unlink(missing_ok=True)


def recover_write(base):
    """Take back a change an interruption cut short. Runs whenever the lock is taken."""
    marker = Path(base) / WRITE_MARKER
    if marker.is_file():
        saved = marker.read_text(encoding="ascii", errors="replace").strip()
        _apply(base, repo.read_saved(base, saved)) if saved else checkout(base, repo.head_revision(base))
        clear_merge_state(base)
        end_write(base)


def abort_merge(base):
    begin_write(base)
    recover_write(base)


def switch(base, branch):
    """Move this worktree to a branch; the working copy follows."""
    versions = _versions(base, repo.branch_revision(base, branch))
    begin_write(base)
    _apply(base, versions)
    repo.set_head(base, branch)
    end_write(base)


def fast_forward(base, revision):
    """Move the current branch up to a revision it is behind."""
    versions = _versions(base, revision)
    begin_write(base)
    _apply(base, versions)
    repo.set_branch(base, repo.current_branch(base), revision)
    end_write(base)


def worktree_dir(main, name):
    return repo.contained(Path(main), WORKTREES, name)


def is_live(private):
    """Whether a worktree directory still belongs to the Git worktree that made it."""
    try:
        marker = Path((private / GIT_DIR_FILE).read_text(encoding="utf-8").strip()) / GIT_MARKER
        return marker.read_text(encoding="utf-8") == (private / WORKTREE_TOKEN).read_text(encoding="utf-8")
    except (OSError, ValueError):
        return False


def _worktrees(base):
    root = repo.contained(shared_root(base), WORKTREES)
    return [path for path in sorted(root.iterdir()) if is_live(path)] if root.is_dir() else []


def branches_in_use(base):
    """Branch by the place that has it open. Like Git, one branch sits in one place at a time."""
    used = {repo.current_branch(shared_root(base)): "main worktree"}
    for path in _worktrees(base):
        try:
            used[repo.current_branch(path)] = path.name
        except StoredObjectIntegrityError:
            continue  # one damaged worktree must not stop every other place
    return used


def _worktree_branch(main, wanted, name):
    used = branches_in_use(main)
    for candidate in (wanted, f"{wanted}-{name}", name, f"worktree-{name}"):
        if repo.valid_branch_name(candidate) and candidate not in used and not repo.branch_conflict(main, candidate):
            return candidate
    return f"worktree-{secrets.token_hex(4)}"


def attach_worktree(main, git_dir, name, git_branch):
    """A linked Git worktree's private HEAD and working copy, made the first time it is used.

    The token left in Git's own directory for the worktree tells a live worktree from
    a new one that reuses a removed worktree's name.
    """
    private = worktree_dir(main, name)
    if is_live(private):
        return private
    if private.exists():
        shutil.rmtree(private)
    for sub in SUBDIRS.values():
        (private / sub).mkdir(parents=True, exist_ok=True)
    branch = _worktree_branch(main, git_branch, name)
    if repo.branch_revision(main, branch) is None and repo.head_revision(main):
        repo.set_branch(main, branch, repo.head_revision(main))
    switch(private, branch)
    token = secrets.token_hex(16)
    (private / GIT_DIR_FILE).write_text(str(git_dir), encoding="utf-8")
    (private / WORKTREE_TOKEN).write_text(token, encoding="utf-8")
    (Path(git_dir) / GIT_MARKER).write_text(token, encoding="utf-8")
    return private


def write_objects(base, objects):
    """Write merged objects into the working copy, in the store's own JSON layout."""
    for obj_id, obj in objects.items():
        repo.replace_file(_object_path(base, obj_id), json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8"))


def read_merge_state(base):
    path = Path(base) / MERGE_STATE
    if not path.is_file():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        valid = (isinstance(state["branch"], str) and repo.DIGEST.fullmatch(state["theirs"])
                 and isinstance(state["conflicts"], list))
    except (ValueError, KeyError, TypeError) as exc:
        raise StoredObjectIntegrityError(path, "merge state is unreadable") from exc
    if not valid:
        raise StoredObjectIntegrityError(path, "merge state has an invalid shape")
    head = repo.head_revision(base)
    if head and state["theirs"] in repo.read_revision(base, head)["parents"]:
        clear_merge_state(base)  # the merge was recorded; only this cleanup was interrupted
        return None
    return state


def write_merge_state(base, state):
    repo.replace_file(Path(base) / MERGE_STATE, json.dumps(state, indent=2, ensure_ascii=False).encode("utf-8"))


def clear_merge_state(base):
    (Path(base) / MERGE_STATE).unlink(missing_ok=True)


def migrate(base):
    """Turn a 7.x workspace into a repository, its objects forming the first revision."""
    backups = Path(base) / BACKUPS
    backups.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backups / f"intent-7-{stamp}.tar.gz"
    with tarfile.open(backup, "w:gz") as archive:
        for name in (*SUBDIRS.values(), "hub.json", "maintenance.json"):
            if (Path(base) / name).exists():
                archive.add(Path(base) / name, arcname=name)
    repo.create_repository(base)
    return repo.commit_worktree(base, "migrate", summary="Migrated from Intent 7"), backup
