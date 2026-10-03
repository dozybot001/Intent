"""One-time operator identity binding. Exact IDs arrive through protected stdin."""

import json
import os
import sys

from apps.inthub_api.tenon import bind_existing_account


def main():
    try:
        if os.getenv("INTHUB_IDENTITY_MAINTENANCE") != "1":
            raise ValueError("Maintenance authorization required")
        data = json.loads(sys.stdin.read(4097))
        result = bind_existing_account(os.environ["INTHUB_DATABASE_URL"], data["account_id"], data["subject"])
    except Exception:
        print(json.dumps({"ok": False, "error": "Identity binding failed; check exact IDs and conflicts."}))
        return 1
    print(json.dumps({"ok": True, "result": result}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
