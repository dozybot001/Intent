# IntHub Official Production Deployment Standard

[中文](../CN/inthub-production.md) | [English](inthub-production.md)

## Metadata

- Status: implemented
- Owner: project maintainers
- Last verified: 2026-08-04
- Runtime surface: build, package, deploy, ops, data, web, API
- Supported entry point: [deploy/inthub/release.sh](../../deploy/inthub/release.sh)
- Internal implementation:
  - [build-release.sh](../../deploy/inthub/build-release.sh) — builds and verifies a release bundle from a clean commit
  - [release_manifest.py](../../deploy/inthub/release_manifest.py) — creates and strictly verifies the manifest and checksums
  - [remote-release.sh](../../deploy/inthub/remote-release.sh) — verifies, backs up, loads, accepts, and rolls back on the server
  - [runtime-images.lock.json](../../deploy/inthub/runtime-images.lock.json) — locks the database runtime identity
  - [smoke.sh](../../deploy/inthub/smoke.sh) — internal and public acceptance
  - [compose.yaml](../../deploy/inthub/compose.yaml) — can start only preloaded images
  - [inthub.caddy](../../deploy/inthub/inthub.caddy) — owns IntHub's isolated public ingress

## Summary

IntHub production releases use this fixed chain:

```text
local clean main commit
  → export a commit-exact source context from Git objects
  → build on the machine-wide linux/amd64 Builder
  → smoke-test the exact image locally
  → source archive + image archive + manifest + SHA-256
  → upload over SSH into /opt/inthub/incoming
  → acquire /opt/inthub/.release-lock
  → verify and docker load on the server; never clone, build, or pull
  → back up PostgreSQL and the environment file
  → start the inactive App slot with --no-build --pull never
  → candidate readiness while the old slot keeps serving
  → switch Caddy traffic + public smoke
  → atomically switch /opt/inthub/current and stop the old slot
  → route back to the still-running old slot on failure; never downgrade the database
```

The only supported production command is:

```bash
bash deploy/inthub/release.sh
```

`build-release.sh` may be run alone to produce a bundle without affecting production.
`remote-release.sh` is an internal step and refuses normal use without the project release
lock created by the supported entry point.

## Git and remote boundary

The project keeps one remote by default:

```text
origin  https://github.com/dozybot001/Intent.git
```

GitHub is an asynchronous backup, collaboration, CI, and Pages surface. It is not a
build or deployment dependency:

- the local full Git SHA identifies a release, not a branch name or remote state;
- release qualification requires a clean local `main` and passing checks, not a push;
- a clean local commit may be released while GitHub is unavailable;
- the manifest records `github_sync: pending` by default; use
  `INTHUB_GITHUB_SYNC_STATUS=confirmed` only after explicitly confirming the push;
- every bundle carries a commit-exact source archive, including for unpushed commits;
- production never runs `git clone`, `git pull`, `git fetch`, or contacts GitHub;
- release code never rewrites remotes, adds Gitee, or falls back to another mirror.

GitHub synchronization remains a separate operation:

```bash
git push origin main
```

It is not a hidden `release.sh` step and does not authorize a production release.

## Official runtime boundary

| Item | Standard value |
|---|---|
| Public URL | `https://inthub.tenon.asia` |
| Local SSH alias | `agenthub-prod` |
| Production root | `/opt/inthub` |
| Loopback slots | `127.0.0.1:7250` (blue), `127.0.0.1:7251` (green) |
| Target platform | `linux/amd64` |
| Shared Builder | `shared-linux-amd64` |
| Compose project | `inthub` |
| App containers | `inthub-app-blue` / `inthub-app-green`; first migration accepts legacy `inthub-app` |
| PostgreSQL container | `inthub-postgres` |
| PostgreSQL volume | `inthub-postgres-data` |
| Caddy site | `/etc/caddy/sites-enabled/inthub.caddy` |

PostgreSQL exposes no host port, and the application binds only to loopback. IntHub
does not reuse another project's containers, database, secrets, directories, lock,
Caddy site, or deployment credentials.

