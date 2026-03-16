from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_VERSION = "0.1"

EXIT_SUCCESS = 0
EXIT_GENERAL_FAILURE = 1
EXIT_INVALID_INPUT = 2
EXIT_STATE_CONFLICT = 3
EXIT_OBJECT_NOT_FOUND = 4

DIR_NAMES = {
    "intent": "intents",
    "checkpoint": "checkpoints",
    "adoption": "adoptions",
    "run": "runs",
    "decision": "decisions",
}

ID_PREFIXES = {
    "intent": "intent",
    "checkpoint": "cp",
    "adoption": "adopt",
    "run": "run",
    "decision": "decision",
}

OBJECT_LABELS = {
    "intent": "Intent",
    "checkpoint": "Checkpoint",
    "adoption": "Adoption",
}

OBJECT_PLURALS = {
    "intent": "Intents",
    "checkpoint": "Checkpoints",
    "adoption": "Adoptions",
}


class IntentError(Exception):
    def __init__(
        self,
        exit_code: int,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        suggested_fix: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.code = code
        self.message = message
        self.details = details or {}
        self.suggested_fix = suggested_fix

    def to_json(self) -> Dict[str, Any]:
        payload = {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            },
        }
        if self.suggested_fix:
            payload["error"]["suggested_fix"] = self.suggested_fix
        return payload


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")


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


def object_sort_key(item: Dict[str, Any]) -> Tuple[str, int]:
    object_id = item.get("id", "")
    suffix = object_id.rsplit("-", 1)[-1]
    number = int(suffix) if suffix.isdigit() else 0
    return (item.get("created_at", ""), number)


def object_brief(obj: Optional[Dict[str, Any]], include_status: bool = True) -> Optional[Dict[str, Any]]:
    if not obj:
        return None
    payload = {
        "id": obj["id"],
        "title": obj["title"],
        "status": obj["status"],
    }
    if include_status and "adopted" in obj:
        payload["adopted"] = obj["adopted"]
    return payload


def write_result(
    object_name: str,
    action: str,
    object_id: Optional[str],
    result: Dict[str, Any],
    warnings: List[str],
    next_action: Optional[Dict[str, str]] = None,
    *,
    state_changed: bool = True,
    noop: bool = False,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "ok": True,
        "object": object_name,
        "action": action,
        "id": object_id,
        "state_changed": state_changed,
        "result": result,
        "warnings": warnings,
    }
    if next_action is not None:
        payload["next_action"] = next_action
    if noop:
        payload["noop"] = True
    if reason:
        payload["reason"] = reason
    return payload


@dataclass
class StatusSnapshot:
    state: Dict[str, Any]
    active_intent: Optional[Dict[str, Any]]
    current_checkpoint: Optional[Dict[str, Any]]
    latest_adoption: Optional[Dict[str, Any]]
    candidate_checkpoints: List[Dict[str, Any]]
    warnings: List[str]
    git: Dict[str, Any]


