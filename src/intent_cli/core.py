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

    def _active_decisions(self) -> List[Dict[str, Any]]:
        return sorted(
            [d for d in self.store.list_objects("decision") if d.get("status") == "active"],
            key=object_sort_key,
        )

    def _latest_active_snap(self, intent_id: str) -> Optional[Dict[str, Any]]:
        active = [
            s for s in self.store.list_objects("snap")
            if s.get("intent_id") == intent_id and s.get("status") == "active"
        ]
        if not active:
            return None
        return sorted(active, key=object_sort_key, reverse=True)[0]

    def _derive_workspace_status(self, state: Dict[str, Any]) -> str:
        intent = self._active_intent(state)
        if not intent:
            return "idle"
        return "active"

    def _attach_decisions_to_intent(self, intent: Dict[str, Any], decisions: List[Dict[str, Any]]) -> None:
        decision_ids = [d["id"] for d in decisions]
        intent["decision_ids"] = decision_ids
        intent["updated_at"] = utc_now()
        self.store.save_object("intent", intent)
        for d in decisions:
            if intent["id"] not in d.get("intent_ids", []):
                d.setdefault("intent_ids", []).append(intent["id"])
                d["updated_at"] = utc_now()
                self.store.save_object("decision", d)

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
                suggested_fix="itt done or itt suspend",
            )

        active_decisions = self._active_decisions()

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
            "decision_ids": [d["id"] for d in active_decisions],
        }
        self.store.save_object("intent", intent)

        for d in active_decisions:
            if intent_id not in d.get("intent_ids", []):
                d.setdefault("intent_ids", []).append(intent_id)
                d["updated_at"] = now
                self.store.save_object("decision", d)

        state["active_intent_id"] = intent_id
        state["workspace_status"] = "active"
        self._save_state(state)

        attached = [{"id": d["id"], "title": d["title"]} for d in active_decisions]
        return intent, [], attached

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

    def suspend_intent(self) -> Tuple[Dict[str, Any], List[str]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self._load_state()
        intent = self._require_active_intent(state)

        intent["status"] = "suspended"
        intent["updated_at"] = utc_now()
        self.store.save_object("intent", intent)

        state["active_intent_id"] = None
        state["workspace_status"] = "idle"
        self._save_state(state)
        return intent, []

    def resume_intent(self, intent_id: Optional[str] = None) -> Tuple[Dict[str, Any], List[str], List[Dict[str, Any]]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self._load_state()

        current = self._active_intent(state)
        if current and current.get("status") == "open":
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                f"Intent '{current['id']}' is still open.",
                suggested_fix="itt suspend or itt done",
            )

        suspended = [
            i for i in self.store.list_objects("intent")
            if i.get("status") == "suspended"
        ]

        if intent_id:
            intent = self.store.require_object("intent", intent_id)
            if intent.get("status") != "suspended":
                raise IntentError(
                    EXIT_STATE_CONFLICT,
                    "STATE_CONFLICT",
                    f"Intent '{intent_id}' is not suspended.",
                )
        elif len(suspended) == 1:
            intent = suspended[0]
        elif len(suspended) == 0:
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "No suspended intents to resume.",
                suggested_fix='itt start "Describe the problem"',
            )
        else:
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "Multiple suspended intents. Specify which one to resume.",
                details={
                    "suspended": [{"id": i["id"], "title": i["title"]} for i in suspended],
                },
                suggested_fix=f"itt resume {suspended[-1]['id']}",
            )

        intent["status"] = "open"
        intent["updated_at"] = utc_now()

        # Re-attach active decisions (catch up on decisions created while suspended)
        active_decisions = self._active_decisions()
        self._attach_decisions_to_intent(intent, active_decisions)

        state["active_intent_id"] = intent["id"]
        state["workspace_status"] = "active"
        self._save_state(state)

        attached = [{"id": d["id"], "title": d["title"]} for d in active_decisions]
        return intent, [], attached

    # --- snap lifecycle ---

    def create_snap(
        self,
        title: str,
        rationale: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], List[str]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self._load_state()
        intent = self._require_active_intent(state)

        git_payload, warnings = build_git_context(self.cwd)
        snap_id = self.store.next_id("snap")
        now = utc_now()
        snap = {
            "id": snap_id,
            "object": "snap",
            "schema_version": SCHEMA_VERSION,
            "created_at": now,
            "updated_at": now,
            "title": title,
            "rationale": rationale or "",
            "status": "active",
            "intent_id": intent["id"],
            "git": git_payload,
        }
        self.store.save_object("snap", snap)
        return snap, warnings

    def revert_snap(self, rationale: Optional[str] = None) -> Tuple[Dict[str, Any], List[str]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self._load_state()
        intent = self._require_active_intent(state)

        latest = self._latest_active_snap(intent["id"])
        if not latest:
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "No active snap to revert.",
                suggested_fix='itt snap "Describe the step"',
            )

        latest["status"] = "reverted"
        if rationale:
            latest["rationale"] = rationale
        latest["updated_at"] = utc_now()
        self.store.save_object("snap", latest)
        return latest, []

    # --- decision lifecycle ---

    def create_decision(
        self,
        title: str,
        rationale: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], List[str]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self._load_state()

        decision_id = self.store.next_id("decision")
        now = utc_now()

        intent = self._active_intent(state)
        created_from = intent["id"] if intent else None
        intent_ids = [intent["id"]] if intent else []

        decision = {
            "id": decision_id,
            "object": "decision",
            "schema_version": SCHEMA_VERSION,
            "created_at": now,
            "updated_at": now,
            "title": title,
            "rationale": rationale or "",
            "status": "active",
            "intent_ids": intent_ids,
            "created_from_intent_id": created_from,
        }
        self.store.save_object("decision", decision)

        # Attach decision to active intent
        if intent:
            intent.setdefault("decision_ids", []).append(decision_id)
            intent["updated_at"] = now
            self.store.save_object("intent", intent)

        return decision, []

    def deprecate_decision(
        self,
        decision_id: Optional[str] = None,
        rationale: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], List[str]]:
        self.ensure_git()
        self.ensure_initialized()

        active_decisions = self._active_decisions()

        if decision_id:
            decision = self.store.require_object("decision", decision_id)
            if decision.get("status") != "active":
                raise IntentError(
                    EXIT_STATE_CONFLICT,
                    "STATE_CONFLICT",
                    f"Decision '{decision_id}' is not active.",
                )
        elif len(active_decisions) == 1:
            decision = active_decisions[0]
        elif len(active_decisions) == 0:
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "No active decisions to deprecate.",
                suggested_fix='itt decide "Describe the decision"',
            )
        else:
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "Multiple active decisions. Specify which one to deprecate.",
                details={
                    "active_decisions": [{"id": d["id"], "title": d["title"]} for d in active_decisions],
                },
                suggested_fix=f"itt deprecate {active_decisions[-1]['id']}",
            )

        decision["status"] = "deprecated"
        if rationale:
            decision["rationale"] = rationale
        decision["updated_at"] = utc_now()
        self.store.save_object("decision", decision)
        return decision, []

    # --- read ---

    def inspect(self) -> Dict[str, Any]:
        self.ensure_git()
        self.ensure_initialized()
        state = self._load_state()
        intent = self._active_intent(state)
        git_payload, git_warnings = build_git_context(self.cwd)

        latest_snap = None
        if intent:
            latest_snap = self._latest_active_snap(intent["id"])

        suspended_intents = [
            {"id": i["id"], "title": i["title"]}
            for i in self.store.list_objects("intent")
            if i.get("status") == "suspended"
        ]

        active_decisions = [
            {"id": d["id"], "title": d["title"], "status": d["status"]}
            for d in self._active_decisions()
        ]

        workspace_status = self._derive_workspace_status(state)
        if workspace_status != state.get("workspace_status"):
            state["workspace_status"] = workspace_status
            self._save_state(state)

        def brief(obj: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
            if not obj:
                return None
            keys = ("id", "title", "status", "rationale", "decision_ids")
            return {k: obj[k] for k in keys if k in obj}

        action = self._next_action(intent, suspended_intents)

        return {
            "ok": True,
            "schema_version": SCHEMA_VERSION,
            "workspace_status": workspace_status,
            "intent": brief(intent),
            "latest_snap": brief(latest_snap),
            "active_decisions": active_decisions,
            "suspended_intents": suspended_intents,
            "suggested_next_action": action,
            "git": {
                "branch": git_payload["branch"],
                "head": git_payload["head"],
                "working_tree": git_payload["working_tree"],
            },
            "warnings": git_warnings,
        }

    def list_objects(self, object_name: str, intent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        self.ensure_git()
        self.ensure_initialized()
        if object_name not in ("intent", "snap", "decision"):
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                f"Unknown object type: {object_name}",
                suggested_fix="Use 'intent', 'snap', or 'decision'.",
            )
        items = self.store.list_objects(object_name)
        if intent_id and object_name == "snap":
            items = [s for s in items if s.get("intent_id") == intent_id]
        return sorted(items, key=object_sort_key, reverse=True)

    def show_object(self, object_id: str) -> Dict[str, Any]:
        self.ensure_git()
        self.ensure_initialized()
        object_name = self._type_from_id(object_id)
        return self.store.require_object(object_name, object_id)

    # --- internal ---

    def _type_from_id(self, object_id: str) -> str:
        if object_id.startswith("intent-"):
            return "intent"
        if object_id.startswith("snap-"):
            return "snap"
        if object_id.startswith("decision-"):
            return "decision"
        raise IntentError(
            EXIT_OBJECT_NOT_FOUND,
            "OBJECT_NOT_FOUND",
            f"Cannot determine type for id '{object_id}'.",
            suggested_fix="Use a valid id like 'intent-001', 'snap-001', or 'decision-001'.",
        )

    def _next_action(
        self,
        intent: Optional[Dict[str, Any]],
        suspended: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        if not intent or intent.get("status") != "open":
            if suspended:
                return {
                    "command": f"itt resume {suspended[-1]['id']}",
                    "reason": "Suspended intents exist.",
                }
            return {"command": "itt start 'Describe the problem'", "reason": "No active intent."}
        return {"command": "itt snap 'Describe the step'", "reason": "Intent is active."}
