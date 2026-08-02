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
            account_id TEXT,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            repo_id TEXT NOT NULL,
            owner TEXT NOT NULL,
            repo_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (account_id, provider, repo_id)
        );

        CREATE TABLE IF NOT EXISTS workspaces (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            repo_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );

        CREATE TABLE IF NOT EXISTS sync_batches (
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

    conn.raw.executescript(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            provider_user_id TEXT NOT NULL,
            login TEXT NOT NULL,
            display_name TEXT,
            avatar_url TEXT,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_login_at TEXT NOT NULL,
            UNIQUE (provider, provider_user_id)
        );

        CREATE TABLE IF NOT EXISTS oauth_login_attempts (
            state_hash TEXT PRIMARY KEY,
            code_verifier TEXT NOT NULL,
            return_to TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS web_sessions (
            id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            account_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS account_access_tokens (
            id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            account_id TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_used_at TEXT,
            revoked_at TEXT,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_web_sessions_account
            ON web_sessions(account_id);
        CREATE INDEX IF NOT EXISTS idx_web_sessions_expires
            ON web_sessions(expires_at);
        CREATE INDEX IF NOT EXISTS idx_oauth_login_attempts_expires
            ON oauth_login_attempts(expires_at);
        CREATE INDEX IF NOT EXISTS idx_account_access_tokens_account
            ON account_access_tokens(account_id);
        CREATE INDEX IF NOT EXISTS idx_account_access_tokens_expires
            ON account_access_tokens(expires_at);
        CREATE INDEX IF NOT EXISTS idx_projects_account
            ON projects(account_id);

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
            account_id TEXT,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            repo_id TEXT NOT NULL,
            owner TEXT NOT NULL,
            repo_name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (account_id, provider, repo_id)
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
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            provider_user_id TEXT NOT NULL,
            login TEXT NOT NULL,
            display_name TEXT,
            avatar_url TEXT,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_login_at TEXT NOT NULL,
            UNIQUE (provider, provider_user_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS oauth_login_attempts (
            state_hash TEXT PRIMARY KEY,
            code_verifier TEXT NOT NULL,
            return_to TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS web_sessions (
            id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS account_access_tokens (
            id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            last_used_at TEXT,
            revoked_at TEXT
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_web_sessions_account
            ON web_sessions(account_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_web_sessions_expires
            ON web_sessions(expires_at)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_oauth_login_attempts_expires
            ON oauth_login_attempts(expires_at)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_account_access_tokens_account
            ON account_access_tokens(account_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_account_access_tokens_expires
            ON account_access_tokens(expires_at)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_projects_account
            ON projects(account_id)
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
