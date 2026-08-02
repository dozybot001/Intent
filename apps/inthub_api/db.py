"""Database adapters for IntHub.

SQLite remains the zero-dependency local default. Production can use PostgreSQL
by passing a ``postgresql://`` URL; the rest of the API intentionally uses the
same small connection surface for both backends.
"""

import hashlib
import sqlite3
import threading
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


_INITIALIZED = set()
_INIT_LOCK = threading.Lock()


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


def connect(target):
    backend = _backend_for(target)
    raw = _connect_raw(target, backend)
    conn = DatabaseConnection(raw, backend)
    key = (backend, hashlib.sha256(str(target).encode("utf-8")).hexdigest())
    try:
        if key not in _INITIALIZED:
            with _INIT_LOCK:
                if key not in _INITIALIZED:
                    init_db(conn)
                    _INITIALIZED.add(key)
        return conn
    except Exception:
        conn.close()
        raise


def _create_sqlite_schema(conn):
    conn.raw.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            repo_id TEXT NOT NULL UNIQUE,
            owner TEXT NOT NULL,
            repo_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            repo_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );
        """
    )

    existing = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'sync_batches'"
    ).fetchone()
    if existing is None:
        conn.raw.executescript(
            """
            CREATE TABLE sync_batches (
                sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT NOT NULL UNIQUE,
                project_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                accepted_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            );
            """
        )
    else:
        columns = set()
        for row in conn.execute("PRAGMA table_info(sync_batches)").fetchall():
            columns.add(row["name"] if hasattr(row, "keys") else row[1])
        if "sequence_id" not in columns:
            # v1 stored ordering implicitly in rowid. Rebuild once so the same
            # explicit ordering key works on SQLite and PostgreSQL.
            conn.raw.executescript(
                """
                ALTER TABLE sync_batches RENAME TO sync_batches_v1;
                CREATE TABLE sync_batches (
                    sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE,
                    project_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    accepted_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(id),
                    FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
                );
                INSERT INTO sync_batches (
                    sequence_id, id, project_id, workspace_id,
                    generated_at, accepted_at, payload_json
                )
                SELECT rowid, id, project_id, workspace_id,
                       generated_at, accepted_at, payload_json
                FROM sync_batches_v1
                ORDER BY rowid;
                DROP TABLE sync_batches_v1;
                """
            )

    conn.raw.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_workspaces_project
            ON workspaces(project_id);
        CREATE INDEX IF NOT EXISTS idx_sync_batches_project_workspace_sequence
            ON sync_batches(project_id, workspace_id, sequence_id DESC);
        CREATE INDEX IF NOT EXISTS idx_sync_batches_workspace_sequence
            ON sync_batches(workspace_id, sequence_id DESC);
        """
    )


def _create_postgresql_schema(conn):
    statements = (
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            repo_id TEXT NOT NULL,
            owner TEXT NOT NULL,
            repo_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (provider, repo_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES projects(id),
            provider TEXT NOT NULL,
            repo_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS sync_batches (
            sequence_id BIGSERIAL PRIMARY KEY,
            id TEXT NOT NULL UNIQUE,
            project_id TEXT NOT NULL REFERENCES projects(id),
            workspace_id TEXT NOT NULL REFERENCES workspaces(id),
            generated_at TEXT NOT NULL,
            accepted_at TEXT NOT NULL,
            payload_json TEXT NOT NULL
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_workspaces_project
            ON workspaces(project_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sync_batches_project_workspace_sequence
            ON sync_batches(project_id, workspace_id, sequence_id DESC)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_sync_batches_workspace_sequence
            ON sync_batches(workspace_id, sequence_id DESC)
        """,
    )
    for statement in statements:
        conn.execute(statement)


def init_db(conn):
    if not isinstance(conn, DatabaseConnection):
        conn = DatabaseConnection(conn, "sqlite")
    if getattr(conn, "backend", "sqlite") == "postgresql":
        _create_postgresql_schema(conn)
    else:
        _create_sqlite_schema(conn)
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