class IntentRepository:
    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.intent_dir = cwd / ".intent"
        self.config_path = self.intent_dir / "config.json"
        self.state_path = self.intent_dir / "state.json"

    def ensure_git(self) -> None:
        ensure_git_worktree(self.cwd)

    def is_initialized(self) -> bool:
        return self.intent_dir.exists() and self.config_path.exists() and self.state_path.exists()

    def ensure_initialized(self) -> None:
        if not self.is_initialized():
            raise IntentError(
                EXIT_GENERAL_FAILURE,
                "NOT_INITIALIZED",
                "Intent is not initialized in this repository",
                suggested_fix="itt init",
            )

    def _object_dir(self, object_name: str) -> Path:
        return self.intent_dir / DIR_NAMES[object_name]

    def init_workspace(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        self.ensure_git()
        if self.intent_dir.exists():
            raise IntentError(
                EXIT_GENERAL_FAILURE,
                "ALREADY_EXISTS",
                "Intent is already initialized in this repository",
                suggested_fix="Use the existing .intent workspace",
            )

        self.intent_dir.mkdir()
        for dir_name in DIR_NAMES.values():
            (self.intent_dir / dir_name).mkdir()

        config = {
            "schema_version": SCHEMA_VERSION,
            "git": {"strict_adoption": False},
        }
        state = {
            "schema_version": SCHEMA_VERSION,
            "mode": "human",
            "active_intent_id": None,
            "active_run_id": None,
            "current_checkpoint_id": None,
            "last_adoption_id": None,
            "workspace_status": "idle",
            "updated_at": utc_now(),
        }
        write_json(self.config_path, config)
        write_json(self.state_path, state)
        return config, state

    def load_config(self) -> Dict[str, Any]:
        self.ensure_initialized()
        return read_json(self.config_path)

    def load_state(self) -> Dict[str, Any]:
        self.ensure_initialized()
        return read_json(self.state_path)

    def save_state(self, state: Dict[str, Any]) -> None:
        state["updated_at"] = utc_now()
        write_json(self.state_path, state)

    def next_id(self, object_name: str) -> str:
        directory = self._object_dir(object_name)
        prefix = ID_PREFIXES[object_name]
        max_index = 0
        for path in directory.glob(f"{prefix}-*.json"):
            suffix = path.stem[len(prefix) + 1 :]
            if suffix.isdigit():
                max_index = max(max_index, int(suffix))
        return f"{prefix}-{max_index + 1:03d}"

    def save_object(self, object_name: str, payload: Dict[str, Any]) -> None:
        path = self._object_dir(object_name) / f"{payload['id']}.json"
        write_json(path, payload)

    def load_object(self, object_name: str, object_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not object_id:
            return None
        path = self._object_dir(object_name) / f"{object_id}.json"
        if not path.exists():
            return None
        return read_json(path)

    def require_object(self, object_name: str, object_id: str) -> Dict[str, Any]:
        payload = self.load_object(object_name, object_id)
        if payload is None:
            raise IntentError(
                EXIT_OBJECT_NOT_FOUND,
                "OBJECT_NOT_FOUND",
                f"{object_name.capitalize()} '{object_id}' was not found.",
                details={"id": object_id, "object": object_name},
            )
        return payload

    def list_objects(self, object_name: str) -> List[Dict[str, Any]]:
        directory = self._object_dir(object_name)
        if not directory.exists():
            return []
        payloads = [read_json(path) for path in directory.glob("*.json")]
        return sorted(payloads, key=object_sort_key)

    def show_config(self) -> Dict[str, Any]:
        self.ensure_git()
        self.ensure_initialized()
        return self.load_config()

    def object_list_item(self, object_name: str, payload: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        item = {
            "id": payload["id"],
            "title": payload["title"],
            "status": payload["status"],
            "created_at": payload["created_at"],
            "updated_at": payload["updated_at"],
        }
        if object_name == "intent":
            item["latest_checkpoint_id"] = payload.get("latest_checkpoint_id")
            item["latest_adoption_id"] = payload.get("latest_adoption_id")
            item["is_active"] = payload["id"] == state.get("active_intent_id")
        elif object_name == "checkpoint":
            item["intent_id"] = payload.get("intent_id")
            item["ordinal"] = payload.get("ordinal")
            item["selected"] = payload.get("selected", False)
            item["adopted"] = payload.get("adopted", False)
            item["adopted_by"] = payload.get("adopted_by")
            item["is_current"] = payload["id"] == state.get("current_checkpoint_id")
        elif object_name == "adoption":
            item["intent_id"] = payload.get("intent_id")
            item["checkpoint_id"] = payload.get("checkpoint_id")
            item["reverts_adoption_id"] = payload.get("reverts_adoption_id")
            item["is_latest"] = payload["id"] == state.get("last_adoption_id")
        return item

    def list_view(self, object_name: str) -> List[Dict[str, Any]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self.load_state()
        payloads = sorted(self.list_objects(object_name), key=object_sort_key, reverse=True)
        return [self.object_list_item(object_name, payload, state) for payload in payloads]

    def show_view(self, object_name: str, object_id: str) -> Dict[str, Any]:
        self.ensure_git()
        self.ensure_initialized()
        return self.require_object(object_name, object_id)

    def active_intent(self, state: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        state = state or self.load_state()
        return self.load_object("intent", state.get("active_intent_id"))

    def candidate_checkpoints(self, intent_id: Optional[str]) -> List[Dict[str, Any]]:
        if not intent_id:
            return []
        checkpoints = self.list_objects("checkpoint")
        return [
            checkpoint
            for checkpoint in checkpoints
            if checkpoint.get("intent_id") == intent_id
            and checkpoint.get("status") == "candidate"
            and not checkpoint.get("adopted")
        ]

    def latest_active_adoption(self, intent_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        adoptions = [
            adoption
            for adoption in self.list_objects("adoption")
            if adoption.get("status") == "active"
            and (intent_id is None or adoption.get("intent_id") == intent_id)
        ]
        if not adoptions:
            return None
        return sorted(adoptions, key=object_sort_key, reverse=True)[0]

    def derive_current_checkpoint(
        self,
        state: Dict[str, Any],
        active_intent: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        current = self.load_object("checkpoint", state.get("current_checkpoint_id"))
        if (
            current
            and active_intent
            and current.get("intent_id") == active_intent.get("id")
            and current.get("status") == "candidate"
            and not current.get("adopted")
            and current.get("selected")
        ):
            return current

        candidates = self.candidate_checkpoints(active_intent["id"] if active_intent else None)
        selected = [item for item in candidates if item.get("selected")]
        if len(selected) == 1:
            return selected[0]
        return None

    def derive_workspace_status(
        self,
        state: Dict[str, Any],
        active_intent: Optional[Dict[str, Any]],
        current_checkpoint: Optional[Dict[str, Any]],
    ) -> str:
        all_intents = self.list_objects("intent")
        if not active_intent:
            return "blocked_no_active_intent" if all_intents else "idle"

        candidates = self.candidate_checkpoints(active_intent["id"])
        selected = [item for item in candidates if item.get("selected")]
        if len(candidates) > 1 and len(selected) != 1:
            return "conflict_multiple_candidates"
        if current_checkpoint:
            return "candidate_ready"
        last_adoption = self.load_object("adoption", state.get("last_adoption_id"))
        if last_adoption and last_adoption.get("intent_id") == active_intent["id"]:
            return "adoption_recorded"
        return "intent_active"

    def snapshot(self) -> StatusSnapshot:
        self.ensure_git()
        self.ensure_initialized()
        state = self.load_state()
        active_intent = self.active_intent(state)
        current_checkpoint = self.derive_current_checkpoint(state, active_intent)
        git_payload, git_warnings = build_git_context(self.cwd)
        warnings = list(git_warnings)
        if current_checkpoint is not None and state.get("current_checkpoint_id") != current_checkpoint["id"]:
            state["current_checkpoint_id"] = current_checkpoint["id"]

        state["workspace_status"] = self.derive_workspace_status(state, active_intent, current_checkpoint)

        latest_adoption = None
        last_adoption_id = state.get("last_adoption_id")
        if last_adoption_id:
            candidate = self.load_object("adoption", last_adoption_id)
            if candidate and active_intent and candidate.get("intent_id") == active_intent["id"]:
                latest_adoption = candidate

        if latest_adoption is None and state["workspace_status"] == "adoption_recorded" and active_intent:
            latest_adoption = self.latest_active_adoption(active_intent["id"])
            state["last_adoption_id"] = latest_adoption["id"] if latest_adoption else None

        return StatusSnapshot(
            state=state,
            active_intent=active_intent,
            current_checkpoint=current_checkpoint,
            latest_adoption=latest_adoption,
            candidate_checkpoints=self.candidate_checkpoints(active_intent["id"] if active_intent else None),
            warnings=warnings,
            git=git_payload,
        )

    def refresh_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        snapshot = self.snapshot()
        state.update(snapshot.state)
        return state

    def create_intent(self, title: str, summary: str = "") -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self.load_state()
        previous = self.active_intent(state)
        if previous and previous.get("status") == "active":
            previous["status"] = "paused"
            previous["updated_at"] = utc_now()
            self.save_object("intent", previous)

        intent_id = self.next_id("intent")
        now = utc_now()
        intent = {
            "id": intent_id,
            "object": "intent",
            "schema_version": SCHEMA_VERSION,
            "created_at": now,
            "updated_at": now,
            "title": title,
            "summary": summary,
            "status": "active",
            "parent_intent_id": None,
            "tags": [],
            "latest_checkpoint_id": None,
            "latest_adoption_id": None,
            "metadata": {},
        }
        self.save_object("intent", intent)

        state["active_intent_id"] = intent_id
        state["current_checkpoint_id"] = None
        state["last_adoption_id"] = None
        state["workspace_status"] = "intent_active"
        self.save_state(state)
        return intent, state, []

    def create_checkpoint(self, title: str, summary: str = "") -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self.load_state()
        intent = self.active_intent(state)
        if not intent:
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "Cannot save a checkpoint without an active intent",
                suggested_fix='itt start "Describe the problem"',
            )

        current = self.derive_current_checkpoint(state, intent)
        if current:
            current["selected"] = False
            current["updated_at"] = utc_now()
            self.save_object("checkpoint", current)

        git_payload, warnings = build_git_context(self.cwd)
        checkpoint_id = self.next_id("checkpoint")
        ordinal = len([item for item in self.list_objects("checkpoint") if item.get("intent_id") == intent["id"]]) + 1
        now = utc_now()
        checkpoint = {
            "id": checkpoint_id,
            "object": "checkpoint",
            "schema_version": SCHEMA_VERSION,
            "created_at": now,
            "updated_at": now,
            "title": title,
            "summary": summary,
            "status": "candidate",
            "intent_id": intent["id"],
            "run_id": None,
            "ordinal": ordinal,
            "selected": True,
            "adopted": False,
            "adopted_by": None,
            "git": git_payload,
            "metadata": {},
        }
        self.save_object("checkpoint", checkpoint)

        intent["latest_checkpoint_id"] = checkpoint_id
        intent["updated_at"] = utc_now()
        self.save_object("intent", intent)

        state["current_checkpoint_id"] = checkpoint_id
        state["workspace_status"] = "candidate_ready"
        self.save_state(state)
        return checkpoint, state, warnings

    def select_checkpoint(self, checkpoint_id: str) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self.load_state()
        intent = self.active_intent(state)
        if not intent:
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "No active intent is available.",
                suggested_fix='itt start "Describe the problem"',
            )

        checkpoint = self.require_object("checkpoint", checkpoint_id)
        if checkpoint.get("intent_id") != intent["id"] or checkpoint.get("status") != "candidate":
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "Checkpoint does not belong to the active intent or is not selectable.",
                details={"checkpoint_id": checkpoint_id, "active_intent_id": intent["id"]},
            )

        for candidate in self.candidate_checkpoints(intent["id"]):
            candidate["selected"] = candidate["id"] == checkpoint_id
            candidate["updated_at"] = utc_now()
            self.save_object("checkpoint", candidate)

        checkpoint = self.require_object("checkpoint", checkpoint_id)
        state["current_checkpoint_id"] = checkpoint["id"]
        state["workspace_status"] = "candidate_ready"
        self.save_state(state)
        return checkpoint, state, []

    def _default_adoption_title(self, checkpoint: Dict[str, Any]) -> str:
        return f"Adopt {checkpoint['title']}"

    def create_adoption(
        self,
        message: Optional[str],
        checkpoint_id: Optional[str],
        rationale: str,
        if_not_adopted: bool,
        link_git: Optional[str],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[str], bool]:
        self.ensure_git()
        self.ensure_initialized()
        state = self.load_state()
        intent = self.active_intent(state)
        if not intent:
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "No active intent is available for adoption.",
                suggested_fix='itt start "Describe the problem"',
            )

        if checkpoint_id:
            checkpoint = self.require_object("checkpoint", checkpoint_id)
        else:
            checkpoint = self.derive_current_checkpoint(state, intent)
            if checkpoint is None:
                raise IntentError(
                    EXIT_STATE_CONFLICT,
                    "STATE_CONFLICT",
                    "Cannot adopt because the current checkpoint is not unambiguous",
                    details={"intent_id": intent["id"]},
                    suggested_fix="itt checkpoint select <id>",
                )

        if checkpoint.get("intent_id") != intent["id"]:
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "Checkpoint does not belong to the active intent.",
                details={"checkpoint_id": checkpoint["id"], "active_intent_id": intent["id"]},
            )

        existing_for_checkpoint = [
            adoption
            for adoption in self.list_objects("adoption")
            if adoption.get("checkpoint_id") == checkpoint["id"] and adoption.get("status") == "active"
        ]

        if checkpoint.get("status") != "candidate":
            if if_not_adopted and checkpoint.get("adopted") and existing_for_checkpoint:
                return existing_for_checkpoint[-1], state, [], True
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "Checkpoint is not available for adoption.",
                details={"checkpoint_id": checkpoint["id"], "status": checkpoint.get("status")},
            )

        if existing_for_checkpoint:
            if if_not_adopted:
                return existing_for_checkpoint[-1], state, [], True
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "Checkpoint already has an active adoption.",
                details={"checkpoint_id": checkpoint["id"]},
            )

        config = self.load_config()
        git_payload, warnings = build_git_context(self.cwd, explicit_ref=link_git)
        if config.get("git", {}).get("strict_adoption"):
            if git_payload["working_tree"] != "clean" or not git_payload.get("head"):
                raise IntentError(
                    EXIT_GENERAL_FAILURE,
                    "GIT_STATE_INVALID",
                    "Strict adoption requires a clean working tree and a resolvable HEAD.",
                    suggested_fix="Commit or clean your working tree before adopting",
                )

        adoption_id = self.next_id("adoption")
        now = utc_now()
        adoption = {
            "id": adoption_id,
            "object": "adoption",
            "schema_version": SCHEMA_VERSION,
            "created_at": now,
            "updated_at": now,
            "title": message or self._default_adoption_title(checkpoint),
            "summary": "",
            "status": "active",
            "intent_id": intent["id"],
            "checkpoint_id": checkpoint["id"],
            "rationale": rationale,
            "reverts_adoption_id": None,
            "git": git_payload,
            "metadata": {},
        }
        self.save_object("adoption", adoption)

        checkpoint["status"] = "adopted"
        checkpoint["adopted"] = True
        checkpoint["adopted_by"] = adoption_id
        checkpoint["selected"] = False
        checkpoint["updated_at"] = utc_now()
        self.save_object("checkpoint", checkpoint)

        intent["latest_adoption_id"] = adoption_id
        intent["updated_at"] = utc_now()
        self.save_object("intent", intent)

        state["current_checkpoint_id"] = None
        state["last_adoption_id"] = adoption_id
        state["workspace_status"] = self.derive_workspace_status(state, intent, None)
        self.save_state(state)
        return adoption, state, warnings, False

    def revert_adoption(
        self,
        message: Optional[str],
        rationale: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self.load_state()
        intent = self.active_intent(state)
        if not intent:
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "No active intent is available for revert.",
                suggested_fix='itt start "Describe the problem"',
            )

        target = self.latest_active_adoption(intent["id"])
        if not target:
            raise IntentError(
                EXIT_OBJECT_NOT_FOUND,
                "OBJECT_NOT_FOUND",
                "No active adoption is available to revert.",
            )

        git_payload, warnings = build_git_context(self.cwd)
        adoption_id = self.next_id("adoption")
        now = utc_now()
        revert_title = message or f"Revert {target['title']}"
        revert_record = {
            "id": adoption_id,
            "object": "adoption",
            "schema_version": SCHEMA_VERSION,
            "created_at": now,
            "updated_at": now,
            "title": revert_title,
            "summary": "",
            "status": "active",
            "intent_id": target["intent_id"],
            "checkpoint_id": target["checkpoint_id"],
            "rationale": rationale,
            "reverts_adoption_id": target["id"],
            "git": git_payload,
            "metadata": {},
        }
        self.save_object("adoption", revert_record)

        target["status"] = "reverted"
        target["updated_at"] = utc_now()
        self.save_object("adoption", target)

        checkpoint = self.require_object("checkpoint", target["checkpoint_id"])
        checkpoint["status"] = "reverted"
        checkpoint["adopted"] = False
        checkpoint["adopted_by"] = None
        checkpoint["selected"] = False
        checkpoint["updated_at"] = utc_now()
        self.save_object("checkpoint", checkpoint)

        intent["latest_adoption_id"] = adoption_id
        intent["updated_at"] = utc_now()
        self.save_object("intent", intent)

        state["current_checkpoint_id"] = None
        state["last_adoption_id"] = adoption_id
        state["workspace_status"] = self.derive_workspace_status(state, intent, None)
        self.save_state(state)
        return revert_record, state, warnings

    def next_action(self, snapshot: StatusSnapshot, *, machine: bool = False) -> Optional[Dict[str, str]]:
        status = snapshot.state["workspace_status"]
        if status in {"idle", "blocked_no_active_intent"}:
            return {
                "command": 'itt start "Describe the problem"',
                "reason": "No active intent is available.",
            }
        if status == "intent_active":
            return {
                "command": 'itt snap "First candidate"',
                "reason": "Active intent is ready for a first candidate.",
            }
        if status == "candidate_ready" and snapshot.current_checkpoint:
            command = (
                f'itt adopt --checkpoint {snapshot.current_checkpoint["id"]} -m "Adopt candidate"'
                if machine
                else 'itt adopt -m "Adopt candidate"'
            )
            return {
                "command": command,
                "reason": "Current checkpoint is ready for adoption.",
            }
        if status == "conflict_multiple_candidates":
            checkpoint = sorted(snapshot.candidate_checkpoints, key=lambda item: item["created_at"], reverse=True)[0]
            return {
                "command": f"itt checkpoint select {checkpoint['id']}",
                "reason": "Multiple candidate checkpoints exist and one must be selected.",
            }
        if status == "adoption_recorded":
            return {
                "command": "itt log",
                "reason": "Latest semantic history is available in the log.",
            }
        return None

    def state_warnings(self, snapshot: StatusSnapshot) -> List[str]:
        status = snapshot.state["workspace_status"]
        if status == "conflict_multiple_candidates":
            return ["Multiple candidate checkpoints exist and no unique current checkpoint is selected."]
        return []

    def pending_items(self, snapshot: StatusSnapshot) -> List[Dict[str, Any]]:
        status = snapshot.state["workspace_status"]
        if status == "candidate_ready" and snapshot.current_checkpoint:
            return [
                {
                    "type": "candidate",
                    "id": snapshot.current_checkpoint["id"],
                    "reason": "Ready for adoption",
                }
            ]
        if status == "conflict_multiple_candidates":
            return [
                {
                    "type": "candidate",
                    "id": checkpoint["id"],
                    "reason": "Candidate requires explicit selection",
                }
                for checkpoint in sorted(snapshot.candidate_checkpoints, key=lambda item: item["created_at"])
            ]
        return []

    def status_json(self) -> Dict[str, Any]:
        snapshot = self.snapshot()
        state = snapshot.state
        warnings = snapshot.warnings + self.state_warnings(snapshot)
        payload = {
            "ok": True,
            "object": "status",
            "schema_version": SCHEMA_VERSION,
            "active_intent": object_brief(snapshot.active_intent, include_status=False),
            "current_checkpoint": object_brief(snapshot.current_checkpoint, include_status=False),
            "latest_adoption": object_brief(snapshot.latest_adoption, include_status=False),
            "workspace_status": state["workspace_status"],
            "git": {
                "branch": snapshot.git["branch"],
                "head": snapshot.git["head"],
                "working_tree": snapshot.git["working_tree"],
            },
            "next_action": self.next_action(snapshot, machine=False),
            "warnings": warnings,
        }
        return payload

    def inspect_json(self) -> Dict[str, Any]:
        snapshot = self.snapshot()
        warnings = snapshot.warnings + self.state_warnings(snapshot)
        payload = {
            "ok": True,
            "object": "inspect",
            "schema_version": SCHEMA_VERSION,
            "mode": snapshot.state["mode"],
            "state": {
                "active_intent_id": snapshot.state.get("active_intent_id"),
                "active_run_id": snapshot.state.get("active_run_id"),
                "current_checkpoint_id": snapshot.state.get("current_checkpoint_id"),
                "last_adoption_id": snapshot.state.get("last_adoption_id"),
                "workspace_status": snapshot.state.get("workspace_status"),
            },
            "active_intent": object_brief(snapshot.active_intent, include_status=False),
            "current_checkpoint": object_brief(snapshot.current_checkpoint),
            "latest_adoption": object_brief(snapshot.latest_adoption, include_status=False),
            "pending_items": self.pending_items(snapshot),
            "suggested_next_actions": (
                [self.next_action(snapshot, machine=True)] if self.next_action(snapshot, machine=True) else []
            ),
            "git": {
                "branch": snapshot.git["branch"],
                "head": snapshot.git["head"],
                "working_tree": snapshot.git["working_tree"],
            },
            "warnings": warnings,
        }
        return payload

    def render_status_text(self) -> str:
        snapshot = self.snapshot()
        status = snapshot.state["workspace_status"]
        next_action = self.next_action(snapshot)
        if status in {"idle", "blocked_no_active_intent"}:
            return "\n".join(
                [
                    "Semantic workspace",
                    f"Status: {status}",
                    "No active intent",
                    f"Next: {next_action['command']}" if next_action else "",
                ]
            ).strip()

        lines = ["Semantic workspace"]
        if snapshot.active_intent:
            lines.append(f"Intent: {snapshot.active_intent['id']}  {snapshot.active_intent['title']}")
        if snapshot.current_checkpoint:
            lines.append(
                f"Current checkpoint: {snapshot.current_checkpoint['id']}  {snapshot.current_checkpoint['title']}"
            )
        lines.append(f"Status: {status}")
        if snapshot.latest_adoption and status == "adoption_recorded":
            lines.append(f"Latest adoption: {snapshot.latest_adoption['id']}  {snapshot.latest_adoption['title']}")
        if status == "conflict_multiple_candidates":
            lines.append("Warning: Multiple candidate checkpoints exist and no unique current checkpoint is selected")
        if next_action:
            lines.append(f"Next: {next_action['command']}")
        return "\n".join(lines)

    def render_log_text(self) -> str:
        self.ensure_git()
        self.ensure_initialized()
        adoptions = sorted(self.list_objects("adoption"), key=object_sort_key, reverse=True)
        if not adoptions:
            return "Semantic history\nNo adoptions recorded yet\nNext: itt status"

        lines = ["Semantic history", ""]
        for adoption in adoptions:
            created = adoption["created_at"].replace("T", " ").replace("Z", "")
            checkpoint = self.load_object("checkpoint", adoption.get("checkpoint_id"))
            intent = self.load_object("intent", adoption.get("intent_id"))
            git_head = (adoption.get("git") or {}).get("head") or "no-commit"
            lines.append(f"{created}  {adoption['id']}  {adoption['title']}")
            if intent:
                lines.append(f"  Intent: {intent['id']}  {intent['title']}")
            if checkpoint:
                lines.append(f"  Checkpoint: {checkpoint['id']}  {checkpoint['title']}")
            if adoption.get("reverts_adoption_id"):
                lines.append(f"  Reverts: {adoption['reverts_adoption_id']}")
            lines.append(f"  Git: {git_head}")
            lines.append("")
        return "\n".join(lines).rstrip()

    def render_config_text(self) -> str:
        config = self.show_config()
        lines = [
            "Intent config",
            f"Schema version: {config.get('schema_version')}",
            f"Strict adoption: {str(config.get('git', {}).get('strict_adoption', False)).lower()}",
        ]
        return "\n".join(lines)

    def render_object_list_text(self, object_name: str) -> str:
        items = self.list_view(object_name)
        label = OBJECT_PLURALS[object_name]
        if not items:
            return f"{label}\nNo {object_name}s recorded yet"

        lines = [label, ""]
        for item in items:
            details = [f"status={item['status']}"]
            if object_name == "intent":
                if item.get("is_active"):
                    details.append("active")
            elif object_name == "checkpoint":
                details.append(f"intent={item['intent_id']}")
                if item.get("selected"):
                    details.append("selected")
                if item.get("is_current"):
                    details.append("current")
                if item.get("adopted"):
                    details.append("adopted")
            elif object_name == "adoption":
                details.append(f"intent={item['intent_id']}")
                details.append(f"checkpoint={item['checkpoint_id']}")
                if item.get("is_latest"):
                    details.append("latest")
                if item.get("reverts_adoption_id"):
                    details.append(f"reverts={item['reverts_adoption_id']}")
            lines.append(f"{item['id']}  {item['title']} [{', '.join(details)}]")
        return "\n".join(lines)

    def render_object_show_text(self, object_name: str, object_id: str) -> str:
        payload = self.show_view(object_name, object_id)
        label = OBJECT_LABELS[object_name]
        lines = [
            f"{label} {payload['id']}",
            f"Title: {payload['title']}",
            f"Status: {payload['status']}",
        ]
        if payload.get("summary"):
            lines.append(f"Summary: {payload['summary']}")

        if object_name == "intent":
            lines.append(f"Latest checkpoint: {payload.get('latest_checkpoint_id') or 'none'}")
            lines.append(f"Latest adoption: {payload.get('latest_adoption_id') or 'none'}")
        elif object_name == "checkpoint":
            lines.append(f"Intent: {payload.get('intent_id')}")
            lines.append(f"Ordinal: {payload.get('ordinal')}")
            lines.append(f"Selected: {str(payload.get('selected', False)).lower()}")
            lines.append(f"Adopted: {str(payload.get('adopted', False)).lower()}")
            lines.append(f"Adopted by: {payload.get('adopted_by') or 'none'}")
            lines.append(f"Git: {summarize_git(payload.get('git', {}))}")
        elif object_name == "adoption":
            lines.append(f"Intent: {payload.get('intent_id')}")
            lines.append(f"Checkpoint: {payload.get('checkpoint_id')}")
            if payload.get("rationale"):
                lines.append(f"Because: {payload['rationale']}")
            lines.append(f"Reverts: {payload.get('reverts_adoption_id') or 'none'}")
            lines.append(f"Git: {summarize_git(payload.get('git', {}))}")
        return "\n".join(lines)
