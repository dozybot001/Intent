"""Sign the CLI in through the browser, as `gh auth login` does.

The terminal shows a short code and waits. A signed-in browser enters the code
and approves it, and the CLI then collects an ordinary access token, which
appears under Settings and can be revoked there. No secret travels through the
browser, so this also works over SSH and on machines without one.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from apps.inthub_api.auth import create_account_access_token
from apps.inthub_api.common import APIError, new_id, now_utc
from apps.inthub_api.db import connect

LOGIN_TTL = timedelta(minutes=10)
POLL_SECONDS = 3
TOKEN_TTL_SECONDS = 90 * 24 * 60 * 60
NAME_MAX = 100
PENDING_MAX = 100_000
VERIFICATION_PATH = "/device"
# Consonants only: no digits to confuse with letters, and no accidental words.
CODE_ALPHABET = "BCDFGHJKLMNPQRSTVWXZ"
CODE_LENGTH = 8
CODE_INVALID = "This code is not valid or has expired. Run itt auth login again."


def _hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _expired(row):
    return datetime.fromisoformat(row["expires_at"]) <= datetime.now(timezone.utc)


def _clean_name(value):
    name = "".join(char for char in value if ord(char) >= 32 and ord(char) != 127).strip() if isinstance(value, str) else ""
    return name[:NAME_MAX] or "itt"


def _user_code():
    code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
    return f"{code[:4]}-{code[4:]}"


def _pending(conn, code):
    """The undecided request behind a code as typed: case and the hyphen do not matter."""
    typed = "".join(char for char in code.upper() if char.isalnum()) if isinstance(code, str) else ""
    if len(typed) != CODE_LENGTH:
        raise APIError("DEVICE_CODE_INVALID", CODE_INVALID, 404)
    row = conn.execute(
        "SELECT id, name, expires_at, decided_at FROM device_logins WHERE user_hash = ?",
        (_hash(f"{typed[:4]}-{typed[4:]}"),),
    ).fetchone()
    if row is None or row["decided_at"] or _expired(row):
        raise APIError("DEVICE_CODE_INVALID", CODE_INVALID, 404)
    return row


def start_device_login(db_target, name):
    device_code = f"ith_dev_{secrets.token_urlsafe(32)}"
    user_code = _user_code()
    created_at = now_utc()
    expires_at = (datetime.now(timezone.utc) + LOGIN_TTL).isoformat()
    with connect(db_target) as conn:
        conn.execute("DELETE FROM device_logins WHERE expires_at <= ?", (created_at,))
        pending = conn.execute("SELECT COUNT(*) AS total FROM device_logins").fetchone()["total"]
        if pending >= PENDING_MAX:
            raise APIError("RATE_LIMITED", "Too many sign-ins are in progress. Try again in a few minutes.", 429)
        conn.execute(
            """INSERT INTO device_logins (id, device_hash, user_hash, name, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (new_id("dev"), _hash(device_code), _hash(user_code), _clean_name(name), created_at, expires_at),
        )
    return {
        "device_code": device_code,
        "user_code": user_code,
        "verification_path": VERIFICATION_PATH,
        "expires_in": int(LOGIN_TTL.total_seconds()),
        "interval": POLL_SECONDS,
    }


def describe_device_login(db_target, code):
    with connect(db_target) as conn:
        row = _pending(conn, code)
    return {"name": row["name"], "token_days": TOKEN_TTL_SECONDS // 86400}


def decide_device_login(db_target, code, approve, account_id):
    with connect(db_target) as conn:
        row = _pending(conn, code)
        conn.execute(
            "UPDATE device_logins SET account_id = ?, decided_at = ? WHERE id = ? AND decided_at IS NULL",
            (account_id if approve is True else None, now_utc(), row["id"]),
        )
    return {"approved": approve is True, "name": row["name"]}


def poll_device_login(db_target, device_code):
    """The CLI's answer. A token leaves here once: collecting it removes the request."""
    if not isinstance(device_code, str) or not device_code.startswith("ith_dev_"):
        return {"status": "expired"}
    with connect(db_target) as conn:
        row = conn.execute(
            "SELECT id, name, expires_at, account_id, decided_at FROM device_logins WHERE device_hash = ?",
            (_hash(device_code),),
        ).fetchone()
        if row is None:
            return {"status": "expired"}
        if not row["decided_at"]:
            if not _expired(row):
                return {"status": "pending"}
            conn.execute("DELETE FROM device_logins WHERE id = ?", (row["id"],))
            return {"status": "expired"}
        if conn.execute("DELETE FROM device_logins WHERE id = ?", (row["id"],)).rowcount != 1 or not row["account_id"]:
            return {"status": "denied"}
    token = create_account_access_token(db_target, row["account_id"], name=row["name"], ttl_seconds=TOKEN_TTL_SECONDS)
    return {"status": "approved", "token": token["token"], "expires_at": token["expires_at"]}
