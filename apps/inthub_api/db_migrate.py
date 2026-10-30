"""Apply and check schema migrations against a ledger, one backward-compatible step at a time."""

from datetime import datetime, timezone
from apps.inthub_api.db_connection import DatabaseConnection
from apps.inthub_api.db_schema import _create_postgresql_public_profiles_schema, _create_postgresql_schema, _create_sqlite_public_profiles_schema, _create_sqlite_schema, _create_tenon_schema
from apps.inthub_api.db_schema import LATEST_SCHEMA_VERSION, _DELETION_SCHEMA_CHECKSUM, _DELETION_SCHEMA_NAME, _EXPECTED_SCHEMA_COLUMNS, _EXPECTED_SCHEMA_COLUMNS_V1, _EXPECTED_SCHEMA_COLUMNS_V2, _EXPECTED_SCHEMA_COLUMNS_V3, _HISTORY_SCHEMA_CHECKSUM, _HISTORY_SCHEMA_NAME, _HOSTED_SCHEMA_CHECKSUM, _HOSTED_SCHEMA_NAME, _IDENTITY_COLUMNS, _IDENTITY_SCHEMA_CHECKSUM, _IDENTITY_SCHEMA_NAME, _INITIAL_SCHEMA_CHECKSUM, _INITIAL_SCHEMA_NAME, _PUBLIC_PROFILES_SCHEMA_CHECKSUM, _PUBLIC_PROFILES_SCHEMA_NAME, _TEAMS_SCHEMA_CHECKSUM, _TEAMS_SCHEMA_NAME, _TENON_SCHEMA_CHECKSUM, _TENON_SCHEMA_NAME


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
        3: {
            "name": _TENON_SCHEMA_NAME,
            "checksum": _TENON_SCHEMA_CHECKSUM,
            "backward_compatible": 1,
        },
        4: {"name": _HISTORY_SCHEMA_NAME, "checksum": _HISTORY_SCHEMA_CHECKSUM,
            "backward_compatible": 1},
        5: {"name": _DELETION_SCHEMA_NAME, "checksum": _DELETION_SCHEMA_CHECKSUM,
            "backward_compatible": 1},
        6: {"name": _IDENTITY_SCHEMA_NAME, "checksum": _IDENTITY_SCHEMA_CHECKSUM,
            "backward_compatible": 1},
        7: {"name": _TEAMS_SCHEMA_NAME, "checksum": _TEAMS_SCHEMA_CHECKSUM,
            "backward_compatible": 1},
        8: {"name": _HOSTED_SCHEMA_NAME, "checksum": _HOSTED_SCHEMA_CHECKSUM,
            "backward_compatible": 1},
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
        _validate_schema(conn, {**_EXPECTED_SCHEMA_COLUMNS_V1, **_EXPECTED_SCHEMA_COLUMNS_V2})
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

    if 3 not in applied_versions:
        _create_tenon_schema(conn)
        _validate_schema(conn, _EXPECTED_SCHEMA_COLUMNS_V3)
        conn.execute(
            """INSERT INTO schema_migrations
                (version, name, checksum, backward_compatible, applied_at)
                VALUES (?, ?, ?, ?, ?)""",
            (3, _TENON_SCHEMA_NAME, _TENON_SCHEMA_CHECKSUM, 1,
             datetime.now(timezone.utc).isoformat()),
        )

    if 4 not in applied_versions:
        conn.execute("""CREATE TABLE IF NOT EXISTS semantic_heads (
            project_id TEXT PRIMARY KEY REFERENCES projects(id), revision TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS semantic_versions (
            project_id TEXT NOT NULL REFERENCES projects(id),
            revision TEXT NOT NULL, parent TEXT, snapshot_json TEXT NOT NULL,
            created_at TEXT NOT NULL, PRIMARY KEY (project_id, revision))""")
        conn.execute("""INSERT INTO schema_migrations
            (version, name, checksum, backward_compatible, applied_at)
            VALUES (?, ?, ?, ?, ?)""",
            (4, _HISTORY_SCHEMA_NAME, _HISTORY_SCHEMA_CHECKSUM, 1,
             datetime.now(timezone.utc).isoformat()))

    if 5 not in applied_versions:
        conn.execute("""CREATE TABLE IF NOT EXISTS product_deletion_receipts (
            operation_id TEXT PRIMARY KEY NOT NULL, issuer TEXT NOT NULL,
            subject TEXT NOT NULL, completed_at TEXT NOT NULL)""")
        conn.execute("CREATE INDEX IF NOT EXISTS product_deletion_subject_idx ON product_deletion_receipts(issuer, subject, completed_at)")
        if "started_at" not in _observed_schema_columns(conn)["tenon_login_attempts"]:
            conn.execute("ALTER TABLE tenon_login_attempts ADD COLUMN started_at TEXT")
        conn.execute("""INSERT INTO schema_migrations
            (version, name, checksum, backward_compatible, applied_at)
            VALUES (?, ?, ?, ?, ?)""",
            (5, _DELETION_SCHEMA_NAME, _DELETION_SCHEMA_CHECKSUM, 1,
             datetime.now(timezone.utc).isoformat()))

    if 6 not in applied_versions:
        # Additive, so the previous image keeps working after a rollback. The
        # cascade keeps its project deletion working too: these rows are derived.
        observed = _observed_schema_columns(conn)
        for table, columns in _IDENTITY_COLUMNS.items():
            for column in sorted(columns - observed[table]):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
        conn.execute("""CREATE TABLE IF NOT EXISTS verified_objects (
            project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            object_id TEXT NOT NULL, revision TEXT NOT NULL,
            PRIMARY KEY (project_id, object_id))""")
        conn.execute("""INSERT INTO schema_migrations
            (version, name, checksum, backward_compatible, applied_at)
            VALUES (?, ?, ?, ?, ?)""",
            (6, _IDENTITY_SCHEMA_NAME, _IDENTITY_SCHEMA_CHECKSUM, 1,
             datetime.now(timezone.utc).isoformat()))

    if 7 not in applied_versions:
        # Additive again. After a rollback the previous image ignores these
        # columns, so team projects and public pages simply stop being reachable.
        conn.execute("""CREATE TABLE IF NOT EXISTS teams (
            id TEXT PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
            created_by TEXT REFERENCES accounts(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS team_members (
            team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK (role IN ('admin', 'member', 'viewer')),
            joined_at TEXT NOT NULL, PRIMARY KEY (team_id, account_id))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS team_invites (
            id TEXT PRIMARY KEY,
            team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL CHECK (role IN ('admin', 'member', 'viewer')),
            created_by TEXT REFERENCES accounts(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL, expires_at TEXT NOT NULL)""")
        observed = _observed_schema_columns(conn)["projects"]
        if "team_id" not in observed:
            conn.execute("ALTER TABLE projects ADD COLUMN team_id TEXT REFERENCES teams(id)")
        if "visibility" not in observed:
            conn.execute("ALTER TABLE projects ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private'")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_team_name ON projects(team_id, provider, repo_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_team_members_account ON team_members(account_id)")
        conn.execute("""INSERT INTO schema_migrations
            (version, name, checksum, backward_compatible, applied_at)
            VALUES (?, ?, ?, ?, ?)""",
            (7, _TEAMS_SCHEMA_NAME, _TEAMS_SCHEMA_CHECKSUM, 1,
             datetime.now(timezone.utc).isoformat()))

    if 8 not in applied_versions:
        # Additive: after a rollback the table sits unused and the CLI asks for a pasted token,
        # stored_bytes falls behind until the next migration, and suspensions stop applying.
        conn.execute("""CREATE TABLE IF NOT EXISTS device_logins (
            id TEXT PRIMARY KEY, device_hash TEXT NOT NULL UNIQUE, user_hash TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
            account_id TEXT REFERENCES accounts(id) ON DELETE CASCADE, decided_at TEXT)""")
        observed = _observed_schema_columns(conn)
        if "stored_bytes" not in observed["projects"]:
            conn.execute("ALTER TABLE projects ADD COLUMN stored_bytes BIGINT NOT NULL DEFAULT 0")
        if "suspended_at" not in observed["projects"]:
            conn.execute("ALTER TABLE projects ADD COLUMN suspended_at TEXT")
        if "suspended_at" not in observed["accounts"]:
            conn.execute("ALTER TABLE accounts ADD COLUMN suspended_at TEXT")
        size = "OCTET_LENGTH(v.snapshot_json)" if conn.backend == "postgresql" else "LENGTH(CAST(v.snapshot_json AS BLOB))"
        conn.execute(f"""UPDATE projects SET stored_bytes = COALESCE(
            (SELECT SUM({size}) FROM semantic_versions v WHERE v.project_id = projects.id), 0)""")
        conn.execute("""INSERT INTO schema_migrations
            (version, name, checksum, backward_compatible, applied_at)
            VALUES (?, ?, ?, ?, ?)""",
            (8, _HOSTED_SCHEMA_NAME, _HOSTED_SCHEMA_CHECKSUM, 1,
             datetime.now(timezone.utc).isoformat()))

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
