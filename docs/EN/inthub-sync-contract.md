# IntHub Sync Contract (V1)

English | [中文](../CN/inthub-sync-contract.md)

## What this document answers

- How the first IntHub release should divide responsibility across the local Intent CLI, the IntHub backend, and GitHub
- What the first synchronization payload should look like
- How identity, idempotency, object ownership, and the minimum API surface should work
- Which capabilities are required for v1, and which should be explicitly deferred

## Relationship to other documents

- For product positioning and first-phase scope, see the [IntHub MVP design doc](inthub-mvp.md)
- For the local object model, see the [CLI design doc](cli.md)
- This document answers only: "how local `.intent/` data syncs safely into IntHub and becomes a remote collaboration view"

## 1. V1 invariants

- V1 supports **GitHub-first** repositories only
- GitHub provides repo identity, permissions, and Git context
- IntHub provides semantic-data sync, storage, indexing, and display
- `.intent/` must remain local workspace metadata, not committed to Git and not consumed as GitHub content
- The first IntHub Web release is **read-only** by default
- The local CLI remains the primary write path

## 2. First-release responsibility split

### Local CLI

Responsible for:

- reading `intent / snap / decision` from `.intent/`
- reading current Git context
- building a sync payload
- pushing that payload to IntHub

Not responsible for:

- remote object editing
- remote search indexing
- remote conflict resolution

### IntHub API

Responsible for:

- auth checks
- repo-binding checks
- accepting sync batches
- storing raw batches append-only
- deriving current read models
- serving overview / handoff / detail / search data to the Web app

### GitHub

Responsible for:

- user identity and repo authorization
- repo / branch / commit / release context

Not responsible for:

- semantic object primary storage
- semantic object querying
- semantic relationship computation

## 3. Provider and auth model

V1 supports GitHub as the only repo provider.

Recommended permission model:

- **prefer a GitHub App in production**
- allow a personal token temporarily for local development or early validation

Why:

- a GitHub App fits per-repo installation and revocable permissions better
- a personal token is fast, but weak as a long-term permission boundary

The first implementation may accept one simplifying constraint:

- one IntHub project may initially bind to one GitHub repo

That is an implementation simplification, not a permanent model limitation.

## 4. Local hub config

V1 should add a local-only file under `.intent/`:

```text
.intent/
  config.json
  hub.json
  intents/
  snaps/
  decisions/
```

`hub.json` is **runtime local config**, not part of the semantic object model.

Recommended minimum structure:

```json
{
  "api_base_url": "http://127.0.0.1:8000",
  "auth_token": "",
  "workspace_id": "wks_01J....",
  "project_id": "proj_01J....",
  "repo_binding": {
    "provider": "github",
    "repo_id": "dozybot001/Intent",
    "owner": "dozybot001",
    "name": "Intent"
  },
  "last_sync_batch_id": "sync_01J....",
  "last_synced_at": "2026-03-19T00:00:00Z"
}
```

Intent behind this design:

- `api_base_url` and `auth_token` are local runtime configuration
- `workspace_id` must stay stable for one checkout
- but it is not Git content and should not automatically travel across clones
- `project_id` and `repo_binding` connect the local workspace to IntHub

## 5. Identity and object ownership

V1 should distinguish at least these identifiers:

| Identifier | Meaning |
| --- | --- |
| `project_id` | IntHub project |
| `repo_id` | GitHub repository |
| `workspace_id` | one local checkout |
| `sync_batch_id` | one sync event |
| `remote_object_id` | IntHub internal object primary key |
| `local_object_id` | local `intent-001` / `snap-001` / `decision-001` |

Core V1 rule:

- local objects must not use `intent-001` directly as a remote primary key
- the remote uniqueness key should be:
  - `workspace_id`
  - `object_type`
  - `local_object_id`

So if two different workspaces both contain `intent-001`, the server must not assume they are the same object.

## 6. Suggested CLI surface for V1

V1 should introduce only the minimum entrypoints:

```bash
itt hub login
itt hub link
itt hub sync
```

Responsibilities:

- `itt hub login`
  - obtain an IntHub access token
- `itt hub link`
  - create or select an IntHub project
  - bind the current GitHub repo
  - initialize local `.intent/hub.json`
- `itt hub sync`
  - read `.intent/`
  - enrich with Git context
  - build and push one sync batch

V1 should avoid:

