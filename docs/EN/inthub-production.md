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

## Sole Tenon account entry and one-time migration

The sole sign-in entry is the same-origin `/auth/redirect` page. It paints a local waiting screen before calling `POST /api/v1/auth/tenon/prepare` for a backend-validated authorization URL. Failure or a 15-second timeout exposes retry and return actions; arbitrary destination parameters are not accepted. The direct start endpoint has been removed. The exact registered callback is
`https://inthub.tenon.asia/api/v1/auth/tenon/callback`. The issuer is fixed to
`https://account.tenon.asia/api/auth`; discovery supplies endpoints and signing keys.
Authlib validates signed ID Tokens, issuer, audience, expiration and nonce. Every attempt
uses S256 PKCE and a single-use browser-bound state. The callback requests only
`openid profile email`, verifies UserInfo sub, verified email and matching platform role,
then creates an independent product session without persisting central tokens.

Schema v3 adds exact `(issuer, subject)` mappings to existing `accounts.id`. Project ownership,
local business roles, public grants and PAT ownership are preserved. First-time Tenon users
receive ordinary local business records; email and display names never merge accounts.
Central admin applies only to a verified session, never permanently changes a business role,
and does not bypass private project ownership. Both ordinary and administrator product sessions
have a fixed 30-day (2592000-second) lifetime from issuance. Their persistent HttpOnly, Secure,
SameSite=Strict cookies use the same Max-Age. Token validity remains mandatory at callback and
session issuance; the verified local session then lasts independently of short OIDC tokens.
Product requests check only local sessions and identity mappings, with no per-request central
calls, sliding expiration or additional renewal mechanism. Ordinary central logout leaves valid
product sessions intact; IntHub logout immediately revokes the current local session. Central
outages cannot create or extend sessions. Role changes take effect on reauthorization, within
at most 30 days. Single-use state and PKCE login attempts remain valid for 10 minutes; CLI PATs
retain their own lifetimes. The runtime entry no longer reads the legacy INTHUB_SESSION_TTL_SECONDS
setting. Existing short sessions expire as issued; the next login creates a 30-day session.

Register the confidential web client once through Tenon's controlled `account/clients.mjs`
maintenance entry with `client_secret_basic`, a production lock, verified active container and
consistent database backup. Save the returned secret directly into the server's `0600` runtime
configuration as `INTHUB_TENON_CLIENT_ID` / `INTHUB_TENON_CLIENT_SECRET`; never put it in chat,
logs, Git, images or browser assets.

Existing-account binding is an explicit operator migration after proving the original product
owner and confirming the exact central subject. Back up IntHub first, then provide exact
`account_id` and `subject` through protected stdin to `python -m apps.inthub_api.bind_tenon`,
with `INTHUB_IDENTITY_MAINTENANCE=1`. Conflicts fail without overwriting mappings; identical
bindings are idempotent. This command is not exposed through HTTP. Legacy GitHub login returns
410 and its OAuth client implementation has been removed. Pre-migration browser sessions must
sign in again; PATs retain their original scope and expiration. Remove legacy OAuth configuration
after acceptance; application rollback requires its protected configuration backup and previous
image, without deleting mappings or downgrading the database. Actual owner login remains a
separate acceptance check from isolated protocol tests.

The first migration may stage those exact IDs in root-owned `0600`
`shared/tenon-binding.pending.json`. The normal publisher binds them under its release lock,
after database backup and migration but before candidate login, then moves the applied record
into that release's protected backup directory. The login button reuses Tenon's
`dist/assets/mark.svg` (2026-10-03), with fixed brand color `#F06B32`.

## Product-only deletion

The account menu calls `POST /api/auth/tenon/delete/start` with immediate loading feedback. The backend derives the exact subject from a valid local browser session and uses its existing confidential client to request a source-bound central link. The frontend accepts only `https://account.tenon.asia/account/delete/`. Tenon owns scope selection, recent authentication and final confirmation; IntHub provides no duplicate confirmation or identity flow.

`POST /api/auth/tenon/delete/execute` is server-only. It claims a short-lived grant with `client_secret_basic`, validates the exact issuer, `productId=inthub`, operation ID and subject, then deletes business data and commits a durable receipt in the same transaction. Browser sessions, admin privileges and client-provided identity claims cannot replace the proof; GET never deletes. A temporary central finish outage does not turn a committed deletion into a false failure.

Schema5 explicitly adds `product_deletion_receipts` and a server-owned login-attempt `started_at`. Receipts survive account deletion and contain only operation ID, issuer/subject and completion time. An authorized retry reads the existing receipt and never removes a subsequently re-created account. A completed central proof with a missing local receipt fails closed. Deletion and OIDC mapping share the same subject lock: a callback started before deletion cannot recreate the identity, while a newly initiated login may create a fresh business account. All former browser sessions and CLI PATs immediately stop working.

Removal covers the product account, identity mapping, sessions/PATs, public profile, all owned cloud projects, semantic versions/heads, sync batches and workspace copies. Deleted projects disappear from public pages; other accounts and their projects remain. **Local repositories and `.intent` files are untouched**; registering again does not restore removed cloud data. The central Tenon account and other products remain. Minimal deletion receipts and backups subject to existing rotation policy are retained; online deletion is not represented as immediate backup erasure.

See the [implementation](../../apps/inthub_api/product_deletion.py), [isolation and failure tests](../../tests/test_inthub_product_deletion.py) and [PostgreSQL concurrency tests](../../tests/test_inthub_postgres.py). The formal publisher backs up and explicitly applies the candidate schema5 expansion; live startup retains `INTHUB_AUTO_MIGRATE=0`. Initial activation must finish all product releases and verify that old slots have stopped before registering central deletion metadata; an old callback writer must never overlap real deletion.

## Shared semantic history and compatible migration

Semantic synchronization is independent of source Git. Schema v4 adds only `semantic_heads`
and `semantic_versions`, preserving all legacy workspace data. A named project has one
account-private shared history. Revisions hash the parent and canonical full snapshot.
Head validation and advancement share one transaction: SQLite uses BEGIN IMMEDIATE,
PostgreSQL a row lock. Identical content is idempotent; divergent pushes never overwrite.

POST `/api/v2/link` links idempotently, GET `/api/v2/history?project=NAME` reads the head,
and POST `/api/v2/history` accepts fast-forward revisions. Existing PAT authentication
remains; browser sessions cannot write. Workspace link/sync/snapshot endpoints, import options and compatibility paths are removed.
Historical table definitions remain only for migration integrity and old-image rollback,
without product entry points. This release does not migrate or reupload local exports.

Sources: [server history](../../apps/inthub_api/history.py),
[CLI synchronization](../../src/intent_cli/commands/shared.py),
[multi-client tests](../../tests/test_shared_history.py),
[PostgreSQL concurrency tests](../../tests/test_inthub_postgres.py).

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
