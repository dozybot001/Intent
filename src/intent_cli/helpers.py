from __future__ import annotations

import json
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")


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
    next_action: Optional[Dict[str, Any]] = None,
    *,
    state_changed: bool = True,
    noop: bool = False,
    reason: Optional[str] = None,
    workspace_status: Optional[str] = None,
    workspace_status_reason: Optional[str] = None,
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
    if workspace_status is not None:
        payload["workspace_status"] = workspace_status
    if workspace_status_reason is not None:
        payload["workspace_status_reason"] = workspace_status_reason
    return payload


def cli_action(args: List[str], reason: str) -> Dict[str, Any]:
    return {
        "command": shlex.join(["itt", *args]),
        "args": args,
        "reason": reason,
    }
