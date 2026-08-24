# IntHub Official Production Deployment

[中文](../CN/inthub-production.md) | [English](inthub-production.md)

## Metadata

- Status: implemented; production execution requires explicit authorization
- Owner: project maintainers
- Last verified: 2026-08-24
- Runtime surface: local Git, Gitee, isolated server Builder, Bundle, data, ingress
- Sole production entry: [release.sh](../../deploy/inthub/release.sh)
- Local qualification: [qualify-release.sh](../../deploy/inthub/qualify-release.sh)
- Server build launcher: [release-from-gitee.sh](../../deploy/inthub/release-from-gitee.sh)
- Bundle builder: [build-release.sh](../../deploy/inthub/build-release.sh)
- Production activator: [remote-release.sh](../../deploy/inthub/remote-release.sh)
- Manifest: [release_manifest.py](../../deploy/inthub/release_manifest.py)

## One supported path

Production accepts only a full Commit that has been published to and read back from Gitee
`main`. GitHub may receive the same history asynchronously, but it is not part of release
identity, qualification, build, rollback, or disaster recovery.

```text
clean local main Commit
  -> PostgreSQL integration tests, diff/check, exact-Commit source scan
  -> fast-forward Gitee main and read back the full SHA
  -> server independently reads the same Gitee SHA
  -> dedicated /opt/inthub/builder/source checkout
  -> server linux/amd64 Builder requalifies and builds exactly once
  -> final-image smoke
  -> source + images + Manifest v4 + SHA256SUMS
  -> atomically solidified read-only Bundle
  -> acquire fail-closed production lock only after Bundle verification
  -> PostgreSQL/env backup and explicit compatible migration
  -> inactive slot -> readiness -> reversible traffic switch -> public smoke
  -> update current -> observation window -> second public smoke -> stop old slot
```

The only routine production command is:

```bash
bash deploy/inthub/release.sh
```

Local image-Bundle uploads, `git pull` in a runtime directory, GitHub fallback, external
registries, mutable-tag deployments, and on-server source edits are unsupported. If Gitee,
the exact SHA, the Builder, or locked dependencies are unavailable, the release fails closed
and the current healthy release keeps serving.

## Fixed production boundary

| Surface | Standard value |
|---|---|
| Public URL | `https://inthub.tenon.asia` |
| Production host | `ubuntu@122.51.14.35` |
| Local SSH alias | `agenthub-prod` |
| Local Gitee write alias | `inthub-gitee` |
| Gitee production source | `https://gitee.com/dozybot/Intent.git` |
| Gitee release ref | `refs/heads/main` |
| Asynchronous GitHub mirror | `https://github.com/dozybot001/Intent.git` |
| Production root | `/opt/inthub` |
| App slots | `127.0.0.1:7250` / `127.0.0.1:7251` |
| Compose projects | `inthub`, `inthub-blue`, `inthub-green` |
| PostgreSQL | `inthub-postgres`, only on `inthub-private` |
| Caddy site | `/etc/caddy/sites-enabled/inthub.caddy` |
| Target platform | `linux/amd64` |
| Server Builder | `default`, driver=`docker` |

The recommended developer remote model is:

```text
origin  https://gitee.com/dozybot/Intent.git
github  https://github.com/dozybot001/Intent.git
```

The release program uses fixed Gitee read and write URLs rather than a remote name. Public
HTTPS performs readback, while `git@inthub-gitee:dozybot/Intent.git` performs only the
fast-forward publication. The remote layout keeps the operator model clear. GitHub pushes
happen separately; failure to mirror cannot change a completed production result.

The release machine needs a dedicated Gitee account SSH key once, with a local alias pinned
to that private key:

```sshconfig
Host inthub-gitee
  HostName gitee.com
  User git
  IdentityFile /absolute/path/to/inthub_gitee_push_ed25519
  IdentitiesOnly yes
```

Gitee repository deploy keys are read-only and cannot perform the fast-forward publication
required by the release entry. This therefore uses an independently revocable account key.
The private key remains only on the release machine and never enters the repository, server,
or Bundle.

## One-time control-plane bootstrap

Install the stable Gitee launcher once, or explicitly rerun the bootstrap when that control
plane changes:

```bash
bash deploy/inthub/bootstrap-gitee-deployment.sh
```

Bootstrap transfers only a small control-plane script. It does not transfer source or images,
read secrets, build, migrate, restart, or switch traffic. It verifies project directories,
the `0600` production env, Docker/Buildx, read-only Gitee access, host support for isolated
Python environments, and SHA-256 before installing:

```text
/opt/inthub/deploy/release-from-gitee.sh
```

The Ubuntu Builder has one system-level prerequisite:

```bash
sudo apt-get install python3-venv
```

Bootstrap verifies this dependency; it does not install or upgrade operating-system packages.

