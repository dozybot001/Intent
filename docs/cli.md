English | [简体中文](cli.CN.md)

# Intent CLI Specification

Schema version: **0.3**

Intent CLI is a semantic history tool built on Git. It records what problem you are working on, what you did, and why — using three objects: **intent**, **snap**, and **decision**.

Core loop: `init → start → snap → done` (with `decide` to capture cross-cutting decisions)

## 1. Object Model

### Intent

An intent represents a unit of work — typically one problem or task.

| Field            | Type   | Description                     |
| ---------------- | ------ | ------------------------------- |
| `id`             | string | e.g. `intent-001`              |
| `object`         | string | Always `"intent"`              |
| `schema_version` | string | `"0.3"`                        |
| `created_at`     | string | ISO 8601 UTC                   |
| `updated_at`     | string | ISO 8601 UTC                   |
| `title`          | string | What problem is being solved   |
| `status`         | string | `open`, `suspended`, or `done` |
| `decision_ids`   | list   | Related decision IDs           |

### Snap

A snap records a step taken within an intent — what was done and why.

| Field            | Type   | Description                          |
| ---------------- | ------ | ------------------------------------ |
| `id`             | string | e.g. `snap-001`                      |
| `object`         | string | Always `"snap"`                      |
| `schema_version` | string | `"0.3"`                              |
| `created_at`     | string | ISO 8601 UTC                         |
| `updated_at`     | string | ISO 8601 UTC                         |
| `title`          | string | What was done                        |
| `rationale`      | string | Why (from `-m` flag)                 |
| `status`         | string | `active` or `reverted`               |
| `intent_id`      | string | Parent intent ID                     |
| `git`            | object | Git context at time of snap          |

**Snap status semantics:**

- `active` — default when created with `snap`. This step is accepted.
- `reverted` — was active, then rolled back via `revert`.

### Decision

A decision records a cross-cutting choice that may span multiple intents.

| Field                 | Type   | Description                              |
| --------------------- | ------ | ---------------------------------------- |
| `id`                  | string | e.g. `decision-001`                      |
| `object`              | string | Always `"decision"`                      |
| `schema_version`      | string | `"0.3"`                                  |
| `created_at`          | string | ISO 8601 UTC                             |
| `updated_at`          | string | ISO 8601 UTC                             |
| `title`               | string | What was decided                         |
| `rationale`           | string | Why this choice was made                 |
| `status`              | string | `active` or `deprecated`                 |
| `intent_ids`          | list   | Related intent IDs                       |
| `created_from_intent_id` | string | Intent that prompted this decision    |

## 2. State Machine

### Workspace status

Derived from current state, stored in `state.json`:

| Status     | Meaning                                   |
| ---------- | ----------------------------------------- |
| `idle`     | No active intent                          |
| `active`   | One intent is open                        |

### Intent lifecycle

```
open → done
open → suspended → open → done
```

An intent is `open` when created by `start`, and becomes `done` when closed by `done`. An open intent can be `suspended` via `suspend` and later resumed with `resume`.

## 3. Storage Layout

```
.intent/
  config.json           # {"schema_version": "0.3"}
  state.json            # workspace state
  intents/
    intent-001.json
    intent-002.json
  snaps/
    snap-001.json
    snap-002.json
  decisions/
    decision-001.json
    decision-002.json
```

### state.json

```json
{
  "schema_version": "0.3",
  "active_intent_id": null,
  "workspace_status": "idle",
  "updated_at": "2026-03-17T10:00:00Z"
}
```

## 4. Commands

All commands output JSON. There is no human-readable text mode and no `--json` flag.

### version

Print version info.

```
itt version
```

```json
{
  "ok": true,
  "action": "version",
  "result": { "version": "0.3.0" }
}
```

### init

Initialize Intent in the current Git repository. Creates `.intent/` directory with `config.json`, `state.json`, and subdirectories for intents and snaps.

```
itt init
```

Fails if `.intent/` already exists or if not inside a Git worktree.

### start

Create and activate a new intent. Only one intent can be open at a time.

```
itt start "Fix the login timeout bug"
```

```json
{
  "ok": true,
  "action": "start",
  "result": {
    "id": "intent-001",
    "object": "intent",
    "schema_version": "0.3",
    "created_at": "2026-03-17T10:00:00Z",
    "updated_at": "2026-03-17T10:00:00Z",
    "title": "Fix the login timeout bug",
    "status": "open",
    "decision_ids": [],
    "attached_decisions": []
  },
  "warnings": []
}
```

Fails if an intent is already open. Close it with `itt done` or suspend it with `itt suspend`.

### snap

Record a snap against the active intent. The snap status is `active`.

```
itt snap "Increase timeout to 30s" -m "Default 5s was too short for slow networks"
```

### revert

Revert the latest active snap within the active intent.

```
itt revert
itt revert -m "Approach caused regression in tests"
```

Changes the snap status from `active` to `reverted`. Fails if no active snap exists.

### suspend

Suspend the active intent. The workspace becomes `idle`, allowing you to start or resume a different intent.

