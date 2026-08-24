"""Explicitly publish account-owned IntHub projects as read-only profiles.

This module is an operator-only control surface. It never runs during normal
application startup and it does not make future projects public implicitly.
"""

import argparse
import json
import os
import re
from datetime import datetime, timezone

from apps.inthub_api.db import connect


_SLUG_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")


class PublicProfileConfigurationError(RuntimeError):
    """Raised when an operator request would violate publication boundaries."""


def _now_utc():
    return datetime.now(timezone.utc).isoformat()


def validate_public_profile_slug(slug):
    value = str(slug or "").strip().lower()
    if _SLUG_PATTERN.fullmatch(value) is None:
        raise PublicProfileConfigurationError(
            "profile slug must use 1-63 lowercase letters, numbers, or hyphens"
        )
    return value


def _validate_text(value, *, field, limit, required=False):
    normalized = str(value or "").strip()
    if required and not normalized:
        raise PublicProfileConfigurationError(f"{field} is required")
    if len(normalized) > limit:
        raise PublicProfileConfigurationError(
            f"{field} must be at most {limit} characters"
        )
    return normalized


def _account_row(conn, provider, provider_user_id):
    row = conn.execute(
        """
        SELECT id, provider, provider_user_id, login, display_name, avatar_url
        FROM accounts
        WHERE provider = ? AND provider_user_id = ?
        """,
        (provider, str(provider_user_id)),
    ).fetchone()
    if row is None:
        raise PublicProfileConfigurationError(
            "the requested identity does not have an IntHub account"
        )
    return row


def _current_project_ids(conn, account_id):
    rows = conn.execute(
        """
        SELECT p.id
        FROM projects AS p
        LEFT JOIN sync_batches AS sb ON sb.project_id = p.id
        WHERE p.account_id = ?
        GROUP BY p.id
        ORDER BY COALESCE(MAX(sb.accepted_at), p.created_at) DESC, p.created_at DESC
        """,
        (account_id,),
    ).fetchall()
    return [row["id"] for row in rows]


def configure_public_profile(
    db_target,
    *,
    slug,
    provider,
    provider_user_id,
    title=None,
    description="",
    project_ids=None,
    include_all_current_projects=False,
):
    """Create or update one profile and replace its explicit project grants."""
    slug = validate_public_profile_slug(slug)
    provider = _validate_text(provider, field="provider", limit=32, required=True)
    description = _validate_text(description, field="description", limit=500)
    requested_project_ids = list(dict.fromkeys(project_ids or ()))

    with connect(db_target) as conn:
        account = _account_row(conn, provider, provider_user_id)
        account_id = account["id"]
        existing_slug = conn.execute(
            "SELECT account_id FROM public_profiles WHERE slug = ?",
            (slug,),
        ).fetchone()
        if existing_slug is not None and existing_slug["account_id"] != account_id:
            raise PublicProfileConfigurationError(
                "profile slug is already owned by another account"
            )
        existing_account = conn.execute(
            "SELECT slug FROM public_profiles WHERE account_id = ?",
            (account_id,),
        ).fetchone()
        if existing_account is not None and existing_account["slug"] != slug:
            raise PublicProfileConfigurationError(
                "account already owns a different public profile slug"
            )

        if include_all_current_projects:
            requested_project_ids = _current_project_ids(conn, account_id)
        if not requested_project_ids:
            raise PublicProfileConfigurationError(
                "at least one explicit project grant is required"
            )

        placeholders = ", ".join("?" for _ in requested_project_ids)
        rows = conn.execute(
            f"""
            SELECT id
            FROM projects
            WHERE account_id = ? AND id IN ({placeholders})
            """,
            (account_id, *requested_project_ids),
        ).fetchall()
        owned_project_ids = {row["id"] for row in rows}
        missing = [project_id for project_id in requested_project_ids if project_id not in owned_project_ids]
        if missing:
            raise PublicProfileConfigurationError(
                "projects are missing or not owned by this account: " + ", ".join(missing)
            )

        profile_title = _validate_text(
            title or account["display_name"] or f"@{account['login']}",
            field="title",
            limit=120,
            required=True,
        )
        timestamp = _now_utc()
        conn.execute(
            """
            INSERT INTO public_profiles
                (slug, account_id, title, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (slug) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                updated_at = excluded.updated_at
            """,
            (slug, account_id, profile_title, description, timestamp, timestamp),
        )
        conn.execute(
            "DELETE FROM public_profile_projects WHERE profile_slug = ?",
            (slug,),
        )
        for position, project_id in enumerate(requested_project_ids):
            conn.execute(
                """
                INSERT INTO public_profile_projects
                    (profile_slug, project_id, position, published_at)
                VALUES (?, ?, ?, ?)
                """,
                (slug, project_id, position, timestamp),
            )

    return {
        "slug": slug,
        "provider": provider,
        "provider_user_id": str(provider_user_id),
        "login": account["login"],
        "title": profile_title,
        "description": description,
        "project_ids": requested_project_ids,
        "project_count": len(requested_project_ids),
        "updated_at": timestamp,
    }


def remove_public_profile(db_target, *, slug):
    slug = validate_public_profile_slug(slug)
    with connect(db_target) as conn:
        cursor = conn.execute("DELETE FROM public_profiles WHERE slug = ?", (slug,))
        removed = cursor.rowcount > 0
    return {"slug": slug, "removed": removed}


def _parser():
    parser = argparse.ArgumentParser(description="Manage explicit IntHub public profiles.")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("INTHUB_DATABASE_URL"),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    publish = commands.add_parser("publish")
    publish.add_argument("--slug", required=True)
    publish.add_argument("--provider", default="github")
    publish.add_argument("--provider-user-id", required=True)
    publish.add_argument("--title")
    publish.add_argument("--description", default="")
    publish.add_argument("--project-id", action="append", default=[])
    publish.add_argument("--all-current-projects", action="store_true")

    unpublish = commands.add_parser("unpublish")
    unpublish.add_argument("--slug", required=True)
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    if not args.database_url:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "DATABASE_URL_REQUIRED",
                        "message": "INTHUB_DATABASE_URL or --database-url is required",
                    },
                }
            )
        )
        return 2
    try:
        if args.command == "publish":
            result = configure_public_profile(
                args.database_url,
                slug=args.slug,
                provider=args.provider,
                provider_user_id=args.provider_user_id,
                title=args.title,
                description=args.description,
                project_ids=args.project_id,
                include_all_current_projects=args.all_current_projects,
            )
        else:
            result = remove_public_profile(args.database_url, slug=args.slug)
    except PublicProfileConfigurationError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "code": "PUBLIC_PROFILE_CONFIGURATION_INVALID",
                        "message": str(exc),
                    },
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps({"ok": True, "result": result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
