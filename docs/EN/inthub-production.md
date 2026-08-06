# IntHub Official Production Deployment Standard

[中文](../CN/inthub-production.md) | [English](inthub-production.md)

## Metadata

- Status: implemented locally; production execution requires separate authorization
- Owner: project maintainers
- Last verified: 2026-08-07
- Runtime surface: local Git, Builder, Bundle, SSH, server, data, ingress
- Only supported entry: [release.sh](../../deploy/inthub/release.sh)
- Local implementation: [local-release.sh](../../deploy/inthub/local-release.sh)
- Build entry: [build-release.sh](../../deploy/inthub/build-release.sh)
- Server activation: [remote-release.sh](../../deploy/inthub/remote-release.sh)
- Manifest: [release_manifest.py](../../deploy/inthub/release_manifest.py)

## Summary

IntHub's default production path is controlled entirely by the local machine and target
server:

```text
clean local main commit
  → commit-exact source archive
  → cached qualification environment + pinned PostgreSQL integration tests
  → one build on the shared Docker Desktop linux/amd64 Builder
  → local smoke of the final App image under production security constraints
  → source + images + manifest + SHA256SUMS
  → full on-disk re-verification and atomic Bundle publication
  → SSH/rsync into incoming
  → server verifies before acquiring the fail-closed lock
  → read-only Release, backup, and explicit compatible migration
  → inactive slot → readiness → reversible traffic switch → public smoke
  → current update → observation window → second public smoke → old slot stops
```

The daily command is:

```bash
bash deploy/inthub/release.sh
```

It does not call the GitHub API, wait for cloud CI, push commits, publish production data
to a Registry, or clone, install dependencies, or build on the server. Running it initiates
a release operation, but production authorization still follows current project policy.
Running `build-release.sh` alone only creates a Bundle and never contacts the server.

## GitHub boundary

The approved GitHub `origin` is an asynchronous mirror. `.github/workflows/tests.yml` may
provide extra feedback for synchronized commits, but it is not a production gate and does
not create or deploy production artifacts.

- A commit need not be pushed; `origin/main` does not identify or qualify a Release.
- Production scripts read no remote URL, GitHub token, Actions status, or GHCR state.
- GitHub outage does not block local build, release, acceptance, or rollback.
- The Manifest records no GitHub sync, PR, workflow-run, or cloud-state field.
- GitHub synchronization is a separate ordinary Git operation and is never hidden in
  `release.sh`.
- GitHub is not the only backup; local Git, Bundles, and recovery materials need a second
  storage location under operator control.

## Low-cost local adaptation

The existing Docker Desktop `desktop-linux` Builder uses the `docker` driver and advertises
`linux/amd64`. IntHub reuses it as a machine-wide Builder rather than maintaining a project
VM. Every build records and validates the Builder name, driver, Buildx version, and target
platform. Moving to another trusted Builder requires explicit `INTHUB_BUILDER` and
`INTHUB_BUILDER_DRIVER`; there is no fallback to an unknown Builder.

[prepare-release-env.sh](../../deploy/inthub/prepare-release-env.sh) caches the pinned
qualification environment under `dist/inthub-tools/<python-id>-<dependency-id>`. The ID is
derived from the local Python identity and `pyproject.toml` SHA-256. First use creates a venv
and installs dependencies; unchanged dependencies reuse it. The ignored `dist/` cache never
enters Git, the source archive, image, Bundle, or server.

## Local qualification

Before publishing a Bundle, `build-release.sh` requires a clean `main`, fixes the full commit,
checks Docker/Buildx and the configured Builder, validates the pinned PostgreSQL image,
prepares the cached Python environment, starts a temporary Linux/amd64 PostgreSQL container,
and runs the full pytest suite including PostgreSQL integration. It then runs diff and commit
checks, exports source with `git archive`, scans tracked source, derives the database schema,
and builds `inthub:<full-sha>` exactly once.

