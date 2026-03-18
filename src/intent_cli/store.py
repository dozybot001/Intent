from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .constants import DIR_NAMES, EXIT_GENERAL_FAILURE, EXIT_OBJECT_NOT_FOUND, ID_PREFIXES, SCHEMA_VERSION
from .errors import IntentError
from .helpers import read_json, utc_now, write_json

AGENT_INSTRUCTIONS = """\
# Intent — semantic history

This repo uses Intent (`.intent/`) to track what you're doing and why.
If `itt` is not found, use `python3 -m intent_cli` instead.

## Workflow

1. **Session start** → run `itt inspect` to check workspace state
   - **active** → read the intent and latest snap rationale, continue where it left off
   - **suspended intents** → consider `itt resume [id]`
   - **idle** → `itt start "<goal>"` if this session involves substantive work
2. **Begin substantive work** → `itt start "What goal am I pursuing"`
   - An intent is a goal, not a task — keep it high-level
   - Skip for trivial questions or tiny edits
3. **Before each git commit** → `itt snap "What I did" -m "Why, and what comes next"`
   - Snap before commit, not after — this is the key trigger point
4. **Switching context** → `itt suspend`, then `itt start` or `itt resume`
5. **Goal complete** → `itt done`

## Object semantics

- **Intent** = a goal, not a task. One intent may span multiple snaps and commits.
  Title answers: "What problem am I solving?"
  Example: "Migrate auth to JWT", not "Add JWT token generation".
- **Snap** = a step taken toward the intent. Title answers: "What did I do?"
- **Rationale** (`-m`) = the most valuable field. It must give the next session
  everything it needs to continue without re-explaining. Include:
  - What's done, what's in progress, what's remaining
  - Decisions made and why
  - Strategic context (constraints, deadlines, dependencies)

All `itt` output is JSON — parse it, don't guess.
"""


class IntentStore:
    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.intent_dir = cwd / ".intent"
        self.config_path = self.intent_dir / "config.json"
        self.state_path = self.intent_dir / "state.json"

    def is_initialized(self) -> bool:
        return self.intent_dir.exists() and self.config_path.exists() and self.state_path.exists()

    def ensure_initialized(self) -> None:
        if not self.is_initialized():
            raise IntentError(
                EXIT_GENERAL_FAILURE,
                "NOT_INITIALIZED",
                "Intent is not initialized in this repository.",
                suggested_fix="itt init",
            )

    def object_dir(self, object_name: str) -> Path:
        return self.intent_dir / DIR_NAMES[object_name]

    def init_workspace(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if self.intent_dir.exists():
            raise IntentError(
                EXIT_GENERAL_FAILURE,
                "ALREADY_EXISTS",
                "Intent is already initialized in this repository.",
            )

        self.intent_dir.mkdir()
        for dir_name in DIR_NAMES.values():
            (self.intent_dir / dir_name).mkdir()

        config: Dict[str, Any] = {"schema_version": SCHEMA_VERSION}
        state: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "active_intent_id": None,
            "workspace_status": "idle",
            "updated_at": utc_now(),
        }
        write_json(self.config_path, config)
        write_json(self.state_path, state)

        self._write_agent_instructions()

        return config, state

    def _write_agent_instructions(self) -> None:
        claude_dir = self.cwd / ".claude"
        instructions_path = claude_dir / "instructions.md"
        if instructions_path.exists():
            return
        claude_dir.mkdir(exist_ok=True)
        instructions_path.write_text(AGENT_INSTRUCTIONS, encoding="utf-8")

    def load_state(self) -> Dict[str, Any]:
        self.ensure_initialized()
        return read_json(self.state_path)

    def save_state(self, state: Dict[str, Any]) -> None:
        state["updated_at"] = utc_now()
        write_json(self.state_path, state)

    def next_id(self, object_name: str) -> str:
        directory = self.object_dir(object_name)
        prefix = ID_PREFIXES[object_name]
        max_index = 0
        for path in directory.glob(f"{prefix}-*.json"):
            suffix = path.stem[len(prefix) + 1:]
            if suffix.isdigit():
                max_index = max(max_index, int(suffix))
        return f"{prefix}-{max_index + 1:03d}"

    def save_object(self, object_name: str, payload: Dict[str, Any]) -> None:
        path = self.object_dir(object_name) / f"{payload['id']}.json"
        write_json(path, payload)

    def load_object(self, object_name: str, object_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not object_id:
            return None
        path = self.object_dir(object_name) / f"{object_id}.json"
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
        directory = self.object_dir(object_name)
        if not directory.exists():
            return []
        return [read_json(path) for path in directory.glob("*.json")]
