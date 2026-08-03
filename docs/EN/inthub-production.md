# IntHub Production Deployment

[中文](../CN/inthub-production.md) | [English](inthub-production.md)

IntHub production has one account path: a user's first GitHub authorization creates an IntHub account, later browser access uses a database-backed Web session, and the CLI uses an access token issued by that account. Projects, workspace views, and sync history are account-scoped. There is no deployment-wide access token.

The GitHub App and IntHub accounts are separate boundaries:

- The GitHub App is OAuth infrastructure owned and configured once by the platform operator.
- Owning the GitHub App does not make that identity the only IntHub user.
- Regular GitHub users neither create nor own the App; their first sign-in creates their own IntHub account.

## Data and authentication model

- Browser: GitHub OAuth with PKCE and one-time state. The GitHub access token is used only for the identity request and is never persisted.
- Web session: random HttpOnly, SameSite=Strict cookie; only its hash is stored.
- CLI: an account issues an `ith_pat_...` token. Only its hash, label, expiry, last-used time, and revocation state are stored.
- Writes: `itt hub link`, `itt push`, and its `itt hub sync` compatibility alias accept only account tokens. Browser sessions remain read-only except for managing the current account's tokens.
- Data: every production project has an `account_id`; lists, details, search, and sync writes apply the same account boundary. Different IntHub accounts may link their own copy of the same GitHub repository.

Production uses PostgreSQL. Local `itt hub start` remains an unauthenticated SQLite process bound only to loopback. PostgreSQL supplies a durable boundary for concurrent writes, backup and recovery, and future team collaboration, but it does not replace application authorization.

## Topology

```text
Internet
  → Caddy :443
  → 127.0.0.1:7250
  → inthub-app :8000
  → inthub-postgres :5432 (Docker-internal only)
```

- Use the independent Compose project `inthub`, its own network, and its own data volume.
- Publish only Caddy on 80/443. Bind the app to loopback and do not publish PostgreSQL.
- Keep `/opt/inthub/shared/inthub.env` at mode `0600`.
- Store releases at `/opt/inthub/releases/<git-sha>` and point `/opt/inthub/current` at the active release.
- Never reuse another service's containers, database, credentials, directories, or Caddy site file.

## First deployment and GitHub App configuration

Manually register one public GitHub App in GitHub Developer settings. This is a platform deployment action performed once:

- Homepage URL: `https://inthub.example.com`
- User authorization callback URL: `https://inthub.example.com/api/v1/auth/github/callback`
- Webhook: disabled
- Repository permissions: none
- Organization / account permissions: none
- `Where can this GitHub App be installed?`: `Any account` (public); this does not grant the App access to users' repositories

After generating a Client Secret, write the Client ID and Client Secret directly to `/opt/inthub/shared/inthub.env` on the server and keep the file at mode `0600`. Do not send the secret through chat, commit it, or print it in logs:

```text
INTHUB_GITHUB_CLIENT_ID=<GitHub App Client ID>
INTHUB_GITHUB_CLIENT_SECRET=<GitHub App Client Secret>
```

Complete the remaining configuration from [inthub.env.example](../../deploy/inthub/inthub.env.example). Use a URL-safe random PostgreSQL password.

Start the release:

```bash
sudo docker compose \
  --project-name inthub \
  --env-file /opt/inthub/shared/inthub.env \
  --file /opt/inthub/current/deploy/inthub/compose.yaml \
  up --detach --build --remove-orphans
```

After startup, the homepage exposes only normal `Continue with GitHub`. Any GitHub user's first authorization creates an ordinary `member` account; owning the GitHub App grants no additional data access.

## Account token and sync

After signing in, select `CLI token` in the account area. IntHub creates a 90-day account token and shows it once:

```bash
itt auth login --api-base-url https://inthub.example.com
cd your-project
itt hub link
itt push --dry-run
itt push
```

`itt auth login` prompts without echo when `--token` and `INTHUB_TOKEN` are absent. It saves only the endpoint in the user config and delegates the token to Git's configured credential helper. Use a secure OS-backed helper; Git's `store` helper is plaintext. `--token` can still supply a token to one CLI command. The CLI never persists a token to `.intent/hub.json`. HTTP sends it as `Authorization: Bearer <token>`; Bearer is the transport scheme, while the authorization principal remains the specific IntHub account. `itt auth logout` removes the local credential but does not revoke it on the server; revoke it in the Web UI when compromise or permanent removal is intended.

## Verification

```bash
curl --fail --silent --show-error https://inthub.example.com/healthz
curl --fail --silent --show-error https://inthub.example.com/readyz

# Unauthenticated reads must return 401.
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  https://inthub.example.com/api/v1/projects

# An account token returns only that account's projects.
curl --fail --silent --show-error \
  -H "Authorization: Bearer $INTHUB_TOKEN" \
  https://inthub.example.com/api/v1/projects
```

`/health` and `/healthz` report liveness only; `/readyz` also checks PostgreSQL. None returns a database address, version, credential, or project data. After OAuth, `GET /api/v1/auth/me` returns the current account. After logout, the old cookie must receive `401`.

Install only `/etc/caddy/sites-enabled/inthub.caddy`, validate from the shared root configuration, and then reload:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl reload caddy
```

## Backup, release, and rollback

Before every release, preserve both:

- a self-contained PostgreSQL `pg_dump --format=custom`;
- `/opt/inthub/shared/inthub.env` at mode `0600`.

The account model is the only supported data model. There is no compatibility migration from the preview deployment-wide-token database. Back up such a deployment, create the current empty schema, let users register through GitHub, and resync with their account tokens.

Application rollback does not roll back data. Point `/opt/inthub/current` to a retained release, update the release variables, and rerun `compose up`. A release with an incompatible schema change requires its matching database restore; switching code alone is insufficient.

Use bounded diagnostics:

```bash
sudo docker compose --project-name inthub \
  --env-file /opt/inthub/shared/inthub.env \
  --file /opt/inthub/current/deploy/inthub/compose.yaml ps
sudo docker logs --tail 200 inthub-app
sudo docker logs --tail 200 inthub-postgres
```

Logs and diagnostics must never contain account tokens, the GitHub Client Secret, or the PostgreSQL password.
