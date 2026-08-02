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
