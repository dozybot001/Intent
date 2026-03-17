from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .constants import EXIT_OBJECT_NOT_FOUND, EXIT_STATE_CONFLICT, SCHEMA_VERSION
from .errors import IntentError
from .git import build_git_context, ensure_git_worktree
from .helpers import object_sort_key, utc_now
from .store import IntentStore


class IntentRepository:
    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.store = IntentStore(cwd)

    # --- guards ---

    def ensure_git(self) -> None:
        ensure_git_worktree(self.cwd)

    def ensure_initialized(self) -> None:
        self.store.ensure_initialized()

    # --- init ---

    def init_workspace(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        self.ensure_git()
        return self.store.init_workspace()

    # --- state helpers ---

    def _load_state(self) -> Dict[str, Any]:
        return self.store.load_state()

    def _save_state(self, state: Dict[str, Any]) -> None:
        self.store.save_state(state)

    def _active_intent(self, state: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        state = state or self._load_state()
        return self.store.load_object("intent", state.get("active_intent_id"))

    def _require_active_intent(self, state: Dict[str, Any]) -> Dict[str, Any]:
        intent = self._active_intent(state)
        if not intent:
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "No active intent.",
                suggested_fix='itt start "Describe the problem"',
            )
        return intent

    def _candidate_checkpoints(self, intent_id: str) -> List[Dict[str, Any]]:
        return sorted(
            [
                cp for cp in self.store.list_objects("checkpoint")
                if cp.get("intent_id") == intent_id and cp.get("status") == "candidate"
            ],
            key=object_sort_key,
        )

    def _latest_adopted(self, intent_id: str) -> Optional[Dict[str, Any]]:
        adopted = [
            cp for cp in self.store.list_objects("checkpoint")
            if cp.get("intent_id") == intent_id and cp.get("status") == "adopted"
        ]
        if not adopted:
            return None
        return sorted(adopted, key=object_sort_key, reverse=True)[0]

    def _derive_workspace_status(self, state: Dict[str, Any]) -> str:
        intent = self._active_intent(state)
        if not intent:
            return "idle"
        candidates = self._candidate_checkpoints(intent["id"])
        if len(candidates) > 1:
            return "conflict"
        return "active"

    # --- intent lifecycle ---

    def create_intent(self, title: str) -> Tuple[Dict[str, Any], List[str]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self._load_state()

        current = self._active_intent(state)
        if current and current.get("status") == "open":
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                f"Intent '{current['id']}' is still open.",
                suggested_fix="itt done",
            )

        intent_id = self.store.next_id("intent")
        now = utc_now()
        intent = {
            "id": intent_id,
            "object": "intent",
            "schema_version": SCHEMA_VERSION,
            "created_at": now,
            "updated_at": now,
            "title": title,
            "status": "open",
        }
        self.store.save_object("intent", intent)

        state["active_intent_id"] = intent_id
        state["workspace_status"] = "active"
        self._save_state(state)
        return intent, []

    def close_intent(self, intent_id: Optional[str] = None) -> Tuple[Dict[str, Any], List[str]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self._load_state()

        if intent_id:
            intent = self.store.require_object("intent", intent_id)
        else:
            intent = self._require_active_intent(state)

        if intent.get("status") == "done":
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                f"Intent '{intent['id']}' is already done.",
            )

        intent["status"] = "done"
        intent["updated_at"] = utc_now()
        self.store.save_object("intent", intent)

        if intent["id"] == state.get("active_intent_id"):
            state["active_intent_id"] = None
            state["workspace_status"] = "idle"
            self._save_state(state)

        return intent, []

    # --- checkpoint lifecycle ---

    def create_checkpoint(
        self,
        title: str,
        rationale: Optional[str] = None,
        candidate: bool = False,
    ) -> Tuple[Dict[str, Any], List[str]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self._load_state()
        intent = self._require_active_intent(state)

        git_payload, warnings = build_git_context(self.cwd)
        checkpoint_id = self.store.next_id("checkpoint")
        now = utc_now()
        status = "candidate" if candidate else "adopted"
        checkpoint = {
            "id": checkpoint_id,
            "object": "checkpoint",
            "schema_version": SCHEMA_VERSION,
            "created_at": now,
            "updated_at": now,
            "title": title,
            "rationale": rationale or "",
            "status": status,
            "intent_id": intent["id"],
            "git": git_payload,
        }
        self.store.save_object("checkpoint", checkpoint)

        state["workspace_status"] = self._derive_workspace_status(state)
        self._save_state(state)
        return checkpoint, warnings

    def adopt_checkpoint(
        self,
        checkpoint_id: Optional[str] = None,
        rationale: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], List[str]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self._load_state()
        intent = self._require_active_intent(state)

        candidates = self._candidate_checkpoints(intent["id"])

        if checkpoint_id:
            checkpoint = self.store.require_object("checkpoint", checkpoint_id)
            if checkpoint.get("intent_id") != intent["id"]:
                raise IntentError(
                    EXIT_STATE_CONFLICT,
                    "STATE_CONFLICT",
                    "Checkpoint does not belong to the active intent.",
                    details={"checkpoint_id": checkpoint_id, "intent_id": intent["id"]},
                )
            if checkpoint.get("status") != "candidate":
                raise IntentError(
                    EXIT_STATE_CONFLICT,
                    "STATE_CONFLICT",
                    f"Checkpoint '{checkpoint_id}' is not a candidate.",
                )
        elif len(candidates) == 1:
            checkpoint = candidates[0]
        elif len(candidates) == 0:
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "No candidate checkpoints to adopt.",
                suggested_fix='itt snap "Describe the step" --candidate',
            )
        else:
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "Multiple candidates exist. Specify which one to adopt.",
                details={
                    "candidates": [{"id": c["id"], "title": c["title"]} for c in candidates],
                },
                suggested_fix=f"itt adopt {candidates[-1]['id']}",
            )

        checkpoint["status"] = "adopted"
        if rationale:
            checkpoint["rationale"] = rationale
        checkpoint["updated_at"] = utc_now()
        self.store.save_object("checkpoint", checkpoint)

        state["workspace_status"] = self._derive_workspace_status(state)
        self._save_state(state)
        return checkpoint, []

    def revert_checkpoint(self, rationale: Optional[str] = None) -> Tuple[Dict[str, Any], List[str]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self._load_state()
        intent = self._require_active_intent(state)

        latest = self._latest_adopted(intent["id"])
        if not latest:
            raise IntentError(
                EXIT_OBJECT_NOT_FOUND,
                "OBJECT_NOT_FOUND",
                "No adopted checkpoint to revert.",
            )

        latest["status"] = "reverted"
        if rationale:
            latest["rationale"] = rationale
        latest["updated_at"] = utc_now()
        self.store.save_object("checkpoint", latest)

        state["workspace_status"] = self._derive_workspace_status(state)
        self._save_state(state)
        return latest, []

    # --- read ---

    def inspect(self) -> Dict[str, Any]:
        self.ensure_git()
        self.ensure_initialized()
        state = self._load_state()
        intent = self._active_intent(state)
        git_payload, git_warnings = build_git_context(self.cwd)

        latest_checkpoint = None
        candidate_checkpoints: List[Dict[str, Any]] = []
        if intent:
            latest_checkpoint = self._latest_adopted(intent["id"])
            candidate_checkpoints = [
                {"id": c["id"], "title": c["title"]}
                for c in self._candidate_checkpoints(intent["id"])
            ]

        workspace_status = self._derive_workspace_status(state)
        if workspace_status != state.get("workspace_status"):
            state["workspace_status"] = workspace_status
            self._save_state(state)

        def brief(obj: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
            if not obj:
                return None
            return {k: obj[k] for k in ("id", "title", "status") if k in obj}

        action = self._next_action(intent, candidate_checkpoints)

        return {
            "ok": True,
            "schema_version": SCHEMA_VERSION,
            "workspace_status": workspace_status,
            "intent": brief(intent),
            "latest_checkpoint": brief(latest_checkpoint),
            "candidate_checkpoints": candidate_checkpoints,
            "suggested_next_action": action,
            "git": {
                "branch": git_payload["branch"],
                "head": git_payload["head"],
                "working_tree": git_payload["working_tree"],
            },
            "warnings": git_warnings,
        }

    def list_objects(self, object_name: str) -> List[Dict[str, Any]]:
        self.ensure_git()
        self.ensure_initialized()
        if object_name not in ("intent", "checkpoint"):
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                f"Unknown object type: {object_name}",
                suggested_fix="Use 'intent' or 'checkpoint'.",
            )
        return sorted(self.store.list_objects(object_name), key=object_sort_key, reverse=True)

    def show_object(self, object_id: str) -> Dict[str, Any]:
        self.ensure_git()
        self.ensure_initialized()
        object_name = self._type_from_id(object_id)
        return self.store.require_object(object_name, object_id)

    # --- internal ---

    def _type_from_id(self, object_id: str) -> str:
        if object_id.startswith("intent-"):
            return "intent"
        if object_id.startswith("cp-"):
            return "checkpoint"
        raise IntentError(
            EXIT_OBJECT_NOT_FOUND,
            "OBJECT_NOT_FOUND",
            f"Cannot determine type for id '{object_id}'.",
            suggested_fix="Use a valid id like 'intent-001' or 'cp-001'.",
        )

    def _next_action(
        self,
        intent: Optional[Dict[str, Any]],
        candidates: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not intent or intent.get("status") != "open":
            return {"command": "itt start 'Describe the problem'", "reason": "No active intent."}
        if len(candidates) > 1:
            return {
                "command": f"itt adopt {candidates[-1]['id']}",
                "reason": "Multiple candidates — pick one to adopt.",
            }
        if len(candidates) == 1:
            return {
                "command": f"itt adopt {candidates[0]['id']}",
                "reason": "One candidate ready for adoption.",
            }
        return {"command": "itt snap 'Describe the step'", "reason": "Intent is active."}
