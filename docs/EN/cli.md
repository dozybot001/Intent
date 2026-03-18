# Intent CLI Design Document

English | [中文](../CN/cli.md)

Schema version: **0.6**

Intent CLI is an object-centric, agent-first CLI. The system models only three types of objects: **intent**, **snap**, and **decision**.

Design principles:

- `decision` is the highest-level object, representing crystallized long-term decisions that can link to multiple intents
- `intent` is a goal the agent identified from a user query, linking to multiple decisions and snaps
- `snap` is a snapshot of one user-agent interaction, recording query, a brief summary of what the agent did, and user feedback
- Schema version is a workspace-level config, stored only in `config.json`
- All objects share `id`, `object`, `created_at`, `title`, `status`
- All objects no longer have `updated_at`
- Creating a `decision` auto-attaches all `active` intents
- Creating an `intent` auto-attaches all `active` decisions
- Multiple intents can be active simultaneously

## 1. Object Model

### 1.1 Shared Fields

| Field | Type | Description |
| --- | --- | --- |
| `id` | string | Object ID, e.g. `intent-001` |
| `object` | string | Object type: `intent`, `snap`, `decision` |
| `created_at` | string | ISO 8601 UTC |
| `title` | string | Object title |
| `status` | string | Object status, enum varies by type |

### 1.2 Intent

An intent represents what the user wants to solve. It comes from the agent's intent recognition of a user query, not from the user "manually opening a task."

| Field | Type | Description |
| --- | --- | --- |
| Shared fields | - | See above |
| `source_query` | string | Original user query that triggered this intent |
| `rationale` | string | Why this goal matters; filled when the user's query contains explanatory context, otherwise empty |
| `decision_ids` | string[] | Linked decision IDs, preserving historical relationships |
| `snap_ids` | string[] | Currently linked snap IDs |

Intent states:

- `active`: Currently valid and being progressed
- `suspend`: Temporarily paused, not included in new decision auto-attachment
- `done`: This intent has been completed

### 1.3 Snap

A snap represents one complete user-agent interaction snapshot. It belongs to one intent and records what was asked, what the agent did, and how the user responded.

| Field | Type | Description |
| --- | --- | --- |
| Shared fields | - | See above |
| `intent_id` | string | Parent intent ID |
| `query` | string | Original user query for this interaction |
| `rationale` | string | Why this approach was chosen; filled when the user explains reasoning, otherwise empty |
| `summary` | string | Brief summary of what the agent did; not a detailed operation log |
| `feedback` | string | User feedback; empty string `""` if user moved on to another topic |

`summary` is a summary field, not a step-by-step execution log. It does not require storing complete commands, file-level operation details, or terminal output.

Snap states:

- `active`: This interaction record is currently valid
- `reverted`: This interaction was explicitly reverted later

### 1.4 Decision

A decision represents a crystallized long-term decision. It is the highest-level object, effective across multiple intents.

| Field | Type | Description |
| --- | --- | --- |
| Shared fields | - | See above |
| `rationale` | string | Why this long-term decision was made |
| `intent_ids` | string[] | Linked intent IDs, preserving historical relationships |

Decision states:

- `active`: Currently in effect, auto-attaches to new intents
- `deprecated`: This decision has been retired; history preserved but no longer auto-attaches to new intents

## 2. Relationship Rules

All attachment relationships must be persisted bidirectionally.

- When `decision ↔ intent` relationship changes, both `decision.intent_ids` and `intent.decision_ids` must be updated
- When `intent ↔ snap` relationship changes, both `snap.intent_id` and `intent.snap_ids` must be updated
- Object files themselves are the single source of truth; no separate state index files are maintained
- `decision ↔ intent` relationships preserve history by default; `decision deprecated` does not remove existing links, only stops future auto-attachment

### 2.1 Decision → Intent

- One decision can link to multiple intents
- One intent can also link to multiple decisions simultaneously
- When creating a decision, the system auto-adds all `active` intents to `intent_ids`
- When creating an intent, the system auto-adds all `active` decisions to `decision_ids`
- When reactivating a suspended intent to `active`, it should catch up on all current `active` decisions
- Manual attachment must also update both sides

