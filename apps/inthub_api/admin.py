"""Operator commands for a hosted hub, run inside the app container:

    docker exec inthub-app-green python -m apps.inthub_api.admin find someone@example.com

Suspending an account ends its sessions and refuses its tokens and sign-ins, and takes
down its public personal projects. A takedown makes a project private and keeps it
that way; its members can still read and export it.
"""

import argparse
import json
import os

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


COMMANDS = {"find": find, "suspend": suspend, "restore": restore, "takedown": takedown, "reinstate": reinstate}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m apps.inthub_api.admin")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("target", help="an account or project ID; find also takes an email")
    parser.add_argument("--database-url", default=os.environ.get("INTHUB_DATABASE_URL"))
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("INTHUB_DATABASE_URL or --database-url is required")
    print(json.dumps(COMMANDS[args.command](args.database_url, args.target), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
