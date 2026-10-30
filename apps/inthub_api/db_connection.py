"""One small connection surface over SQLite and PostgreSQL."""

import sqlite3
from pathlib import Path
from urllib.parse import urlsplit


def _backend_for(target):
    scheme = urlsplit(str(target)).scheme.lower()
    if scheme in {"postgres", "postgresql"}:
        return "postgresql"
    return "sqlite"


def _postgres_sql(sql):
    """Translate the portable qmark statements used by the API to psycopg."""
    return sql.replace("?", "%s")


class DatabaseConnection:
    """Closeable, context-managed connection with portable execute semantics."""

    def __init__(self, raw, backend):
        self.raw = raw
        self.backend = backend

    def execute(self, sql, params=()):
        if self.backend == "postgresql":
            sql = _postgres_sql(sql)
        return self.raw.execute(sql, params)

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self.raw.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, _exc, _traceback):
        try:
            if exc_type is None:
                self.raw.commit()
            else:
                self.raw.rollback()
        finally:
            self.raw.close()
        return False


def _connect_raw(target, backend):
    if backend == "sqlite":
        path = Path(target).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = sqlite3.connect(path, check_same_thread=False, timeout=5)
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA foreign_keys = ON")
        raw.execute("PRAGMA busy_timeout = 5000")
        raw.execute("PRAGMA journal_mode = WAL")
        return raw

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:  # pragma: no cover - exercised in server image
        raise RuntimeError(
            "PostgreSQL support requires the 'server' extra: pip install '.[server]'"
        ) from exc
    return psycopg.connect(str(target), row_factory=dict_row, connect_timeout=5)