### 2.2 Intent → Snap

- One intent can link to multiple snaps
- One snap can only belong to one intent
- Creating a snap requires explicitly specifying `intent_id`
- Creating a snap must simultaneously write `snap.intent_id` and the corresponding `intent.snap_ids`
- Only `active` intents can accept new snaps

## 3. State Model

Intent CLI no longer maintains a single workspace active intent state, but manages object collections.

### 3.1 Common State Names

- `active`: Object is currently valid

### 3.2 Type-Specific States

- intent: `suspend`, `done`
- snap: `reverted`
- decision: `deprecated`

### 3.3 Valid State Transitions

Only the following transitions are allowed; all others return `STATE_CONFLICT`:

**Intent:**

- `active` → `suspend` (pause)
- `active` → `done` (complete)
- `suspend` → `active` (resume, triggers catch-up of active decisions)

`done` is terminal and cannot be reversed. To resume the same problem, create a new intent.

**Snap:**

- `active` → `reverted` (revert)

`reverted` is terminal and cannot be reversed.

**Decision:**

- `active` → `deprecated` (retire)

`deprecated` is terminal and cannot be reversed. To reinstate the same decision, create a new decision with rationale.

## 4. Storage Structure

```text
.intent/
  config.json
  intents/
    intent-001.json
  snaps/
    snap-001.json
  decisions/
    decision-001.json
```

### 4.1 config.json

```json
{
  "schema_version": "0.6"
}
```

## 5. Command Design

All commands output JSON. The CLI uses object-subcommand style, no longer using scattered verbs like `start`, `resume`, `decide` as core entry points.

### 5.1 Global Commands

#### version

```bash
itt version
```

#### init

Initialize the `.intent/` directory in the current Git repository.

```bash
itt init
```

#### inspect

Output the current object graph snapshot, rather than a single active intent view. `inspect` computes results in real-time by scanning object files.

`recent_snaps` returns the 10 most recent snaps globally (sorted by `created_at` descending), regardless of intent affiliation or status.

```bash
itt inspect
```

Example:

```json
{
  "ok": true,
  "schema_version": "0.6",
  "active_intents": [
    {
      "id": "intent-001",
      "title": "Fix the login timeout bug",
      "status": "active",
      "decision_ids": ["decision-001"],
      "latest_snap_id": "snap-002"
    }
  ],
  "suspend_intents": [],
  "active_decisions": [
    {
      "id": "decision-001",
      "title": "Timeout must stay configurable",
      "status": "active",
      "intent_ids": ["intent-001", "intent-003"]
    }
  ],
  "recent_snaps": [
    {
      "id": "snap-002",
      "title": "Raise timeout to 30s",
      "intent_id": "intent-001",
      "status": "active",
      "summary": "Updated timeout config and ran the login test",
      "feedback": ""
    }
  ],
  "warnings": []
}
```

### 5.2 Intent Commands

#### create

Create a new intent. Typically called by the agent after recognizing a new goal in the user query.

```bash
itt intent create "Fix the login timeout bug" \
  --query "why does login timeout after 5s?" \
  --rationale "users on slow networks get logged out mid-session"
```

Behavior:

- New object status is `active`
- Auto-attaches all `active` decisions
- New attachment relationships must be persisted bidirectionally to intent and decision

#### list

```bash
itt intent list
itt intent list --status active
itt intent list --status suspend
itt intent list --status done
```

#### show

```bash
itt intent show intent-001
```

#### activate

Reactivate a `suspend` intent to `active`.

```bash
itt intent activate intent-001
```

Behavior:

- Catches up all current `active` decisions to the intent
- New attachment relationships must be persisted bidirectionally to intent and decision

#### suspend

```bash
itt intent suspend intent-001
```

#### done

```bash
itt intent done intent-001
```

### 5.3 Snap Commands

#### create

Record one interaction snapshot under a specified intent.

```bash
itt snap create "Raise timeout to 30s" \
  --intent intent-001 \
  --query "login timeout still fails on slow networks" \
  --rationale "30s covers 99th-percentile latency without hurting UX" \
  --summary "updated timeout config and ran the login test" \
  --feedback "works in staging"
```

