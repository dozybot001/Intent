import sqlite3

from apps.inthub_api.db import connect


def test_connect_migrates_v1_sync_batch_rowid_to_explicit_sequence(tmp_path):
    db_path = tmp_path / "inthub-v1.db"
    raw = sqlite3.connect(db_path)
    raw.executescript(
        """
        CREATE TABLE projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            provider TEXT NOT NULL,
            repo_id TEXT NOT NULL UNIQUE,
            owner TEXT NOT NULL,
            repo_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE workspaces (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            repo_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE sync_batches (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            workspace_id TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            accepted_at TEXT NOT NULL,
            payload_json TEXT NOT NULL
        );
        INSERT INTO projects VALUES (
            'proj_demo', 'Demo', 'github', 'example/demo',
            'example', 'demo', '2026-08-01T00:00:00+00:00'
        );
        INSERT INTO workspaces VALUES (
            'wks_demo', 'proj_demo', 'github', 'example/demo',
            '2026-08-01T00:00:00+00:00'
        );
        INSERT INTO sync_batches VALUES (
            'sync_first', 'proj_demo', 'wks_demo',
            '2026-08-01T00:00:00+00:00',
            '2026-08-01T00:00:01+00:00', '{}'
        );
        """
    )
    raw.commit()
    raw.close()

    with connect(str(db_path)) as conn:
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(sync_batches)").fetchall()
        }
        row = conn.execute(
            "SELECT sequence_id, id FROM sync_batches WHERE id = ?",
            ("sync_first",),
        ).fetchone()

    assert "sequence_id" in columns
    assert row["sequence_id"] == 1
    assert row["id"] == "sync_first"
