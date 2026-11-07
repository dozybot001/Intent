"""Operator commands for a hosted hub, run inside the app container:

    docker exec inthub-app-green python -m apps.inthub_api.admin find someone@example.com

Suspending an account ends its sessions and refuses its tokens and sign-ins, and takes
down its public personal projects. A takedown makes a project private and keeps it
that way; its members can still read and export it.

retire-tokens revokes every CLI token issued before a time, for the day tenon.asia
becomes a redirect (S2): a token an old CLI still sends there could be replayed here.
Run it with --dry-run first. Web sessions need no step: they last 30 days at most.
"""

import argparse
import json
import os
from datetime import datetime, timezone

from apps.inthub_api.common import now_utc
from apps.inthub_api.db import connect


def find(target, query):
    with connect(target) as conn:
        accounts = conn.execute(
            "SELECT id, login, display_name, email, created_at, last_login_at, suspended_at FROM accounts WHERE id = ? OR email = ? OR login = ?",
            (query, query, query),
        ).fetchall()
        result = []
        for account in accounts:
            projects = conn.execute(
                "SELECT id, repo_id, team_id, visibility, stored_bytes, suspended_at FROM projects WHERE account_id = ?",
                (account["id"],),
            ).fetchall()
            result.append({**dict(account), "projects": [dict(project) for project in projects]})
        projects = conn.execute(
            "SELECT id, repo_id, account_id, team_id, visibility, stored_bytes, suspended_at FROM projects WHERE id = ?",
            (query,),
        ).fetchall()
    return {"accounts": result, "projects": [dict(project) for project in projects]}


def suspend(target, account_id):
    timestamp = now_utc()
    with connect(target) as conn:
        if conn.execute("UPDATE accounts SET suspended_at = ? WHERE id = ?", (timestamp, account_id)).rowcount != 1:
            raise SystemExit(f"No account {account_id}.")
        conn.execute("DELETE FROM web_sessions WHERE account_id = ?", (account_id,))
        taken = conn.execute(
            "UPDATE projects SET visibility = 'private', suspended_at = ? WHERE account_id = ? AND team_id IS NULL AND visibility = 'public'",
            (timestamp, account_id),
        ).rowcount
    return {"suspended": account_id, "projects_taken_down": taken}


def restore(target, account_id):
    with connect(target) as conn:
        if conn.execute("UPDATE accounts SET suspended_at = NULL WHERE id = ?", (account_id,)).rowcount != 1:
            raise SystemExit(f"No account {account_id}.")
    return {"restored": account_id}


def takedown(target, project_id):
    with connect(target) as conn:
        changed = conn.execute(
            "UPDATE projects SET visibility = 'private', suspended_at = ? WHERE id = ?", (now_utc(), project_id),
        ).rowcount
    if changed != 1:
        raise SystemExit(f"No project {project_id}.")
    return {"taken_down": project_id}


def reinstate(target, project_id):
    with connect(target) as conn:
        changed = conn.execute("UPDATE projects SET suspended_at = NULL WHERE id = ?", (project_id,)).rowcount
    if changed != 1:
        raise SystemExit(f"No project {project_id}.")
    return {"reinstated": project_id, "visibility": "private"}


def retire_tokens(target, before, dry_run=False):
    try:
        cutoff = datetime.fromisoformat(before)
    except ValueError:
        raise SystemExit("retire-tokens takes an ISO time, such as 2027-01-15T00:00:00+08:00.") from None
    if cutoff.tzinfo is None:
        raise SystemExit("Give the time with its UTC offset.")
    cutoff = cutoff.astimezone(timezone.utc).isoformat()
    with connect(target) as conn:
        live = "FROM account_access_tokens WHERE revoked_at IS NULL AND created_at < ? AND expires_at > ?"
        if dry_run:
            count = conn.execute(f"SELECT count(*) AS n {live}", (cutoff, now_utc())).fetchone()["n"]
            return {"would_retire": count, "issued_before": cutoff}
        count = conn.execute(f"UPDATE account_access_tokens SET revoked_at = ? WHERE id IN (SELECT id {live})",
                             (now_utc(), cutoff, now_utc())).rowcount
    return {"retired": count, "issued_before": cutoff}


COMMANDS = {"find": find, "suspend": suspend, "restore": restore, "takedown": takedown, "reinstate": reinstate,
            "retire-tokens": retire_tokens}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m apps.inthub_api.admin")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("target", help="an account or project ID; find also takes an email; retire-tokens takes a time")
    parser.add_argument("--database-url", default=os.environ.get("INTHUB_DATABASE_URL"))
    parser.add_argument("--dry-run", action="store_true", help="retire-tokens: count, revoke nothing")
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("INTHUB_DATABASE_URL or --database-url is required")
    options = {"dry_run": True} if args.dry_run and args.command == "retire-tokens" else {}
    if args.dry_run and not options:
        parser.error("--dry-run only applies to retire-tokens")
    print(json.dumps(COMMANDS[args.command](args.database_url, args.target, **options), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
