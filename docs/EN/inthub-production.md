# IntHub Production Deployment

[中文](../CN/inthub-production.md) | [English](inthub-production.md)

The production profile is a private semantic-history viewer. The browser signs in through GitHub OAuth, IntHub creates a revocable account session in PostgreSQL, and an HttpOnly, SameSite=Strict cookie reads the API. The GitHub access token is used only for that identity check and is never persisted. Mutations such as `itt hub link` and `itt hub sync` continue to use a separate deployment-level Bearer token.

This is the single-owner phase of the account system, not full multi-tenancy. Production should allow one stable numeric GitHub user ID, and every project remains in the deployment's shared data domain. The database now has accounts, OAuth login attempts, and Web sessions; project ownership, account PATs, and account-scoped queries remain future work.

## Database choice

Production uses PostgreSQL while local `itt hub start` keeps SQLite. Current single-user traffic does not require PostgreSQL; it is selected for concurrent writes, backup and recovery, connection handling, and a cleaner future migration to accounts. Both backends use the same query layer and an explicit `sequence_id`, and CI exercises both.

PostgreSQL is not a tenant model by itself. Multi-account support still requires project ownership, account-scoped uniqueness and queries, account access tokens, authorization policy, quotas, and a data migration. The current GitHub allowlist establishes browser identity only and must not be described as project-level authorization.

## Topology

```text
Internet
  → Caddy :443
  → 127.0.0.1:7250
  → inthub-app :8000
  → inthub-postgres :5432 (Docker-internal only)
```

- Use the independent Compose project `inthub`, its own network, and its own data volume.
- Publish only Caddy on host ports 80/443. Bind the app to loopback and do not publish PostgreSQL.
- Keep production configuration at `/opt/inthub/shared/inthub.env` with mode `0600`.
- Keep releases at `/opt/inthub/releases/<git-sha>` and point `/opt/inthub/current` at the active release.
- Never reuse another service's containers, database, credentials, directories, or Caddy site file.

## Configuration and release

Create production configuration from [inthub.env.example](../../deploy/inthub/inthub.env.example). Give the deployment access token only to the CLI and configure its SHA-256 digest on the server. Generate the token and PostgreSQL password with a cryptographically secure source and keep them out of Git, shell history, chat, and logs.

Register a private GitHub App with `https://inthub.example.com` as its Homepage URL and `https://inthub.example.com/api/v1/auth/github/callback` as its user authorization callback URL. Disable webhooks and grant no repository or account permissions; IntHub reads only the public account identity needed to sign in. Put the Client ID, Client Secret, and the allowed account's numeric GitHub user ID in the mode-`0600` production env file; do not rely on a renameable login as the long-term authorization boundary.

The authorization flow uses one-time state and PKCE. After sign-in, only the hash of IntHub's own random session is stored. Sessions last seven days by default and are deleted from the database on logout.

Start or upgrade the release with:

```bash
sudo docker compose \
  --project-name inthub \
  --env-file /opt/inthub/shared/inthub.env \
  --file /opt/inthub/current/deploy/inthub/compose.yaml \
  up --detach --build --remove-orphans
```

Install only `/etc/caddy/sites-enabled/inthub.caddy`, then validate the shared root configuration before reload:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl reload caddy
```

Never replace `/etc/caddy/Caddyfile` or another service's site file.

## Verification and sync

`/health` and `/healthz` report liveness only. `/readyz` also checks PostgreSQL. None returns a database address, version, credential, or project data. An unauthenticated `/api/v1/projects` request must return `401`; an authenticated CLI request uses `Authorization: Bearer <token>`. The browser must show `Continue with GitHub`, and the GitHub login endpoint must redirect to `github.com`.

```bash
export INTHUB_TOKEN='<access token>'
itt hub link --api-base-url https://inthub.example.com
itt hub sync --dry-run
itt hub sync
```

The CLI does not persist the token in `.intent/hub.json`.

## Backup and rollback

Use `pg_dump --format=custom` from the `database` service and store backups outside the Docker volume under `/opt/inthub/backups`. Before restore, stop the app, preserve the current database, and use a maintenance window; never overwrite the database without inspecting the restore target.

An application rollback does not roll back data. Point `/opt/inthub/current` to a retained release, update `INTHUB_RELEASE` and `INTHUB_PACKAGE_VERSION`, and rerun the same Compose command. A release with a backward-incompatible data migration needs its matching database recovery procedure.

Use `docker compose ... ps` and bounded `docker logs --tail 200` for diagnostics. Logs and diagnostic output must never include the access token or PostgreSQL password.
