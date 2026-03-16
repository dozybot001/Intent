from __future__ import annotations

from typing import Any, Dict, Optional


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