## Shared Builder

IntHub uses a machine-wide Builder selected by target platform, not a project-specific
Builder. The default is `shared-linux-amd64`; `INTHUB_BUILDER` may select another trusted
Linux/amd64 Builder explicitly.

One-time machine bootstrap happens outside a production release:

```bash
docker buildx create \
  --name shared-linux-amd64 \
  --driver docker-container \
  --platform linux/amd64
docker buildx inspect shared-linux-amd64 --bootstrap
```

The Builder receives only the tracked source context exported from the selected commit.
It never receives production environment files, PostgreSQL data, OAuth secrets, CLI
tokens, or SSH private keys. Dependency bootstrap and cache refresh happen before a
production lock is acquired. A missing Builder never causes an on-server build fallback.

## Release bundle

`build-release.sh` creates a non-overwritable bundle under
`dist/inthub/<full-sha>/`. `dist/` is ignored by Git. Its exact file set is:

```text
source.tar.gz          commit-exact tracked source archive
images.tar.gz          linux/amd64 IntHub and PostgreSQL image archive
manifest.json          provenance, platform, image IDs, recipes, and checks
SHA256SUMS             SHA-256 for the exact bundle file set
compose.yaml           production Compose; no build and pull_policy=never
inthub.caddy           isolated project ingress
release_manifest.py    standard-library verifier used on the server
remote-release.sh      lock-protected internal activation step
runtime-images.lock.json  PostgreSQL reference, pull digest, image ID, and platform lock
smoke.sh               anonymous internal and public acceptance
```

The manifest proves at least:

- schema version, project ID, full Git SHA, and `dirty: false`;
- audit-only `github_sync: pending|confirmed`;
- target `linux/amd64`;
- source/image archive names, byte counts, and SHA-256 checksums;
- App and PostgreSQL references, image IDs, platforms, and available RepoDigests;
- exact agreement between PostgreSQL metadata and `runtime-images.lock.json`; an App
  release cannot upgrade the database runtime implicitly;
- App OCI revision, version, and source labels;
- SHA-256 for the Dockerfile and `pyproject.toml`;
- Builder name, driver, Buildx version, and build time;
- passing `pytest`, `git diff --check`, and local smoke of the exact production image.

The verifier rejects unknown fields, extra or missing files, symlinks, non-regular files,
invalid types, truncated JSON, path escapes, size or checksum mismatches, wrong platforms,
and revision/version mismatches. Production loads no image and changes no service before
those checks pass.

## Local qualification

Before any SSH upload, the supported entry point:

1. requires a clean worktree, including no untracked files;
2. requires the `main` branch;
3. runs the complete `pytest -q` suite;
4. runs `git diff --check`;
5. exports the source archive and isolated context from the commit;
6. scans the commit-exact context for high-confidence credential material;
7. builds `inthub:<full-sha>` for Linux/amd64 on the shared Builder;
8. requires the PostgreSQL image ID, immutable pull digest, and Linux/amd64 platform to
   match the project lock exactly;
9. starts the exact App image read-only, capability-free, and with
   `no-new-privileges`, then checks `/healthz` and `/readyz`;
10. packages both images and regenerates and re-verifies all evidence.

An existing bundle for the same SHA is never overwritten. It may be reused only after a
complete verification.

## Server directories and secrets

```text
/opt/inthub/
├── incoming/<sha>-<operation>/
├── releases/<full-sha>/
├── current -> releases/<full-sha>
├── shared/inthub.env              # 0600
├── backups/<timestamp>-<sha>/
│   ├── inthub.dump                # 0600 when a database exists
│   ├── inthub.env                 # 0600
│   ├── release-manifest.json      # 0600
│   └── inthub.caddy               # only when ingress changes
└── .release-lock/
    ├── owner
    └── metadata
```

Real configuration exists only in `/opt/inthub/shared/inthub.env`, mode `0600`. It
contains the domain, PostgreSQL password, GitHub App client ID/secret, session TTL, and
limits. Operators no longer maintain release SHA, package version, App container, or the
blue/green port; activation injects them from the verified manifest and restricted slot
set, preventing drift between the secret file and release/traffic state.

