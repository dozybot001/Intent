"""Database adapters for IntHub.

SQLite remains the zero-dependency local default. Production can use PostgreSQL
by passing a ``postgresql://`` URL; the rest of the API intentionally uses the
same small connection surface for both backends.
"""

import hashlib
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


_INITIALIZED = set()
_INIT_LOCK = threading.Lock()

LATEST_SCHEMA_VERSION = 2
_INITIAL_SCHEMA_NAME = "initial-account-scoped-schema"
_INITIAL_SCHEMA_CHECKSUM = hashlib.sha256(
    b"0001:initial-account-scoped-schema:projects-account:tokens:sync-sequence"
).hexdigest()
_PUBLIC_PROFILES_SCHEMA_NAME = "public-profiles-with-explicit-project-grants"
_PUBLIC_PROFILES_SCHEMA_CHECKSUM = hashlib.sha256(
    b"0002:public-profiles:explicit-project-grants"
).hexdigest()
_EXPECTED_SCHEMA_COLUMNS_V1 = {
    "projects": {
        "id",
        "account_id",
        "name",
        "provider",
        "repo_id",
        "owner",
        "repo_name",
        "created_at",
    },
    "workspaces": {"id", "project_id", "provider", "repo_id", "created_at"},
    "sync_batches": {
        "sequence_id",
        "id",
        "project_id",
        "workspace_id",
        "generated_at",
        "accepted_at",
        "payload_json",
    },
    "accounts": {
        "id",
        "provider",
        "provider_user_id",
        "login",
        "display_name",
        "avatar_url",
        "role",
        "created_at",
        "updated_at",
        "last_login_at",
    },
    "oauth_login_attempts": {
        "state_hash",
        "code_verifier",
        "return_to",
        "created_at",
        "expires_at",
    },
    "web_sessions": {
        "id",
        "token_hash",
        "account_id",
        "created_at",
        "expires_at",
        "last_seen_at",
    },
    "account_access_tokens": {
        "id",
        "token_hash",
        "account_id",
        "name",
        "created_at",
        "expires_at",
        "last_used_at",
        "revoked_at",
    },
}
_EXPECTED_SCHEMA_COLUMNS_V2 = {
    "public_profiles": {
        "slug",
        "account_id",
        "title",
        "description",
        "created_at",
        "updated_at",
    },
    "public_profile_projects": {
        "profile_slug",
        "project_id",
        "position",
        "published_at",
    },
}
_EXPECTED_SCHEMA_COLUMNS = {
    **_EXPECTED_SCHEMA_COLUMNS_V1,
    **_EXPECTED_SCHEMA_COLUMNS_V2,
}


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


def _create_sqlite_public_profiles_schema(conn):
    conn.raw.executescript(
        """
        CREATE TABLE IF NOT EXISTS public_profiles (
            slug TEXT PRIMARY KEY,
            account_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS public_profile_projects (
            profile_slug TEXT NOT NULL,
            project_id TEXT NOT NULL UNIQUE,
            position INTEGER NOT NULL,
            published_at TEXT NOT NULL,
            PRIMARY KEY (profile_slug, project_id),
            FOREIGN KEY (profile_slug) REFERENCES public_profiles(slug) ON DELETE CASCADE,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_public_profile_projects_profile_position
            ON public_profile_projects(profile_slug, position, project_id);
        """
    )


def _create_postgresql_public_profiles_schema(conn):
    statements = (
        """
        CREATE TABLE IF NOT EXISTS public_profiles (
            slug TEXT PRIMARY KEY,
            account_id TEXT NOT NULL UNIQUE REFERENCES accounts(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS public_profile_projects (
            profile_slug TEXT NOT NULL REFERENCES public_profiles(slug) ON DELETE CASCADE,
            project_id TEXT NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            published_at TEXT NOT NULL,
            PRIMARY KEY (profile_slug, project_id)
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_public_profile_projects_profile_position
            ON public_profile_projects(profile_slug, position, project_id)
        """,
    )
    for statement in statements:
        conn.execute(statement)