```
itt suspend
```

Fails if no intent is active.

### resume

Resume a suspended intent. If there is exactly one suspended intent, no ID is needed. On resume, the CLI catches up on any decisions created while the intent was suspended.

```
itt resume
itt resume intent-001
```

Fails if an intent is already active, or if multiple suspended intents exist and no ID is specified (the error will list them).

### decide

Create a new decision linked to the active intent.

```
itt decide "Use PostgreSQL for persistence" -m "Evaluated Redis and SQLite; PG best fits our query patterns"
```

The decision is created with status `active` and linked to the current intent via `created_from_intent_id`. The decision's ID is also added to the intent's `decision_ids`.

### deprecate

Deprecate an existing decision.

```
itt deprecate decision-001
itt deprecate decision-001 -m "Migrating to SQLite for simpler deployment"
```

Changes the decision status from `active` to `deprecated`.

### done

Close the active intent (or a specific intent by ID).

```
itt done
itt done intent-001
```

Sets the intent status to `done`, clears `active_intent_id`, and sets workspace status to `idle`.

### inspect

Machine-readable workspace snapshot. Returns the current state in a single flat JSON object.

```
itt inspect
```

```json
{
  "ok": true,
  "schema_version": "0.3",
  "workspace_status": "active",
  "intent": { "id": "intent-001", "title": "Fix the login timeout bug", "status": "open", "decision_ids": ["decision-001"] },
  "latest_snap": { "id": "snap-002", "title": "Increase timeout to 30s", "status": "active", "rationale": "Default 5s was too short" },
  "active_decisions": [{ "id": "decision-001", "title": "Use PostgreSQL for persistence", "status": "active" }],
  "suspended_intents": [],
  "suggested_next_action": {
    "command": "itt snap 'Describe the step'",
    "reason": "Intent is active."
  },
  "git": {
    "branch": "fix/login-timeout",
    "head": "a1b2c3d",
    "working_tree": "dirty"
  },
  "warnings": ["Git working tree is dirty; recording working tree context."]
}
```

When no intent is active, `intent` and `latest_snap` are `null`, `active_decisions` and `suspended_intents` are `[]`, and `suggested_next_action` recommends `itt start` (or `itt resume` if suspended intents exist).

### list

List all objects of a given type, sorted newest first.

```
itt list intent
itt list snap
itt list decision
```

```json
{
  "ok": true,
  "action": "list",
  "result": [ ... ],
  "count": 3
}
```

### show

Show a single object by its ID. The object type is inferred from the ID prefix (`intent-`, `snap-`, or `decision-`).

```
itt show intent-001
itt show snap-003
itt show decision-001
```

## 5. JSON Output Contract

### Success envelope

Every successful command returns:

```json
{
  "ok": true,
  "action": "<command-name>",
  "result": { ... },
  "warnings": []
}
```

Exception: `inspect` returns a flat structure with `"ok": true` at the top level (no `action`/`result` wrapper).

### Error envelope

Every error returns:

```json
{
  "ok": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable explanation.",
    "details": {},
    "suggested_fix": "itt ..."
  }
}
```

`suggested_fix` is present only when applicable.

## 6. Exit Codes

| Code | Constant              | Meaning              |
| ---- | --------------------- | -------------------- |
| 0    | `EXIT_SUCCESS`        | OK                   |
| 1    | `EXIT_GENERAL_FAILURE`| General failure       |
| 2    | `EXIT_INVALID_INPUT`  | Bad arguments         |
| 3    | `EXIT_STATE_CONFLICT` | State conflict        |
| 4    | `EXIT_OBJECT_NOT_FOUND`| Object not found     |

## 7. Error Codes

| Code                | When                                             |
| ------------------- | ------------------------------------------------ |
| `NOT_INITIALIZED`   | `.intent/` does not exist                        |
| `ALREADY_EXISTS`    | `init` called when `.intent/` already exists     |
| `GIT_STATE_INVALID` | Not inside a Git worktree                        |
| `STATE_CONFLICT`    | Intent already open, invalid state transition, etc. |
| `OBJECT_NOT_FOUND`  | ID does not resolve to a stored object           |
| `INVALID_INPUT`     | Bad arguments or conflicting flags               |

## 8. Git Context

Each snap records a `git` object:

```json
{
  "branch": "main",
  "head": "a1b2c3d",
  "working_tree": "clean",
  "linkage_quality": "stable_commit"
}
```

| `linkage_quality`       | Meaning                                  |
| ----------------------- | ---------------------------------------- |
| `stable_commit`         | Clean tree, HEAD resolved                |
| `working_tree_context`  | Dirty tree or HEAD unresolved            |
| `explicit_ref`          | User-supplied ref was resolved           |

`inspect` returns a subset of git context (`branch`, `head`, `working_tree`) at the top level.

## 9. ID Format

- Intents: `intent-001`, `intent-002`, ...
- Snaps: `snap-001`, `snap-002`, ...
- Decisions: `decision-001`, `decision-002`, ...

IDs are zero-padded to 3 digits, auto-incremented per type.
