English | [简体中文](../CN/cli.md)

# Intent CLI Specification

Schema version: **0.2**

Intent CLI is a semantic history tool built on Git. It records what problem you are working on, what you did, and why — using two objects: **intent** and **checkpoint**.

Core loop: `init → start → snap → done`

## 1. Object Model

### Intent

An intent represents a unit of work — typically one problem or task.

| Field            | Type   | Description                     |
| ---------------- | ------ | ------------------------------- |
| `id`             | string | e.g. `intent-001`              |
| `object`         | string | Always `"intent"`              |
| `schema_version` | string | `"0.2"`                        |
| `created_at`     | string | ISO 8601 UTC                   |
| `updated_at`     | string | ISO 8601 UTC                   |
| `title`          | string | What problem is being solved   |
| `status`         | string | `open` or `done`               |

### Checkpoint

A checkpoint records a step taken within an intent — what was done and why.

| Field            | Type   | Description                          |
| ---------------- | ------ | ------------------------------------ |
| `id`             | string | e.g. `cp-001`                        |
| `object`         | string | Always `"checkpoint"`               |
| `schema_version` | string | `"0.2"`                              |
| `created_at`     | string | ISO 8601 UTC                         |
| `updated_at`     | string | ISO 8601 UTC                         |
| `title`          | string | What was done                        |
| `rationale`      | string | Why (from `-m` flag)                 |
| `status`         | string | `adopted`, `candidate`, or `reverted`|
| `intent_id`      | string | Parent intent ID                     |
| `git`            | object | Git context at time of snap          |

**Checkpoint status semantics:**

- `adopted` — default when created with `snap`. This step is accepted.
- `candidate` — created with `snap --candidate`. Awaiting explicit `adopt`.
- `reverted` — was adopted, then rolled back via `revert`.

## 2. State Machine

### Workspace status

Derived from current state, stored in `state.json`:

| Status     | Meaning                                   |
| ---------- | ----------------------------------------- |
| `idle`     | No active intent                          |
| `active`   | One intent is open                        |
| `conflict` | Multiple candidate checkpoints exist      |

### Intent lifecycle

```
open → done
```

An intent is `open` when created by `start`, and becomes `done` when closed by `done`.

## 3. Storage Layout

```
.intent/
  config.json           # {"schema_version": "0.2"}
  state.json            # workspace state
  intents/
    intent-001.json
    intent-002.json
  checkpoints/
    cp-001.json
    cp-002.json
```

### state.json

```json
{
  "schema_version": "0.2",
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
  "result": { "version": "0.2.4" }
}
```

### init

Initialize Intent in the current Git repository. Creates `.intent/` directory with `config.json`, `state.json`, and subdirectories for intents and checkpoints.

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
    "schema_version": "0.2",
    "created_at": "2026-03-17T10:00:00Z",
    "updated_at": "2026-03-17T10:00:00Z",
    "title": "Fix the login timeout bug",
    "status": "open"
  },
  "warnings": []
}
```

Fails if an intent is already open. Close it first with `itt done`.

### snap

Record a checkpoint against the active intent. By default the checkpoint is `adopted`.

```
itt snap "Increase timeout to 30s" -m "Default 5s was too short for slow networks"
```

Use `--candidate` to record without adopting — useful when exploring alternatives:

```
itt snap "Try connection pooling" --candidate
```

### adopt

Adopt a candidate checkpoint. If there is exactly one candidate, no ID is needed.

```
itt adopt
itt adopt cp-003
itt adopt cp-003 -m "Pooling approach benchmarked 2x faster"
```

Fails if no candidates exist, or if multiple candidates exist and no ID is specified (the error will list the candidates).

### revert

Revert the latest adopted checkpoint within the active intent.

```
itt revert
itt revert -m "Approach caused regression in tests"
```

Changes the checkpoint status from `adopted` to `reverted`. Fails if no adopted checkpoint exists.

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
  "schema_version": "0.2",
  "workspace_status": "active",
  "intent": { "id": "intent-001", "title": "Fix the login timeout bug", "status": "open" },
  "latest_checkpoint": { "id": "cp-002", "title": "Increase timeout to 30s", "status": "adopted" },
  "candidate_checkpoints": [],
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

When no intent is active, `intent`, `latest_checkpoint`, and `candidate_checkpoints` are `null`/`[]`, and `suggested_next_action` recommends `itt start`.

### list

List all objects of a given type, sorted newest first.

```
itt list intent
itt list checkpoint
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

Show a single object by its ID. The object type is inferred from the ID prefix (`intent-` or `cp-`).

```
itt show intent-001
itt show cp-003
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
| `STATE_CONFLICT`    | Intent already open, checkpoint not a candidate, etc. |
| `OBJECT_NOT_FOUND`  | ID does not resolve to a stored object           |
| `INVALID_INPUT`     | Bad arguments or conflicting flags               |

## 8. Git Context

Each checkpoint records a `git` object:

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
- Checkpoints: `cp-001`, `cp-002`, ...

IDs are zero-padded to 3 digits, auto-incremented per type.