The script verifies portable App and database config digests from the `docker save` archive,
platform and OCI labels, starts the final App
image read-only with dropped capabilities and `no-new-privileges`, runs health smoke, exports
both images, writes the Manifest and exact SHA-256 set, rereads everything from disk, and
atomically renames the result to `dist/inthub/<full-sha>`. A failure creates no deployable
Bundle. An existing Bundle is reused only after full verification and is never overwritten.

## Bundle and Manifest v3

The exact Bundle contains `source.tar.gz`, `images.tar.gz`, `manifest.json`, `SHA256SUMS`,
Compose/Caddy definitions, the standard-library verifier, the lock-protected remote entry,
the runtime image lock, and smoke checks.

Manifest v3 records `project_id=inthub`, full `git_sha`, `bundle_id=<git-sha>`, `dirty=false`,
linux/amd64 target, App and PostgreSQL image identities and labels, Builder/Buildx metadata,
Python and pytest versions, executed checks, build-recipe checksums, database schema and
expand/contract compatibility, and sizes/checksums for every artifact and release file.

Verification rejects unknown fields, malformed JSON and types, missing or extra files,
symlinks, source-tar escapes or special entries, size/checksum drift, platform/image/label
drift, and runtime-lock mismatch. GitHub sync state is an unknown field and cannot enter
Release semantics.

The portable image identity is the config digest stored in docker-save's `Config` member,
not `docker image inspect .Id`. Docker Desktop's containerd image store reports an OCI
manifest or index digest there, while a classic Docker Engine reports the config digest.
Reading the archive makes build-host and production-host verification agree across both
stores. The PostgreSQL lock separately pins the exact linux/amd64 platform manifest digest.

## Upload and server activation

`local-release.sh` uploads only a completely verified Bundle into a unique incoming path.
The server verifies the remote script SHA and complete Bundle before atomically acquiring
`/opt/inthub/.release-lock`, then records commit, Bundle ID, client, and start time. SSH uses
keepalive; after remote execution starts, a disconnected client leaves the lock fail closed
because production outcome is unknown.

The server never contacts GitHub, a Registry, or dependency source and runs no Git, pip, apt,
build, or pull. It loads images from the immutable Bundle and rechecks config digests, platforms,
and labels. Releases live at `/opt/inthub/releases/<bundle-id>`, while `current` means only the
last Release that passed public acceptance. Secrets remain in mode-0600
`/opt/inthub/shared/inthub.env`; backups and release state remain separate.

## Database, slots, and rollback

Serving Apps use `INTHUB_AUTO_MIGRATE=0`. After a validated backup, the release explicitly
runs the candidate image's backward-compatible migration. Changes follow expand/contract;
automatic application rollback never downgrades the database.

The App uses loopback blue/green slots 7250 and 7251. The old slot remains live throughout
candidate readiness, Caddy switch, public smoke, and the observation window. Only after the
first public smoke does `current` move atomically. The default 30-second observation window
and a second public smoke must pass before the old slot stops.

Local qualification failure never uploads. Upload or pre-verification failure never acquires
the production lock. Candidate failure leaves the old slot serving. Traffic, public-smoke,
or observation failure restores old Caddy/current and removes the candidate. Incomplete
rollback preserves the lock and phase journal; operators inspect lock, state, Caddy, current,
and containers before any retry. Cleanup of Releases, images, secrets, volumes, or backups
always requires separate authorization.

A same-host dump supports release rollback but is not disaster recovery. Git history, full
Bundles, secret recovery material, and database backups need encrypted second storage and
regular restore drills under operator control.

## Prerequisites

Docker Desktop and `desktop-linux` must be running locally, the machine must be able to create
a Python venv and obtain pinned dependencies on first use, and SSH defaults to `agenthub-prod`
unless `INTHUB_DEPLOY_HOST` is explicit. Production needs Docker Engine/Compose, Caddy,
Python 3, gzip, curl, sha256sum, a mode-0600 non-symlinked environment file, prepared DNS/TLS
and GitHub OAuth callback, and explicit production authorization.

Tool installation, secret creation, backup cleanup, database maintenance, and an actual
production release are never hidden infrastructure-build side effects. This standard defines
and verifies the entry; it does not grant production authority.
