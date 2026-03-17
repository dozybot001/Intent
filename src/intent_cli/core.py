from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .constants import (
    EXIT_GENERAL_FAILURE,
    EXIT_INVALID_INPUT,
    EXIT_OBJECT_NOT_FOUND,
    EXIT_STATE_CONFLICT,
    OBJECT_SELECTORS,
    SCHEMA_VERSION,
)
from .errors import IntentError
from .git import build_git_context, ensure_git_worktree
from .helpers import cli_action, object_brief, object_sort_key, utc_now
from .render import (
    render_config_text,
    render_log_text,
    render_object_list_text,
    render_object_show_text,
    render_status_text,
)
from .store import IntentStore


@dataclass
class StatusSnapshot:
    state: Dict[str, Any]
    active_intent: Optional[Dict[str, Any]]
    active_run: Optional[Dict[str, Any]]
    current_checkpoint: Optional[Dict[str, Any]]
    latest_adoption: Optional[Dict[str, Any]]
    latest_decision: Optional[Dict[str, Any]]
    candidate_checkpoints: List[Dict[str, Any]]
    warnings: List[str]
    git: Dict[str, Any]


class IntentRepository:
    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.store = IntentStore(cwd)

    def ensure_git(self) -> None:
        ensure_git_worktree(self.cwd)

    def is_initialized(self) -> bool:
        return self.store.is_initialized()

    def ensure_initialized(self) -> None:
        self.store.ensure_initialized()

    def init_workspace(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        self.ensure_git()
        return self.store.init_workspace()

    def load_config(self) -> Dict[str, Any]:
        return self.store.load_config()

    def load_state(self) -> Dict[str, Any]:
        return self.store.load_state()

    def save_state(self, state: Dict[str, Any]) -> None:
        self.store.save_state(state)

    def next_id(self, object_name: str) -> str:
        return self.store.next_id(object_name)

    def save_object(self, object_name: str, payload: Dict[str, Any]) -> None:
        self.store.save_object(object_name, payload)

    def load_object(self, object_name: str, object_id: Optional[str]) -> Optional[Dict[str, Any]]:
        return self.store.load_object(object_name, object_id)

    def require_object(self, object_name: str, object_id: str) -> Dict[str, Any]:
        return self.store.require_object(object_name, object_id)

    def resolve_object_reference(self, object_name: str, object_ref: str) -> Dict[str, Any]:
        if not object_ref.startswith("@"):
            return self.require_object(object_name, object_ref)

        if object_ref not in OBJECT_SELECTORS.get(object_name, set()):
            raise IntentError(
                EXIT_INVALID_INPUT,
                "INVALID_INPUT",
                f"Selector '{object_ref}' is not valid for {object_name} objects.",
                details={"selector": object_ref, "object": object_name},
            )

        state = self.load_state()
        if object_name == "intent":
            payload = self.active_intent(state)
            suggested_fix = 'itt start "Describe the problem"'
            extra_details: Dict[str, Any] = {}
        elif object_name == "checkpoint":
            active_intent = self.active_intent(state)
            payload = self.derive_current_checkpoint(state, active_intent)
            candidate_details = self.checkpoint_selector_candidates(active_intent["id"] if active_intent else None)
            suggested_fix = self.checkpoint_selector_fix(active_intent["id"] if active_intent else None)
            extra_details = {"candidate_checkpoints": candidate_details} if candidate_details else {}
        elif object_name == "adoption":
            active_intent = self.active_intent(state)
            payload = self.load_object("adoption", state.get("last_adoption_id"))
            if payload and active_intent and payload.get("intent_id") != active_intent.get("id"):
                payload = None
            if payload is None and active_intent:
                payload = self.latest_active_adoption(active_intent["id"])
            suggested_fix = self.adoption_selector_fix(state, active_intent) if active_intent else 'itt start "Describe the problem"'
            candidate_details = self.checkpoint_selector_candidates(active_intent["id"] if active_intent else None)
            extra_details = {"candidate_checkpoints": candidate_details} if candidate_details else {}
        elif object_name == "run":
            payload = self.active_run(state)
            suggested_fix = "itt run start"
            extra_details = {}
        elif object_name == "decision":
            active_intent = self.active_intent(state)
            decisions = [
                decision
                for decision in self.list_objects("decision")
                if active_intent is None or decision.get("intent_id") == active_intent.get("id")
            ]
            payload = sorted(decisions, key=object_sort_key, reverse=True)[0] if decisions else None
            suggested_fix = "itt decide <title>"
            extra_details = {}
        else:
            payload = None
            suggested_fix = None
            extra_details = {}

        if payload is None:
            details = {"selector": object_ref, "object": object_name}
            details.update(extra_details)
            raise IntentError(
                EXIT_OBJECT_NOT_FOUND,
                "OBJECT_NOT_FOUND",
                f"No {object_name} is available for selector '{object_ref}'.",
                details=details,
                suggested_fix=suggested_fix,
            )
        return payload

    def list_objects(self, object_name: str) -> List[Dict[str, Any]]:
        payloads = self.store.list_objects(object_name)
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
            item["run_id"] = payload.get("run_id")
            item["ordinal"] = payload.get("ordinal")
            item["selected"] = payload.get("selected", False)
            item["adopted"] = payload.get("adopted", False)
            item["adopted_by"] = payload.get("adopted_by")
            item["is_current"] = payload["id"] == state.get("current_checkpoint_id")
        elif object_name == "adoption":
            item["intent_id"] = payload.get("intent_id")
            item["checkpoint_id"] = payload.get("checkpoint_id")
            item["run_id"] = payload.get("run_id")
            item["reverts_adoption_id"] = payload.get("reverts_adoption_id")
            item["is_latest"] = payload["id"] == state.get("last_adoption_id")
        elif object_name == "run":
            item["intent_id"] = payload.get("intent_id")
            item["is_active"] = payload["id"] == state.get("active_run_id")
        elif object_name == "decision":
            item["intent_id"] = payload.get("intent_id")
            item["run_id"] = payload.get("run_id")
            item["adoption_id"] = payload.get("adoption_id")
            item["checkpoint_id"] = payload.get("checkpoint_id")
        return item

    def list_view(self, object_name: str) -> List[Dict[str, Any]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self.load_state()
        payloads = sorted(self.list_objects(object_name), key=object_sort_key, reverse=True)
        return [self.object_list_item(object_name, payload, state) for payload in payloads]

    def show_view(self, object_name: str, object_ref: str) -> Dict[str, Any]:
        self.ensure_git()
        self.ensure_initialized()
        return self.resolve_object_reference(object_name, object_ref)

    def active_intent(self, state: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        state = state or self.load_state()
        return self.load_object("intent", state.get("active_intent_id"))

    def active_run(self, state: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        state = state or self.load_state()
        run = self.load_object("run", state.get("active_run_id"))
        if run and run.get("status") == "active":
            return run
        return None

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

    def latest_decision(self, intent_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        decisions = [
            decision
            for decision in self.list_objects("decision")
            if intent_id is None or decision.get("intent_id") == intent_id
        ]
        if not decisions:
            return None
        return sorted(decisions, key=object_sort_key, reverse=True)[0]

    def decisions_for_adoption(self, adoption_id: str) -> List[Dict[str, Any]]:
        decisions = [
            decision
            for decision in self.list_objects("decision")
            if decision.get("adoption_id") == adoption_id
        ]
        return sorted(decisions, key=object_sort_key, reverse=True)

    def standalone_decisions(self) -> List[Dict[str, Any]]:
        decisions = [
            decision
            for decision in self.list_objects("decision")
            if not decision.get("adoption_id")
        ]
        return sorted(decisions, key=object_sort_key, reverse=True)

    def checkpoint_selector_candidates(self, intent_id: Optional[str]) -> List[Dict[str, Any]]:
        return [
            {"id": checkpoint["id"], "title": checkpoint["title"]}
            for checkpoint in sorted(self.candidate_checkpoints(intent_id), key=object_sort_key, reverse=True)
        ]

    def checkpoint_selector_fix(self, intent_id: Optional[str]) -> str:
        candidates = self.checkpoint_selector_candidates(intent_id)
        if candidates:
            return f"itt checkpoint select {candidates[0]['id']}"
        return 'itt snap "First candidate"'

    def resolve_checkpoint_argument(
        self,
        state: Dict[str, Any],
        intent: Dict[str, Any],
        checkpoint_ref: str,
    ) -> Dict[str, Any]:
        if not checkpoint_ref.startswith("@"):
            return self.require_object("checkpoint", checkpoint_ref)

        checkpoint = self.derive_current_checkpoint(state, intent)
        if checkpoint is not None:
            return checkpoint

        candidate_details = self.checkpoint_selector_candidates(intent["id"])
        raise IntentError(
            EXIT_STATE_CONFLICT,
            "STATE_CONFLICT",
            "Cannot resolve --checkpoint because the current checkpoint is not unambiguous.",
            details={
                "intent_id": intent["id"],
                "selector": checkpoint_ref,
                "candidate_checkpoints": candidate_details,
            },
            suggested_fix=self.checkpoint_selector_fix(intent["id"]),
        )

    def adoption_selector_fix(self, state: Dict[str, Any], intent: Optional[Dict[str, Any]]) -> str:
        if intent is None:
            return 'itt start "Describe the problem"'
        current_checkpoint = self.derive_current_checkpoint(state, intent)
        if current_checkpoint is not None:
            return f'itt adopt --checkpoint {current_checkpoint["id"]} -m "Adopt candidate"'
        return self.checkpoint_selector_fix(intent["id"])

    def resolve_adoption_argument(
        self,
        state: Dict[str, Any],
        intent: Dict[str, Any],
        adoption_ref: str,
    ) -> Dict[str, Any]:
        if not adoption_ref.startswith("@"):
            return self.require_object("adoption", adoption_ref)

        latest_adoption = self.load_object("adoption", state.get("last_adoption_id"))
        if latest_adoption and latest_adoption.get("intent_id") == intent["id"]:
            return latest_adoption

        latest_adoption = self.latest_active_adoption(intent["id"])
        if latest_adoption is not None:
            return latest_adoption

        candidate_details = self.checkpoint_selector_candidates(intent["id"])
        raise IntentError(
            EXIT_OBJECT_NOT_FOUND,
            "OBJECT_NOT_FOUND",
            f"No adoption is available for selector '{adoption_ref}'.",
            details={
                "selector": adoption_ref,
                "object": "adoption",
                "intent_id": intent["id"],
                "candidate_checkpoints": candidate_details,
            },
            suggested_fix=self.adoption_selector_fix(state, intent),
        )

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
        active_run = self.active_run(state)
        current_checkpoint = self.derive_current_checkpoint(state, active_intent)
        git_payload, git_warnings = build_git_context(self.cwd)
        warnings = list(git_warnings)
        if active_run is None and state.get("active_run_id") is not None:
            state["active_run_id"] = None
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
            active_run=active_run,
            current_checkpoint=current_checkpoint,
            latest_adoption=latest_adoption,
            latest_decision=self.latest_decision(active_intent["id"] if active_intent else None),
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
        if self.active_run(state):
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "Cannot switch the active intent while a run is active.",
                suggested_fix="itt run end",
            )
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
        active_run = self.active_run(state)
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
            "run_id": active_run["id"] if active_run else None,
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

    def create_run(self, title: Optional[str]) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self.load_state()
        intent = self.active_intent(state)
        active_run = self.active_run(state)
        if not intent:
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "No active intent is available for starting a run.",
                suggested_fix='itt start "Describe the problem"',
            )

        if self.active_run(state):
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "An active run already exists.",
                suggested_fix="itt run end",
            )

        git_payload, warnings = build_git_context(self.cwd)
        run_id = self.next_id("run")
        now = utc_now()
        run = {
            "id": run_id,
            "object": "run",
            "schema_version": SCHEMA_VERSION,
            "created_at": now,
            "updated_at": now,
            "title": title or f"Run {run_id}",
            "summary": "",
            "status": "active",
            "intent_id": intent["id"],
            "run_id": None,
            "git": git_payload,
            "metadata": {},
        }
        self.save_object("run", run)

        state["active_run_id"] = run_id
        self.save_state(state)
        return run, state, warnings

    def end_run(self) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self.load_state()
        run = self.active_run(state)
        if not run:
            raise IntentError(
                EXIT_OBJECT_NOT_FOUND,
                "OBJECT_NOT_FOUND",
                "No active run is available to end.",
                suggested_fix="itt run start",
            )

        run["status"] = "completed"
        run["updated_at"] = utc_now()
        self.save_object("run", run)

        state["active_run_id"] = None
        self.save_state(state)
        return run, state, []

    def create_decision(
        self,
        title: str,
        rationale: str,
        adoption_id: Optional[str],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        self.ensure_git()
        self.ensure_initialized()
        state = self.load_state()
        intent = self.active_intent(state)
        if not intent:
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "No active intent is available for creating a decision.",
                suggested_fix='itt start "Describe the problem"',
            )

        active_run = self.active_run(state)
        adoption: Optional[Dict[str, Any]] = None
        checkpoint: Optional[Dict[str, Any]] = None

        if adoption_id:
            adoption = self.resolve_adoption_argument(state, intent, adoption_id)
            if adoption.get("intent_id") != intent["id"]:
                raise IntentError(
                    EXIT_STATE_CONFLICT,
                    "STATE_CONFLICT",
                    "Adoption does not belong to the active intent.",
                    details={"adoption_id": adoption_id, "active_intent_id": intent["id"]},
                )
        else:
            latest_adoption = self.load_object("adoption", state.get("last_adoption_id"))
            if latest_adoption and latest_adoption.get("intent_id") == intent["id"]:
                adoption = latest_adoption

        if adoption:
            checkpoint = self.load_object("checkpoint", adoption.get("checkpoint_id"))

        git_payload, warnings = build_git_context(self.cwd)
        decision_id = self.next_id("decision")
        now = utc_now()
        decision = {
            "id": decision_id,
            "object": "decision",
            "schema_version": SCHEMA_VERSION,
            "created_at": now,
            "updated_at": now,
            "title": title,
            "summary": "",
            "status": "active",
            "intent_id": intent["id"],
            "run_id": active_run["id"] if active_run else None,
            "adoption_id": adoption["id"] if adoption else None,
            "checkpoint_id": checkpoint["id"] if checkpoint else None,
            "rationale": rationale,
            "git": git_payload,
            "metadata": {},
        }
        self.save_object("decision", decision)
        return decision, state, warnings

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
        active_run = self.active_run(state)
        if not intent:
            raise IntentError(
                EXIT_STATE_CONFLICT,
                "STATE_CONFLICT",
                "No active intent is available for adoption.",
                suggested_fix='itt start "Describe the problem"',
            )

        if checkpoint_id:
            checkpoint = self.resolve_checkpoint_argument(state, intent, checkpoint_id)
        else:
            checkpoint = self.derive_current_checkpoint(state, intent)
            if checkpoint is None:
                candidate_details = self.checkpoint_selector_candidates(intent["id"])
                raise IntentError(
                    EXIT_STATE_CONFLICT,
                    "STATE_CONFLICT",
                    "Cannot adopt because the current checkpoint is not unambiguous",
                    details={
                        "intent_id": intent["id"],
                        "candidate_checkpoints": candidate_details,
                    },
                    suggested_fix=self.checkpoint_selector_fix(intent["id"]),
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
            "run_id": active_run["id"] if active_run else None,
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

        active_run = self.active_run(state)
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
            "run_id": active_run["id"] if active_run else None,
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

    def next_action(self, snapshot: StatusSnapshot, *, machine: bool = False) -> Optional[Dict[str, Any]]:
        status = snapshot.state["workspace_status"]
        if status in {"idle", "blocked_no_active_intent"}:
            return cli_action(["start", "Describe the problem"], "No active intent is available.")
        if status == "intent_active":
            return cli_action(["snap", "First candidate"], "Active intent is ready for a first candidate.")
        if status == "candidate_ready" and snapshot.current_checkpoint:
            args = (
                ["adopt", "--checkpoint", snapshot.current_checkpoint["id"], "-m", "Adopt candidate"]
                if machine
                else ["adopt", "-m", "Adopt candidate"]
            )
            return cli_action(args, "Current checkpoint is ready for adoption.")
        if status == "conflict_multiple_candidates":
            checkpoint = sorted(snapshot.candidate_checkpoints, key=object_sort_key, reverse=True)[0]
            return cli_action(
                ["checkpoint", "select", checkpoint["id"]],
                "Multiple candidate checkpoints exist and one must be selected.",
            )
        if status == "adoption_recorded":
            return cli_action(["log"], "Latest semantic history is available in the log.")
        return None

    def workspace_status_reason(self, snapshot: StatusSnapshot) -> str:
        status = snapshot.state["workspace_status"]
        if status == "idle":
            return "No intents have been created in this workspace."
        if status == "blocked_no_active_intent":
            return "Intents exist, but none is currently active."
        if status == "intent_active":
            return "An active intent exists, but there is no current checkpoint."
        if status == "candidate_ready":
            return "A current checkpoint is available for adoption."
        if status == "adoption_recorded":
            return "The latest semantic event is an adoption or revert record."
        if status == "conflict_multiple_candidates":
            return "Multiple candidate checkpoints exist without a unique current selection."
        return "Workspace status is available."

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
                for checkpoint in sorted(snapshot.candidate_checkpoints, key=object_sort_key)
            ]
        return []

    def candidate_checkpoint_briefs(self, snapshot: StatusSnapshot) -> List[Dict[str, Any]]:
        return [
            {
                "id": checkpoint["id"],
                "title": checkpoint["title"],
                "status": checkpoint["status"],
                "selected": checkpoint.get("selected", False),
                "adopted": checkpoint.get("adopted", False),
            }
            for checkpoint in sorted(snapshot.candidate_checkpoints, key=object_sort_key, reverse=True)
        ]

    def latest_event(self, snapshot: StatusSnapshot) -> Optional[Dict[str, Any]]:
        adoption = snapshot.latest_adoption
        if adoption is None:
            candidate = self.load_object("adoption", snapshot.state.get("last_adoption_id"))
            if candidate is not None:
                adoption = candidate
        if adoption is None:
            return None
        return {
            "type": "revert" if adoption.get("reverts_adoption_id") else "adoption",
            "id": adoption["id"],
            "title": adoption["title"],
            "checkpoint_id": adoption.get("checkpoint_id"),
            "reverts_adoption_id": adoption.get("reverts_adoption_id"),
        }

    def status_json(self) -> Dict[str, Any]:
        snapshot = self.snapshot()
        state = snapshot.state
        warnings = snapshot.warnings + self.state_warnings(snapshot)
        payload = {
            "ok": True,
            "object": "status",
            "schema_version": SCHEMA_VERSION,
            "active_intent": object_brief(snapshot.active_intent, include_status=False),
            "active_run": object_brief(snapshot.active_run, include_status=False),
            "current_checkpoint": object_brief(snapshot.current_checkpoint, include_status=False),
            "latest_adoption": object_brief(snapshot.latest_adoption, include_status=False),
            "workspace_status": state["workspace_status"],
            "workspace_status_reason": self.workspace_status_reason(snapshot),
            "git": {
                "branch": snapshot.git["branch"],
                "head": snapshot.git["head"],
                "working_tree": snapshot.git["working_tree"],
            },
            "next_action": self.next_action(snapshot, machine=True),
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
            "active_run": object_brief(snapshot.active_run, include_status=False),
            "current_checkpoint": object_brief(snapshot.current_checkpoint),
            "latest_adoption": object_brief(snapshot.latest_adoption, include_status=False),
            "latest_decision": object_brief(snapshot.latest_decision, include_status=False),
            "latest_event": self.latest_event(snapshot),
            "candidate_checkpoints": self.candidate_checkpoint_briefs(snapshot),
            "workspace_status_reason": self.workspace_status_reason(snapshot),
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
        return render_status_text(self)

    def render_log_text(self) -> str:
        return render_log_text(self)

    def render_config_text(self) -> str:
        return render_config_text(self)

    def render_object_list_text(self, object_name: str) -> str:
        return render_object_list_text(self, object_name)

    def render_object_show_text(self, object_name: str, object_ref: str) -> str:
        return render_object_show_text(self, object_name, object_ref)
