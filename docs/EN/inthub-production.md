# IntHub Production Deployment

[中文](../CN/inthub-production.md) | [English](inthub-production.md)

The production profile is a private semantic-history viewer. Its current identity boundary is one deployment with one shared access token. The browser exchanges that token for a 12-hour HttpOnly, SameSite=Strict cookie which can only read the API. Mutations such as `itt hub link` and `itt hub sync` always require a Bearer token.

## Database choice

Production uses PostgreSQL while local `itt hub start` keeps SQLite. Current single-user traffic does not require PostgreSQL; it is selected for concurrent writes, backup and recovery, connection handling, and a cleaner future migration to accounts. Both backends use the same query layer and an explicit `sequence_id`, and CI exercises both.

PostgreSQL is not a tenant model by itself. Multi-account support still requires account ownership, account-scoped uniqueness and queries, login sessions, authorization policy, quotas, and a data migration. The current shared token must not be described as multi-user authorization.

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

Create production configuration from [inthub.env.example](../../deploy/inthub/inthub.env.example). Give the actual access token only to the CLI/browser; configure its SHA-256 digest on the server. Generate the token and PostgreSQL password with a cryptographically secure source and keep them out of Git, shell history, chat, and logs.

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

`/health` and `/healthz` report liveness only. `/readyz` also checks PostgreSQL. None returns a database address, version, credential, or project data. An unauthenticated `/api/v1/projects` request must return `401`; an authenticated request uses `Authorization: Bearer <token>`.

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
