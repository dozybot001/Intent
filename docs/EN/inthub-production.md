# IntHub Official Production Deployment Standard

[中文](../CN/inthub-production.md) | [English](inthub-production.md)

## Metadata

- Status: reviewed
- Owner: project maintainers
- Last verified: 2026-08-04
- Runtime surface: deploy, ops, data, web, API
- Primary code anchors:
  - [deploy/inthub/compose.yaml](../../deploy/inthub/compose.yaml) - defines the isolated PostgreSQL service, app image, loopback binding, health checks, and container security boundary
  - [deploy/inthub/inthub.caddy](../../deploy/inthub/inthub.caddy) - defines the dedicated `inthub.tenon.asia` public ingress
  - [deploy/inthub/inthub.env.example](../../deploy/inthub/inthub.env.example) - lists production configuration keys without real secrets
  - [Dockerfile](../../Dockerfile) - defines the read-only IntHub application image built from a Git commit
- Primary tests:
  - [tests/test_inthub_postgres.py](../../tests/test_inthub_postgres.py) - protects PostgreSQL schema, account isolation, and concurrent writes
  - [tests/test_inthub_auth.py](../../tests/test_inthub_auth.py) - protects GitHub OAuth, Web sessions, and account access tokens
  - [tests/test_inthub_api_server.py](../../tests/test_inthub_api_server.py) - protects health, authentication, and HTTP API contracts
  - [tests/test_inthub_web_ui.py](../../tests/test_inthub_web_ui.py) - protects the sign-in path and Web static contracts
- Related docs:
  - [CLI guide](cli.md)
  - [IntHub UI/UX redesign plan](../CN/inthub-uiux-redesign.md)

## Short conclusion

