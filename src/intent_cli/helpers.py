from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple


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
