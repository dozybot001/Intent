"""Private raw-snapshot export for IntHub pull clients."""

import json

from apps.inthub_api.common import APIError
from apps.inthub_api.db import connect


SUPPORTED_REPO_PROVIDERS = {"github", "gitee"}


def _validate_repo_identity(provider, repo_id):
    if provider not in SUPPORTED_REPO_PROVIDERS:
        raise APIError(
            "INVALID_INPUT",
            "provider must be 'github' or 'gitee'.",
            status=400,
        )
    parts = repo_id.split("/") if isinstance(repo_id, str) else []
    if len(parts) != 2 or any(not part or part in {".", ".."} for part in parts):
        raise APIError(
            "INVALID_INPUT",
            "repo_id must use the exact 'owner/name' form.",
            status=400,
        )


def _snapshot_rows(conn, provider, repo_id, account_id, workspace_id):
    account_clause = "p.account_id = ?" if account_id is not None else "p.account_id IS NULL"
    workspace_clause = "AND w.id = ?" if workspace_id is not None else ""
    params = [provider, repo_id]
    if account_id is not None:
        params.append(account_id)
    if workspace_id is not None:
        params.append(workspace_id)

    return conn.execute(
        f"""
        SELECT
            p.id AS project_id,
            p.provider,
            p.repo_id,
            p.owner,
            p.repo_name,
            w.id AS workspace_id,
            sb.id AS sync_batch_id,
            sb.sequence_id,
            sb.accepted_at,
            sb.generated_at,
            sb.payload_json
        FROM projects AS p
        JOIN workspaces AS w ON w.project_id = p.id
        JOIN sync_batches AS sb
          ON sb.project_id = p.id
         AND sb.workspace_id = w.id
        WHERE p.provider = ?
          AND p.repo_id = ?
          AND {account_clause}
          {workspace_clause}
          AND sb.sequence_id = (
              SELECT MAX(latest.sequence_id)
              FROM sync_batches AS latest
              WHERE latest.project_id = p.id
                AND latest.workspace_id = w.id
          )
        ORDER BY sb.sequence_id DESC
        """,
        tuple(params),
    ).fetchall()


def export_snapshot(
    db_path,
    provider,
    repo_id,
    *,
    account_id=None,
    workspace_id=None,
):
    """Export one account-owned workspace's latest complete raw snapshot."""
    _validate_repo_identity(provider, repo_id)
    if workspace_id is not None and (
        not isinstance(workspace_id, str) or not workspace_id
    ):
        raise APIError(
            "INVALID_INPUT",
            "workspace_id must be a non-empty string when provided.",
            status=400,
        )

    with connect(db_path) as conn:
        rows = _snapshot_rows(
            conn,
            provider,
            repo_id,
            account_id,
            workspace_id,
        )

    if not rows:
        raise APIError(
            "SNAPSHOT_NOT_FOUND",
            "No synced snapshot matches this account, repository, and workspace.",
            status=404,
        )
    if workspace_id is None and len(rows) > 1:
        raise APIError(
            "WORKSPACE_REQUIRED",
            "Multiple synced workspaces match this repository; select one explicitly.",
            status=409,
            details={
                "candidates": [
                    {
                        "source_workspace_id": row["workspace_id"],
                        "last_accepted_at": row["accepted_at"],
                    }
                    for row in rows
                ],
            },
        )

    row = rows[0]
    payload = row["payload_json"]
    if isinstance(payload, str):
        payload = json.loads(payload)

    return {
        "format_version": 1,
        "project_id": row["project_id"],
        "repo_binding": {
            "provider": row["provider"],
            "repo_id": row["repo_id"],
            "owner": row["owner"],
            "name": row["repo_name"],
        },
        "source_workspace_id": row["workspace_id"],
        "batch": {
            "sync_batch_id": row["sync_batch_id"],
            "sequence_id": row["sequence_id"],
            "accepted_at": row["accepted_at"],
            "generated_at": row["generated_at"],
        },
        "snapshot": payload["snapshot"],
    }