Every formal release compares the local and server launcher hashes. A mismatch fails with an
explicit bootstrap instruction; the release never upgrades its own production control plane.

## Local gate and Gitee publication

`release.sh` first runs `qualify-release.sh`, which:

1. requires a complete, clean `main` Commit and rejects shallow history, submodules, and LFS;
2. verifies the pinned PostgreSQL runtime config digest and `linux/amd64` platform;
3. runs the full suite, including real PostgreSQL integration, in the pinned pytest/psycopg environment;
4. runs `git diff --check` and Commit-object checks;
5. exports the exact Commit with `git archive` and scans it for unsafe entries and high-confidence credentials;
6. proves that HEAD and the worktree did not change during qualification.

After qualification, existing Gitee `main` must be an ancestor of the candidate. The program
performs only a fast-forward push of `<full-sha>:refs/heads/main` and must read the same SHA back
with `git ls-remote` before it contacts production.

## Isolated server build

The server launcher owns `/opt/inthub/.build-lock`, reads Gitee `main` again, and continues only
when it equals the requested SHA. Its dedicated state is:

```text
/opt/inthub/builder/
├── source/          complete Gitee-only checkout
├── tools/           pinned Python qualification cache
└── qualification/   temporary exact-source scan directories
```

The launcher cleans this checkout, fetches `main` and tags, checks out the exact Commit, and
runs `build-release.sh` with the server `default` linux/amd64 Builder. The builder repeats the
qualification gate, builds the App image exactly once, exercises the final image under the
read-only/cap-drop/no-new-privileges boundary, and emits an immutable Bundle. Runtime paths,
`current`, secrets, PostgreSQL, and Caddy are never build inputs.

## Bundle and Manifest v4

The exact Bundle file set is:

```text
source.tar.gz
images.tar.gz
manifest.json
SHA256SUMS
compose.yaml
inthub.caddy
release_manifest.py
remote-release.sh
runtime-images.lock.json
smoke.sh
```

Manifest v4 retains Commit, platform, Builder, dependency, database, image, test, recipe, and
checksum evidence and additionally requires:

```json
{
  "source": {
    "transport": "gitee-exact-commit",
    "repository": "https://gitee.com/dozybot/Intent.git",
    "ref": "refs/heads/main",
    "commit": "<full-sha>"
  }
}
```

The App OCI source label is fixed to `https://gitee.com/dozybot/Intent`. Unknown fields, extra
files, symlinks, path escape, and checksum/platform/config-digest/recipe/source drift fail closed.

## Solidification, database, and blue-green acceptance

The Bundle's `remote-release.sh` completely verifies untrusted incoming bytes before atomically
acquiring `/opt/inthub/.release-lock`. Qualification or build failures therefore cannot back up,
migrate, start a candidate, change traffic, or update `current`.

The mature activation contract remains unchanged:

1. atomically move the Bundle to read-only `/opt/inthub/releases/<full-sha>` and verify again;
2. create a non-empty custom-format PostgreSQL dump, verify it with `pg_restore --list`, and back up env/Manifest;
3. keep `INTHUB_AUTO_MIGRATE=0` and run only explicit backward-compatible expand/contract migration;
4. `docker load` from the Bundle and verify config digests, platform, and revision/version/schema labels;
5. keep the old slot serving while the candidate starts on inactive port 7250 or 7251;
6. validate and reload Caddy only after readiness;
7. update `current` only after public smoke, then stop the old slot only after the observation window and second public smoke.

Application rollback does not downgrade the database. Candidate, traffic-switch, or public-smoke
failure restores old Caddy/current, verifies the old slot, and removes the candidate. Incomplete
rollback preserves the production lock and phase state so later releases fail closed.

## Paths and interruption recovery

```text
/opt/inthub/
├── deploy/                    stable Gitee server launcher
├── builder/                   dedicated checkout, tools, and caches
├── incoming/                  untrusted server-built Bundles
├── releases/<full-sha>/       verified read-only Releases
├── current -> releases/...    last publicly accepted Release
├── shared/inthub.env          0600; never in Git, images, or Bundles
├── backups/<time>-<sha>/      env, Manifest, Caddy, PostgreSQL dump
├── logs/                      release audit
├── .build-lock/               server build owner/metadata
└── .release-lock/             production owner/metadata/phase state
```

- Local qualification or Gitee push failure never contacts production.
- Gitee readback or server build failure never acquires the production lock.
- After SSH interruption, inspect both locks, phase, Caddy, containers, and `current` before retrying.
- Incomplete production rollback preserves the lock for phase-aware manual recovery.
- Release, image, Builder-cache, backup, and data cleanup always requires separate authorization.

A same-host dump is not disaster recovery. Git history outside Gitee/GitHub, complete Releases,
secret recovery material, and database backups still require an encrypted second storage system
under the operator's control and periodic restore drills.