Secrets, database dumps, user data, access tokens, and cookies never enter Git, the
Builder, build context, image layers, bundle, manifest, logs, or Memory.

## Remote release order

`release.sh` transfers only the bundle over SSH/rsync and then:

1. creates project-owned incoming, releases, backups, and shared directories;
2. uploads into a unique operation directory;
3. checks the uploaded `remote-release.sh` against its local SHA-256;
4. acquires fail-closed `/opt/inthub/.release-lock` with atomic `mkdir`;
5. re-verifies the exact bundle file set, manifest, and all checksums;
6. promotes a new bundle to read-only `releases/<full-sha>`; an existing SHA must have
   exactly the same immutable content;
7. backs up the mode-0600 environment file and, when a PostgreSQL volume exists,
   requires a running database, writes a custom-format dump, and validates it with
   `pg_restore --list`;
8. when a database exists, first requires its running image ID to match the runtime lock;
   mismatches require a separate database maintenance procedure;
9. runs `docker load`, then verifies image IDs, platforms, and OCI labels;
10. leaves the current App slot and Caddy untouched while starting the inactive 7250/7251
    slot with `--no-deps --no-build --pull never`;
11. waits for candidate App and PostgreSQL health plus candidate loopback `/readyz`;
12. renders the candidate port into the Caddy site, backs up the old site, validates the
    root configuration, and reloads Caddy to switch traffic;
13. runs candidate loopback and official-domain smoke while the old slot remains running;
14. atomically switches `current` with a same-filesystem symlink rename;
15. verifies that `current` and the serving slot image use the same SHA, then stops the old
    slot and releases the lock.

SSH keepalives are enabled. After remote execution starts, a disconnected client does
not remove the lock because completion is unknown. Inspect `current`, containers, and
`.release-lock/metadata` read-only before deciding how to recover.

## Acceptance

Both internal and public surfaces must satisfy:

- `/healthz` and `/readyz` succeed;
- anonymous `/api/v1/projects` returns `401`;
- GitHub OAuth start returns `302` or `303`;
- `TRACE` returns `405`;
- the homepage contains the required CSP;
- the active `inthub-app-blue` or `inthub-app-green` and `inthub-postgres` are healthy;
- PostgreSQL publishes no host port;
- App revision/version labels match the manifest;
- `current` resolves to the expected full SHA.

Automation cannot claim that the signed-in product journey or visual UI has been accepted
for the user. Hand off the public URL for human review after UI releases.

## Rollback and database boundary

- a candidate-health, Caddy, or public-smoke failure restores the old Caddy site and
  removes the candidate; the old slot was never stopped, so rollback does not depend on
  restarting the previous application;
- a failed first release stops the rejected App but preserves the PostgreSQL volume;
- application rollback never runs a database downgrade;
- schema changes use expand/contract so the previous App remains compatible during the
  rollback window;
- rollback never deletes releases, images, secrets, backups, or volumes;
- a same-host mode-0600 dump is release rollback evidence, not disaster recovery;
  critical data still requires encrypted off-host copies, retention, and restore drills;
- release, image, and backup cleanup is a separate explicitly authorized operation.

## Caddy and first-host bootstrap

After DNS points at the production host, the supported entry may install or update only
IntHub's Caddy site. It never overwrites the shared root Caddyfile or another project
site. It saves the old site first and restores it if validation or public smoke fails.

Before a host's first release, an operator separately:

1. installs Docker CLI, Buildx, and a usable Engine locally; installs Docker
   Engine/Compose, Caddy, Gzip, Python 3, rsync, and SHA-256 tools on the server;
2. configures SSH and project-directory sudo permissions;
3. creates mode-`0600` `/opt/inthub/shared/inthub.env`;
4. bootstraps the machine-wide `shared-linux-amd64` Builder;
5. confirms DNS and the GitHub App callback;
6. obtains authorization for the production release, then runs the single entry point.

Tool installation and secret configuration are not hidden inside a normal App release.
