import sqlite3

import pytest

from apps.inthub_api import db
from apps.inthub_api.db import connect


def test_current_sqlite_schema_has_account_scoped_projects_and_tokens(tmp_path):
    db_path = str(tmp_path / "inthub.db")
    with connect(db_path) as conn:
        project_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(projects)").fetchall()
        }
        token_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("account_access_tokens",),
        ).fetchone()
        sync_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(sync_batches)").fetchall()
        }
        profile_columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(public_profiles)").fetchall()
        }
        grant_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(public_profile_projects)").fetchall()
        }

    assert "account_id" in project_columns
    assert token_table is not None
    assert "sequence_id" in sync_columns
    assert {"slug", "account_id", "title"}.issubset(profile_columns)
    assert {"profile_slug", "project_id", "position"}.issubset(grant_columns)


def test_schema_v1_upgrades_to_public_profile_schema_v2(tmp_path):
    db_path = str(tmp_path / "legacy-v1.db")
    raw = sqlite3.connect(db_path)
    raw.row_factory = sqlite3.Row
    conn = db.DatabaseConnection(raw, "sqlite")
    db._ensure_migration_ledger(conn)
    db._create_sqlite_schema(conn)
    conn.execute(
        """
        INSERT INTO schema_migrations
            (version, name, checksum, backward_compatible, applied_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            1,
            db._INITIAL_SCHEMA_NAME,
            db._INITIAL_SCHEMA_CHECKSUM,
            1,
            "2026-08-01T00:00:00+00:00",
        ),
    )
    conn.commit()
    conn.close()

    migrated = db.migrate_target(db_path, require_backward_compatible=True)
    assert migrated == {
        "from_version": 1,
        "to_version": 2,
        "latest_known_version": 2,
        "backward_compatible_only": True,
    }
    with sqlite3.connect(db_path) as check:
        versions = [row[0] for row in check.execute("SELECT version FROM schema_migrations")]
        profile_table = check.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'public_profiles'"
        ).fetchone()
    assert versions == [1, 2]
    assert profile_table is not None


def test_production_connection_refuses_to_migrate_as_a_startup_side_effect(
    tmp_path, monkeypatch
):
    db_path = str(tmp_path / "production.db")
    monkeypatch.setenv("INTHUB_AUTO_MIGRATE", "0")
    db._INITIALIZED.clear()

    with pytest.raises(RuntimeError, match="migration is required"):
        connect(db_path)

    with sqlite3.connect(db_path) as raw:
        tables = raw.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    assert tables == []

    migrated = db.migrate_target(db_path, require_backward_compatible=True)
    assert migrated["to_version"] == db.LATEST_SCHEMA_VERSION
    db._INITIALIZED.clear()
    with connect(db_path) as conn:
        assert db.current_schema_version(conn) == db.LATEST_SCHEMA_VERSION
