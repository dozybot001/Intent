"""Write-path logic for the IntHub API."""

import json

from apps.inthub_api.common import APIError, new_id, now_utc, require_repo
from apps.inthub_api.db import connect


def link_project(db_path, project_name, repo, workspace_id):
    require_repo(repo)
    if repo.get("provider") != "github":
        raise APIError(
            "PROVIDER_UNSUPPORTED",
            f"Unsupported provider '{repo.get('provider')}'.",
            status=400,
        )

    with connect(db_path) as conn:
        project = conn.execute(
            "SELECT * FROM projects WHERE provider = ? AND repo_id = ?",
            (repo["provider"], repo["repo_id"]),
        ).fetchone()

        if project is None:
            project_id = new_id("proj")
            conn.execute(
                """
                INSERT INTO projects (id, name, provider, repo_id, owner, repo_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    project_name or repo["name"],
                    repo["provider"],
                    repo["repo_id"],
                    repo["owner"],
                    repo["name"],
                    now_utc(),
                ),
            )
        else:
            project_id = project["id"]

        if not workspace_id:
            workspace_id = new_id("wks")

        workspace = conn.execute(
            "SELECT * FROM workspaces WHERE id = ?",
            (workspace_id,),
        ).fetchone()
        if workspace is None:
            conn.execute(
                """
                INSERT INTO workspaces (id, project_id, provider, repo_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (workspace_id, project_id, repo["provider"], repo["repo_id"], now_utc()),
            )
        else:
            if workspace["project_id"] != project_id or workspace["repo_id"] != repo["repo_id"]:
                raise APIError(
                    "STATE_CONFLICT",
                    f"Workspace {workspace_id} is already linked to another project or repo.",
                    status=409,
                )

        conn.commit()
        return {
            "project_id": project_id,
            "workspace_id": workspace_id,
            "repo_binding": {
                "provider": repo["provider"],
                "repo_id": repo["repo_id"],
                "owner": repo["owner"],
                "name": repo["name"],
            },
        }


def store_sync_batch(db_path, payload):
    required = ("sync_batch_id", "project_id", "repo", "workspace", "snapshot")
    missing = [key for key in required if key not in payload]
    if missing:
        raise APIError(
            "INVALID_INPUT",
            f"Missing sync batch fields: {', '.join(missing)}.",
            status=400,
        )

    repo = payload["repo"]
    workspace = payload["workspace"]
    require_repo(repo)

    workspace_id = workspace.get("workspace_id")
    if not workspace_id:
        raise APIError("INVALID_INPUT", "Missing workspace.workspace_id.", status=400)

    with connect(db_path) as conn:
        existing = conn.execute(
            "SELECT accepted_at FROM sync_batches WHERE id = ?",
            (payload["sync_batch_id"],),
        ).fetchone()
        if existing is not None:
            return {
                "sync_batch_id": payload["sync_batch_id"],
                "project_id": payload["project_id"],
                "workspace_id": workspace_id,
                "accepted_at": existing["accepted_at"],
                "duplicate": True,
            }

        project = conn.execute(
            "SELECT * FROM projects WHERE id = ?",
            (payload["project_id"],),
        ).fetchone()
        if project is None:
            raise APIError(
                "OBJECT_NOT_FOUND",
                f"Project {payload['project_id']} not found.",
                status=404,
            )
        if project["provider"] != repo["provider"] or project["repo_id"] != repo["repo_id"]:
            raise APIError(
                "STATE_CONFLICT",
                "Sync batch repo does not match the linked project repo.",
                status=409,
            )

        workspace_row = conn.execute(
            "SELECT * FROM workspaces WHERE id = ? AND project_id = ?",
            (workspace_id, payload["project_id"]),
        ).fetchone()
        if workspace_row is None:
            raise APIError(
                "OBJECT_NOT_FOUND",
                f"Workspace {workspace_id} is not linked to project {payload['project_id']}.",
                status=404,
            )

        accepted_at = now_utc()
        conn.execute(
            """
            INSERT INTO sync_batches (id, project_id, workspace_id, generated_at, accepted_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payload["sync_batch_id"],
                payload["project_id"],
                workspace_id,
                payload.get("generated_at", accepted_at),
                accepted_at,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        conn.commit()
        return {
            "sync_batch_id": payload["sync_batch_id"],
            "project_id": payload["project_id"],
            "workspace_id": workspace_id,
            "accepted_at": accepted_at,
            "duplicate": False,
        }
