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

    assert "account_id" in project_columns
    assert token_table is not None
    assert "sequence_id" in sync_columns


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