- `itt hub pull`
- `itt hub edit`
- `itt hub comment`

because those immediately push the system toward bidirectional collaboration instead of sync-first collaboration.

## 7. Sync batch payload

V1 should upload a **full object snapshot**, not an incremental patch.

Recommended minimum payload:

```json
{
  "sync_batch_id": "sync_01J...",
  "generated_at": "2026-03-19T00:00:00Z",
  "client": {
    "name": "intent-cli-python",
    "version": "1.2.0"
  },
  "project_id": "proj_01J...",
  "repo": {
    "provider": "github",
    "repo_id": "123456789",
    "owner": "dozybot001",
    "name": "Intent"
  },
  "workspace": {
    "workspace_id": "wks_01J..."
  },
  "git": {
    "branch": "main",
    "head_commit": "abc123",
    "dirty": true,
    "remote_url": "git@github.com:dozybot001/Intent.git"
  },
  "snapshot": {
    "schema_version": "1.0",
    "intents": [],
    "snaps": [],
    "decisions": []
  }
}
```

Notes:

- `snapshot.intents / snaps / decisions` carry the current local object JSON directly
- the client does not need to precompute derived views
- the client does not upload full shell logs or raw chat transcripts

## 8. Idempotency and acceptance rules

These rules should be fixed in V1:

### 8.1 Idempotency

- `sync_batch_id` is client-generated
- if the same `sync_batch_id` is retried, the server must return the same result and must not duplicate storage

### 8.2 Acceptance checks

The server should at minimum validate:

- whether the user has access to the IntHub project
- whether the repo is linked to that project
- whether the GitHub repo in the payload matches the linked repo
- whether the `workspace_id` belongs to the current project
- whether the `schema_version` is acceptable

### 8.3 Dirty worktrees

V1 should **allow** `dirty = true` syncs.

Why:

- semantic collaboration often happens before commit
- handoff should not have to wait for commit

But the Web UI must show the dirty state clearly so users do not assume the semantic state is cleanly aligned to a committed revision.

## 9. Server storage and derivation rules

V1 should use two storage layers:

### Raw layer

- append-only storage of each `sync batch`
- full raw payload retained

### Derived layer

- current object state derived from the latest batch per workspace
- project-level overview / handoff / search derived from workspace states

One important V1 simplification:

- **do not auto-merge semantic objects across workspaces**

That means:

- IntHub may aggregate multiple workspaces into one project view
- but it does not pretend two workspaces' `intent-001` are the same thing

## 10. Minimum API surface for V1

V1 should include at least:

### Write endpoints

- `POST /api/v1/hub/link`
- `POST /api/v1/sync-batches`

### Read endpoints

- `GET /api/v1/projects/:project_id/overview`
- `GET /api/v1/projects/:project_id/handoff`
- `GET /api/v1/intents/:remote_object_id`
- `GET /api/v1/decisions/:remote_object_id`
- `GET /api/v1/search`

V1 does not need yet:

- generic remote object update endpoints
- remote comment endpoints
- remote state mutation endpoints

## 11. Web read-model requirements for V1

The first Web release needs only 4 high-value views:

### Project Overview

Show:

- active intents
- active decisions
- recent snaps
- workspace sync status

### Handoff

Aggregate:

- currently active intents
- latest snap for each intent
- current active decisions

### Intent Detail

Show:

- current object state
- snap timeline
- origin workspace
- latest synced branch / commit / dirty state

### Search

Cover only:

- title
- query
- summary
- rationale

## 12. Security and privacy boundary

V1 must explicitly avoid uploading:

- full raw chat transcripts
- file contents
- diffs
- raw shell logs

The first sync path carries only structured semantic objects and the minimum Git context needed for collaboration.

This boundary matters. Without it, IntHub drifts into being a remote work-log platform.

## 13. Recommended implementation order

1. define `hub.json` and the `sync batch` schema
2. implement `itt hub link` / `itt hub sync`
3. implement `POST /sync-batches` and append-only storage
4. implement project overview / handoff read endpoints
5. implement read-only Web pages
6. add search last

## 14. How to know we are ready to build V1

Implementation should start only when these questions are no longer ambiguous:

- whether semantic data enters Git / GitHub
- what GitHub is responsible for in the system
- how a workspace is stably identified
- whether sync uses full snapshots
- whether dirty sync is allowed in V1
- whether the first Web release stays read-only

If these still drift, implementation should not start yet.