Official IntHub production releases are pulled only from Gitee repository
[`https://gitee.com/dozybot/Intent.git`](https://gitee.com/dozybot/Intent), branch
`main`. Gitee `origin/main` is the deployment authority and production provenance.
GitHub repository [`dozybot001/Intent`](https://github.com/dozybot001/Intent) may
continue to receive code and run CI or Pages, but it is not a production source and
must never be an automatic fallback when Gitee is unavailable.

GitHub remains the OAuth identity provider. Identity provider and code deployment
provider are separate boundaries: keeping GitHub sign-in does not authorize a server
to pull release code from GitHub.

| Surface | Official value |
|---|---|
| Public URL | `https://inthub.tenon.asia` |
| Host | `ubuntu@122.51.14.35` |
| Local SSH alias | `agenthub-prod` (operator convenience only) |
| Production root | `/opt/inthub` |
| Loopback endpoint | `127.0.0.1:7250` |
| Compose project | `inthub` |
| App container | `inthub-app` |
| PostgreSQL container | `inthub-postgres` |
| PostgreSQL volume | `inthub-postgres-data` |
| Caddy site | `/etc/caddy/sites-enabled/inthub.caddy` |
| Deployment repository | `https://gitee.com/dozybot/Intent.git` |

## Mental model

```text
Developer clone
  ├─ origin/main  → Gitee dozybot/Intent       ← only production source
  └─ github/main  → GitHub dozybot001/Intent   ← optional collaboration, CI, Pages

Production release
  verified commit on Gitee main
    → /opt/inthub/releases/<git-sha>
    → Docker image inthub:<git-sha>
    → atomic /opt/inthub/current switch
    → Compose project inthub

Traffic
  Internet
    → Caddy :443
    → 127.0.0.1:7250
    → inthub-app :8000
    → inthub-postgres :5432 (Docker-private only)
```

Gitee proves which commit production deploys. The GitHub App confirms user identity
without repository permission. IntHub itself owns accounts, Web sessions, CLI tokens,
and account-scoped data in PostgreSQL. IntHub does not reuse AgentHub directories,
containers, databases, secrets, Gateway credentials, or deployment APIs.

## Source and remote policy

Every development clone uses this remote model:

```text
origin  https://gitee.com/dozybot/Intent.git
github  https://github.com/dozybot001/Intent.git
```

Invariants:

1. `origin/main` is the only production source of truth.
2. The release commit must exist on Gitee `main`; the server resolves and pulls it
   directly from Gitee.
3. GitHub pushes are allowed but optional. GitHub Actions can provide additional
   quality evidence, but cannot replace local checks or Gitee provenance.
4. Deployment code must not contain a GitHub archive, clone, raw URL, or a
   Gitee-to-GitHub fallback.
5. If Gitee is unavailable, stop the release and leave the healthy current release
   running.
6. Never create production releases from SCP, a dirty working tree, an ad-hoc archive,
   or an edit made directly on the server.

Standard delivery order:

```bash
git status --short
git push origin main

# Optional collaboration distribution; never a deployment prerequisite.
git push github main
```

Push release tags to Gitee first, then optionally to GitHub.

## Server layout and permissions

```text
/opt/inthub/
  current -> /opt/inthub/releases/<git-sha>
  releases/<git-sha>/
  shared/inthub.env          # 0600
  backups/<UTC timestamp>/
    inthub.dump              # PostgreSQL custom-format dump
    inthub.env               # 0600
```

Release directories are immutable and named with the full Git SHA. Switch `current`
with a temporary symlink and atomic rename on the same filesystem. Do not overwrite an
existing release directory. The app binds only to `127.0.0.1:7250`; PostgreSQL exposes
no host port. Caddy loads only IntHub's own site file.

## Configuration and account model

Production uses PostgreSQL. Local `itt hub start` remains an unauthenticated SQLite
process bound only to loopback. PostgreSQL supplies durable concurrency, backup, and
future collaboration boundaries; it does not replace application authorization.

Production has one account path:

- Browser: GitHub OAuth with PKCE and one-time state.
- Web session: random HttpOnly, SameSite=Strict cookie; only its hash is stored.
- CLI: account-issued `ith_pat_...` token; only its hash, name, expiry, last-used time,
  and revocation state are stored.
- Data: Project, Workspace, Intent, Snap, Decision, and sync history are scoped by
  `account_id`.

The public GitHub App is configured once:

- Homepage: `https://inthub.tenon.asia`
- Callback: `https://inthub.tenon.asia/api/v1/auth/github/callback`
- Webhook: disabled
- Repository permissions: none
- Organization/account permissions: none
- Installation scope: `Any account`

Real values live only in `/opt/inthub/shared/inthub.env`, mode `0600`. Never put a
secret in Git, chat, or diagnostic output. The configuration includes:

```text
INTHUB_DOMAIN=inthub.tenon.asia
INTHUB_BIND_PORT=7250
INTHUB_RELEASE=<full-gitee-git-sha>
INTHUB_PACKAGE_VERSION=<version-derived-from-the-clean-release>
INTHUB_GITHUB_CLIENT_ID=<configured-client-id>
INTHUB_GITHUB_CLIENT_SECRET=<configured-client-secret>
INTHUB_POSTGRES_PASSWORD=<url-safe-random-password>
```

See [inthub.env.example](../../deploy/inthub/inthub.env.example) for the full key set.

## Standard release flow

### 1. Local eligibility

```bash
git status --short
git branch --show-current
git rev-parse HEAD
pytest -q
git diff --check
git push origin main
git ls-remote origin refs/heads/main
```

The tree must be clean, the branch must be `main`, and tests must pass. Local `HEAD`
must equal Gitee `refs/heads/main`. A GitHub push does not alter eligibility.

### 2. Read-only production preflight

```bash
ssh agenthub-prod 'readlink -f /opt/inthub/current'
ssh agenthub-prod 'stat -c "%a %U:%G %n" /opt/inthub/shared/inthub.env'
ssh agenthub-prod 'sudo docker ps --filter name=inthub --format "{{.Names}} {{.Image}} {{.Status}}"'
ssh agenthub-prod 'df -h /opt/inthub'
```

Never print the full env, database URL, OAuth secret, cookie, or access token.

### 3. Resolve and pull from Gitee

```bash
SOURCE_REPOSITORY=https://gitee.com/dozybot/Intent.git
RELEASE_SHA=$(git ls-remote "$SOURCE_REPOSITORY" refs/heads/main | awk '{print $1}')
RELEASE_DIRECTORY=/opt/inthub/releases/$RELEASE_SHA
STAGING_DIRECTORY=$(mktemp -d /opt/inthub/releases/.staging.XXXXXX)

git clone --branch main --single-branch --no-tags "$SOURCE_REPOSITORY" "$STAGING_DIRECTORY"
test "$(git -C "$STAGING_DIRECTORY" rev-parse HEAD)" = "$RELEASE_SHA"
test ! -e "$RELEASE_DIRECTORY"
mv "$STAGING_DIRECTORY" "$RELEASE_DIRECTORY"
```

Both `ls-remote` and the cloned `HEAD` must match. Do not replace a failed Gitee pull
with a GitHub tarball.

### 4. Back up before build or activation

Create a UTC timestamped directory containing both a self-contained
`pg_dump --format=custom` and a mode-`0600` copy of `inthub.env`. Verify that the dump
is non-empty before building or switching a release.

### 5. Build an immutable image

```bash
sudo docker build \
  --build-arg INTHUB_VERSION="$INTHUB_PACKAGE_VERSION" \
  --tag "inthub:$RELEASE_SHA" \
  --file "$RELEASE_DIRECTORY/Dockerfile" \
  "$RELEASE_DIRECTORY"
```

Verify the image version label. A failed build must not change `current` or shared env.

### 6. Atomic activation and rollback

1. Preserve the old `current` target and an env rollback copy.
2. Generate an env candidate that changes only `INTHUB_RELEASE` and
   `INTHUB_PACKAGE_VERSION`.
3. Atomically replace env and `current`.
4. Start without rebuilding:

```bash
sudo docker compose \
  --project-name inthub \
  --env-file /opt/inthub/shared/inthub.env \
  --file /opt/inthub/current/deploy/inthub/compose.yaml \
  up --detach --no-build --remove-orphans
```

5. Within a bounded window, require both a healthy `inthub-app` container and a
   successful `http://127.0.0.1:7250/readyz`.
6. On any failure, restore old env and `current`, then start the old Compose release.

Application rollback does not roll back data. An incompatible schema release requires
the matching database restore.

### 7. Post-release verification

```bash
curl --fail --silent --show-error http://127.0.0.1:7250/healthz
curl --fail --silent --show-error http://127.0.0.1:7250/readyz
curl --fail --silent --show-error https://inthub.tenon.asia/healthz
curl --fail --silent --show-error https://inthub.tenon.asia/readyz

# Must be 401.
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  https://inthub.tenon.asia/api/v1/projects

# Must begin OAuth with 302.
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  https://inthub.tenon.asia/api/v1/auth/github/start
```

Also verify that `current`, env release, and container image are the same full Gitee
SHA; package version equals the image label; both containers are healthy; and the new
static asset revision is publicly readable.

## Caddy and DNS

DNS is `inthub.tenon.asia A 122.51.14.35`. Validate the shared Caddy root before
reloading:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl reload caddy
```

Reload only when [inthub.caddy](../../deploy/inthub/inthub.caddy) changes. A regular
application release does not reload Caddy.

## Runtime diagnosis

Use bounded, secret-free diagnostics:

```bash
sudo docker compose --project-name inthub \
  --env-file /opt/inthub/shared/inthub.env \
  --file /opt/inthub/current/deploy/inthub/compose.yaml ps
sudo docker logs --tail 200 inthub-app
sudo docker logs --tail 200 inthub-postgres
git ls-remote https://gitee.com/dozybot/Intent.git refs/heads/main
```

Check Gitee SHA first, then `current`/env/image identity, loopback health, Caddy/public
health, and finally the anonymous `401` boundary.

## Invariants

- Production code comes only from Gitee and never falls back to GitHub.
- Gitee downtime blocks a new release but does not affect the running instance.
- PostgreSQL and the app expose no public service port.
- Browser sessions are read-only; CLI writes require an account access token.
- GitHub OAuth tokens are not persisted, and GitHub App ownership grants no extra
  IntHub data access.
- Back up first, build second, switch last; restore the old release if the new one is
  not healthy.
- Do not reuse another service's container, database, secret, directory, Caddy site,
  or runtime credential.
- Logs, commands, and docs must not disclose account tokens, GitHub Client Secrets,
  database passwords, or cookies.

## Open questions

- Releases are still performed by the project session under this standard rather than
  one repository command. A future tool must hard-enforce Gitee-only provenance,
  backup, and rollback.
- Gitee and GitHub currently receive explicit pushes rather than server-side mirroring.
  Any future automation must retain Gitee as deployment authority and must not let a
  GitHub workflow directly source production code.
- Release retention and old image pruning are not automated. Preserve at least one
  verified rollback release and its database/env backup before cleanup.
