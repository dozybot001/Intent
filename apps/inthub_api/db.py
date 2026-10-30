"""Database adapters for IntHub.

SQLite remains the zero-dependency local default. Production can use PostgreSQL
by passing a ``postgresql://`` URL; the rest of the API intentionally uses the
same small connection surface for both backends.
"""

import hashlib
import os
import threading
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from apps.inthub_api.db_connection import DatabaseConnection, _backend_for, _connect_raw
from apps.inthub_api.db_migrate import migrate_db, require_current_schema
from apps.inthub_api.db_schema import LATEST_SCHEMA_VERSION  # noqa: F401


_INITIALIZED = set()
_INIT_LOCK = threading.Lock()


def _auto_migrate_enabled():
    value = os.environ.get("INTHUB_AUTO_MIGRATE", "1").strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(
        "INTHUB_AUTO_MIGRATE must be one of 1/0, true/false, yes/no, or on/off"
    )


def connect(target):
    backend = _backend_for(target)
    raw = _connect_raw(target, backend)
    conn = DatabaseConnection(raw, backend)
    auto_migrate = _auto_migrate_enabled()
    key = (
        backend,
        hashlib.sha256(str(target).encode("utf-8")).hexdigest(),
        auto_migrate,
    )
    try:
        if key not in _INITIALIZED:
            with _INIT_LOCK:
                if key not in _INITIALIZED:
                    if auto_migrate:
                        init_db(conn)
                    else:
                        require_current_schema(conn)
                    _INITIALIZED.add(key)
        return conn
    except Exception:
        conn.close()
        raise


def migrate_target(target, *, require_backward_compatible=True):
    backend = _backend_for(target)
    conn = DatabaseConnection(_connect_raw(target, backend), backend)
    try:
        result = migrate_db(
            conn,
            require_backward_compatible=require_backward_compatible,
        )
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(conn):
    if not isinstance(conn, DatabaseConnection):
        conn = DatabaseConnection(conn, "sqlite")
    migrate_db(conn, require_backward_compatible=True)
    conn.commit()


def check_database(target):
    with connect(target) as conn:
        conn.execute("SELECT 1").fetchone()


def describe_database(target):
    """Return a log-safe database description with credentials removed."""
    if _backend_for(target) == "sqlite":
        return f"SQLite {Path(target).expanduser()}"
    parsed = urlsplit(str(target))
    host = parsed.hostname or "database"
    port = f":{parsed.port}" if parsed.port else ""
    database = parsed.path.lstrip("/") or "postgres"
    safe = urlunsplit(("postgresql", f"{host}{port}", f"/{database}", "", ""))
    return safe