def _ensure_migration_ledger(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            checksum TEXT NOT NULL,
            backward_compatible INTEGER NOT NULL,
            applied_at TEXT NOT NULL
        )
        """
    )


def _migration_ledger_exists(conn):
    if conn.backend == "sqlite":
        row = conn.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'schema_migrations'
            """
        ).fetchone()
        return row is not None
    row = conn.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = 'schema_migrations'
        """
    ).fetchone()
    return row is not None


def _migration_rows(conn):
    return conn.execute(
        """
        SELECT version, name, checksum, backward_compatible, applied_at
        FROM schema_migrations
        ORDER BY version
        """
    ).fetchall()


def _observed_schema_columns(conn):
    if conn.backend == "sqlite":
        observed = {}
        for table_name in _EXPECTED_SCHEMA_COLUMNS:
            rows = conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            observed[table_name] = {row["name"] for row in rows}
        return observed

    rows = conn.execute(
        """
        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
        """
    ).fetchall()
    observed = {table_name: set() for table_name in _EXPECTED_SCHEMA_COLUMNS}
    for row in rows:
        table_name = row["table_name"]
        if table_name in observed:
            observed[table_name].add(row["column_name"])
    return observed


def _validate_schema(conn, expected_schema_columns):
    observed = _observed_schema_columns(conn)
    problems = []
    for table_name, expected_columns in expected_schema_columns.items():
        missing = sorted(expected_columns - observed.get(table_name, set()))
        if missing:
            problems.append(f"{table_name}: missing {','.join(missing)}")
    if problems:
        raise RuntimeError("database schema validation failed: " + "; ".join(problems))


def _validate_migration_ledger(rows):
    known = {
        1: {
            "name": _INITIAL_SCHEMA_NAME,
            "checksum": _INITIAL_SCHEMA_CHECKSUM,
            "backward_compatible": 1,
        },
        2: {
            "name": _PUBLIC_PROFILES_SCHEMA_NAME,
            "checksum": _PUBLIC_PROFILES_SCHEMA_CHECKSUM,
            "backward_compatible": 1,
        },
    }
    observed_versions = set()
    for row in rows:
        version = int(row["version"])
        if version in observed_versions:
            raise RuntimeError(f"duplicate database migration version: {version}")
        observed_versions.add(version)
        if version in known:
            expected = known[version]
            for field, expected_value in expected.items():
                if row[field] != expected_value:
                    raise RuntimeError(
                        f"database migration {version} has invalid {field}"
                    )
        elif int(row["backward_compatible"]) != 1:
            raise RuntimeError(
                f"database contains unknown incompatible migration: {version}"
            )
    if observed_versions and 1 not in observed_versions:
        raise RuntimeError("database migration ledger is missing baseline version 1")


def migrate_db(conn, *, require_backward_compatible=True):
    """Apply and validate the versioned, expand/contract schema migrations."""
    if not isinstance(conn, DatabaseConnection):
        conn = DatabaseConnection(conn, "sqlite")
    _ensure_migration_ledger(conn)
    rows = _migration_rows(conn)
    _validate_migration_ledger(rows)
    before_version = max((int(row["version"]) for row in rows), default=0)
    applied_versions = {int(row["version"]) for row in rows}

    if 1 not in applied_versions:
        backward_compatible = True
        if require_backward_compatible and not backward_compatible:
            raise RuntimeError("pending database migration is not backward compatible")
        if conn.backend == "postgresql":
            _create_postgresql_schema(conn)
        else:
            _create_sqlite_schema(conn)
        _validate_schema(conn, _EXPECTED_SCHEMA_COLUMNS_V1)
        conn.execute(
            """
            INSERT INTO schema_migrations
                (version, name, checksum, backward_compatible, applied_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                1,
                _INITIAL_SCHEMA_NAME,
                _INITIAL_SCHEMA_CHECKSUM,
                1,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    if 2 not in applied_versions:
        backward_compatible = True
        if require_backward_compatible and not backward_compatible:
            raise RuntimeError("pending database migration is not backward compatible")
        if conn.backend == "postgresql":
            _create_postgresql_public_profiles_schema(conn)
        else:
            _create_sqlite_public_profiles_schema(conn)
        _validate_schema(conn, _EXPECTED_SCHEMA_COLUMNS)
        conn.execute(
            """
            INSERT INTO schema_migrations
                (version, name, checksum, backward_compatible, applied_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                2,
                _PUBLIC_PROFILES_SCHEMA_NAME,
                _PUBLIC_PROFILES_SCHEMA_CHECKSUM,
                1,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    rows = _migration_rows(conn)
    _validate_migration_ledger(rows)
    _validate_schema(conn, _EXPECTED_SCHEMA_COLUMNS)
    to_version = max((int(row["version"]) for row in rows), default=0)
    if to_version < LATEST_SCHEMA_VERSION:
        raise RuntimeError("database did not reach the latest schema version")
    return {
        "from_version": before_version,
        "to_version": to_version,
        "latest_known_version": LATEST_SCHEMA_VERSION,
        "backward_compatible_only": bool(require_backward_compatible),
    }


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


def current_schema_version(conn):
    if not _migration_ledger_exists(conn):
        return 0
    rows = _migration_rows(conn)
    _validate_migration_ledger(rows)
    return max((int(row["version"]) for row in rows), default=0)


def require_current_schema(conn):
    """Validate a production schema without applying or creating anything."""
    version = current_schema_version(conn)
    if version < LATEST_SCHEMA_VERSION:
        raise RuntimeError(
            "database schema migration is required before the application starts"
        )
    _validate_schema(conn, _EXPECTED_SCHEMA_COLUMNS)
    return version


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