Behavior:

- New object status defaults to `active`
- Simultaneously writes `snap.intent_id` and the target intent's `snap_ids`
- `--feedback` is optional, defaults to `""`; if the user gives no feedback and moves on, keep the default

#### list

```bash
itt snap list
itt snap list --intent intent-001
itt snap list --status active
```

#### show

```bash
itt snap show snap-001
```

#### feedback

Add or overwrite user feedback. Each snap keeps only the latest feedback value.

```bash
itt snap feedback snap-001 "timeout issue is fixed"
```

#### revert

Mark an interaction as `reverted`.

```bash
itt snap revert snap-001
```

### 5.4 Decision Commands

#### create

Create a new long-term decision.

```bash
itt decision create "Timeout must stay configurable" \
  --rationale "Different deployments have different latency envelopes"
```

Behavior:

- New object status is `active`
- Auto-attaches all `active` intents
- New attachment relationships must be persisted bidirectionally to decision and intent

#### list

```bash
itt decision list
itt decision list --status active
itt decision list --status deprecated
```

#### show

```bash
itt decision show decision-001
```

#### deprecate

```bash
itt decision deprecate decision-001
```

Behavior:

- Changes decision status to `deprecated`
- Preserves existing `decision.intent_ids` and corresponding `intent.decision_ids`
- `deprecated` decisions no longer auto-attach to new intents

#### attach

Manually attach a decision to an intent, for backfilling historical relationships.

```bash
itt decision attach decision-001 --intent intent-002
```

Behavior:

- Must simultaneously update `decision.intent_ids` and `intent.decision_ids`

## 6. JSON Output Contract

### 6.1 Success

Except for `inspect`, success responses follow this format:

```json
{
  "ok": true,
  "action": "<command-name>",
  "result": { ... },
  "warnings": []
}
```

### 6.2 Error

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

### 6.3 Warnings

`warnings` is a string array for non-blocking hints. Possible scenarios:

- No `active` decisions to attach when creating an intent
- No `active` intents to attach when creating a decision
- `inspect` finds orphan snaps (their `intent_id` points to a missing intent file)
- Unrecognized fields in object files (forward-compatibility hint)

Warnings do not affect `ok: true`; they are informational for the caller.

## 7. Error Codes

| Code | Trigger scenario |
| --- | --- |
| `NOT_INITIALIZED` | `.intent/` does not exist |
| `ALREADY_EXISTS` | `.intent/` already exists when running `init` |
| `GIT_STATE_INVALID` | Not inside a Git worktree |
| `STATE_CONFLICT` | Illegal state transition, e.g. `activate` on a `done` intent |
| `OBJECT_NOT_FOUND` | ID does not match any object |
| `INVALID_INPUT` | Parameter errors, missing object ID, missing `--intent`, etc. |

## 8. ID Format

- Intent: `intent-001`, `intent-002`, ...
- Snap: `snap-001`, `snap-002`, ...
- Decision: `decision-001`, `decision-002`, ...

IDs are zero-padded to 3 digits, auto-incremented per type. New ID = current max number for that type + 1. Deleted numbers are not reused.

## 9. Design Constraints

### 9.1 Object Immutability

After creation, content fields (title, summary, rationale, source_query, etc.) have no update command.

This is intentional: semantic history should be append-only records. If a title or summary was written incorrectly, the right approach is to correct it in a subsequent snap, not rewrite history. The only field that allows post-hoc changes is `snap.feedback` (overwritten via the `snap feedback` command), because feedback is inherently delayed.

### 9.2 Relationships Only Grow

`decision attach` is for backfilling relationships, but there is no `detach` command.

Relationships record the fact that "this decision has/is influencing this intent." Removing a relationship would erase history. If a decision no longer applies, `deprecate` it — existing links are preserved; only future auto-attachment stops.

### 9.3 `snap feedback` Uses Overwrite Semantics

`snap feedback` performs a full overwrite of the `feedback` field, not an append. Each snap keeps only the latest feedback.
