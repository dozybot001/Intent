English | [简体中文](../CN/cli.md)

# Unified Intent CLI Specification

Purpose: serve as the single source of truth for Intent CLI. This document defines the project boundary, command semantics, object model, state machine, JSON contract, error model, and implementation order for the initial CLI release.

## What This Document Answers

- what the first version of Intent CLI should and should not do
- how the front-page commands, object model, and human path should be organized
- how the `.intent/` local object layer, `state.json`, and Git linkage should be defined
- how `status --json` / `inspect --json`, write-command response shapes, error codes, and exit codes should be frozen

## What This Document Does Not Answer

- why the agent era needs Intent: see [Vision and problem definition](vision.md)
- longer-term remote collaboration and platform direction
- later concerns such as UI, Hub, or sync protocols

## Boundary with Other Documents

- terminology is defined in [Glossary](glossary.md)
- why Intent is needed, and the long-term relationship among Intent CLI / Skill / IntHub, is defined in [Vision and problem definition](vision.md)
- CLI design, command semantics, and implementation contract are defined here

## 1. Design Goals

Intent CLI is a semantic history tool built on top of Git for recording:

- what problem is currently being worked on
- which candidate outcomes were formed
- what was formally adopted in the end
- how that adoption can be reverted when necessary

The first version is not trying to become a broad process platform. It is trying to make the minimum local loop work:

`init -> start -> snap -> adopt -> log`

This path must satisfy three things at the same time:

- for humans: easy to understand and easy to remember
- for developers: a clear, implementable, Git-trackable local object layer
- for agents: stable objects, states, JSON, and errors that can be consumed reliably

Git prerequisites:

- in v1, Intent only works inside a Git worktree
- a non-Git directory is not an "uninitialized Intent repo"; it is an invalid runtime environment
- in a non-Git directory, the user should run `git init` first or enter an existing Git repository

## 2. v1 Boundary

### 2.0 How to Read This Section

This section defines the public commitment for V1, not every idea that may exist in the future.

Interpretation rules:

- anything under "must cover" belongs to the V1 scope
- anything under "can be deferred" is not required for the first delivery
- anything under "not in the first version" should not keep expanding in V1 discussion

### 2.1 Commands the First Version Must Cover

- `itt init`
- `itt start`
- `itt status`
- `itt snap`
- `itt adopt`
- `itt log`
- `itt inspect`
- `itt checkpoint select`
- `itt revert`

### 2.2 Core Objects for the First Version

- `intent`
- `checkpoint`
- `adoption`
- `state`

### 2.3 Objects That Can Be Deferred

- `run`
- `decision`

Requirements:

- the directories can already exist
- `inspect --json` may return `null` or empty lists for them
- they must not interfere with the minimum loop of `init -> start -> snap -> adopt -> log`

### 2.4 What the First Version Does Not Do

- replace Git's version-control role
- store all raw conversation history
- introduce remote sync commands
- put more objects on the front-page path
- let the platform narrative outweigh the local contract in the first release
- expand the CLI into a full object browser
- freeze `log --json`, complex filters, pagination, or full object-browser semantics in V1
- support initializing or running Intent outside a Git repository

## 3. Front-Page Path

The README front page should expose only these six commands:

```bash
itt init
itt start
itt status
itt snap
itt adopt
itt log
```

Minimal example:

```bash
itt init
itt start "Reduce onboarding confusion"

# explore and change code with agent...

itt snap "Landing page candidate B"
git add .
git commit -m "refine onboarding landing layout"
itt adopt -m "Adopt progressive disclosure layout"
itt log
```

After running this flow, the user should immediately understand:

- Git is still managing the code normally
- Intent records higher-level adoption history
- `start -> snap -> adopt` is more important to remember than the object names themselves

## 4. Object Model and Exposure Order

The first version keeps the five-object model, but onboarding exposes only the minimum actions needed.

| Object | Question It Answers | On the Front Page? | Surface Command | Notes |
| --- | --- | --- | --- | --- |
| `intent` | what problem is currently being worked on | yes | `itt start` | the default semantic context |
| `checkpoint` | which candidate outcomes currently exist | yes, but exposed through `snap` | `itt snap` | the direct prerequisite for adoption |
| `adoption` | which candidate was formally adopted | yes | `itt adopt` | the headline object in semantic history |
| `decision` | why this and not that | no | `itt decide` | appears only when a tradeoff is worth preserving |
| `run` | what happened in one agent execution round | no | `itt run start/end` | more agent / automation / telemetry oriented |

Design principles:

- the object model may be complete
- the front page should expose only the minimum actions
- `adopt` is the central system action
- advanced objects appear later

## 5. Command System

### 5.1 Surface CLI

Short commands for frequent human use:

```bash
itt init
itt start
itt status
itt snap
itt adopt
itt log
itt revert
```

Commands that appear as needed:

```bash
itt inspect
itt checkpoint select
itt decide
itt run start
itt run end
```

The first version does not provide an `itt new` alias.

### 5.2 Canonical CLI

What V1 needs to freeze is the semantic action vocabulary, not the full set of object subcommands all at once.

The only canonical actions that must exist in the first version are:

```bash
itt intent create

itt checkpoint create
itt checkpoint select

itt adoption create
itt adoption revert

itt run start
itt run end

itt inspect
```

These commands exist to:

- serve as the naming baseline for internal handlers and machine semantics
- provide a stable mapping target for the surface CLI
- reserve consistent object space for later `list/show/switch` expansion

The public command promise for V1 still stops here. The following object commands remain reserved directions rather than front-page commitments:

```bash
itt intent list
itt intent show
itt intent switch

itt checkpoint list
itt checkpoint show

itt adoption list
itt adoption show

itt decision create
itt decision list
itt decision show

itt run start
itt run end
itt run list
itt run show
```

Implementation principles:

- internal handlers should be organized around canonical actions first
- the surface CLI should mainly prefill arguments and wrap UX
- even if a few `list/show` helper commands exist in the implementation, they should not overshadow the `init -> start -> snap -> adopt -> log` path
- V1 does not require reserved object commands to become front-page commitments or long-term compatibility promises

Current helper-command note:

- when `show` helpers exist, they may support reserved selectors such as `@active`, `@current`, and `@latest` for machine-friendly reads
- when write commands accept `--checkpoint` or `--adoption`, they may also accept the matching selectors such as `@current` and `@latest` to avoid unnecessary id lookups

### 5.3 Mapping Between Surface and Canonical Commands

| Surface CLI | Canonical Semantics |
| --- | --- |
| `itt start` | `itt intent create --activate` |
| `itt snap` | `itt checkpoint create --select` |
| `itt adopt` | `itt adoption create` |
| `itt revert` | `itt adoption revert` |

## 6. Current Object Mechanism

Intent CLI keeps the current-object philosophy, but it primarily serves human UX rather than being the main automation contract.

### 6.1 active intent

The system maintains one active intent as the default semantic context.

### 6.2 current checkpoint

The system maintains one current checkpoint as the default candidate object.

When a new checkpoint is created:

- it automatically becomes the current checkpoint

When switching explicitly:

```bash
itt checkpoint select cp-012
```

### 6.3 Default Behavior Rules

Human mode:

- `itt start` creates and switches to the active intent
- `itt snap` creates and switches to the current checkpoint
- `itt adopt` adopts the current checkpoint by default
- `itt status` should organize information around the current object first

Agent mode:

- prefer passing explicit `intent id` / `checkpoint id`
- the current object may be read, but should not be treated as a strong contract
- recommended flow: run `itt inspect --json` before any write operation
- when the write target is simply "the current checkpoint" or "the latest adoption", prefer `--checkpoint @current` and `--adoption @latest`

### 6.4 Conflict Handling

If multiple unadopted candidates exist and the default object is not clear:

- `itt adopt` must not guess
- it should return `STATE_CONFLICT`
- it should return candidate ids in the error details
- it should return a concrete next action such as `itt checkpoint select cp-002`

## 7. Local Directory Layout

The first-version directory layout is fixed as:

```text
.intent/
  config.json
  state.json
  intents/
  checkpoints/
  adoptions/
  runs/
  decisions/
```

### 7.1 Directory Responsibilities

| Path | Responsibility |
| --- | --- |
| `.intent/config.json` | repository-level configuration, not runtime context |
| `.intent/state.json` | active workspace state and default object references |
| `.intent/intents/` | intent object files |
| `.intent/checkpoints/` | checkpoint object files |
| `.intent/adoptions/` | adoption object files |
| `.intent/runs/` | run object files |
| `.intent/decisions/` | decision object files; may be empty in V1 |

### 7.2 File Organization Principles

- one object maps to one JSON file
- filenames default to object ids, such as `intent-001.json`
- do not use one large database file
- V1 does not depend on sqlite
- file contents must be readable, Git-trackable, and consumable by other tools

### 7.3 `config.json` Contract

At minimum, the first-version `config.json` contains:

```json
{
  "schema_version": "0.1",
  "git": {
    "strict_adoption": false
  }
}
```

Rules:

- `config.json` stores only repository-level configuration, not runtime context
- V1 freezes only `schema_version` and `git.strict_adoption`
- other configuration items are outside the first-version contract

## 8. Naming and ID Rules

### 8.1 ID Prefixes

| Object | Prefix Example |
| --- | --- |
| intent | `intent-001` |
| checkpoint | `cp-001` |
| adoption | `adopt-001` |
| run | `run-001` |
| decision | `decision-001` |

### 8.2 Generation Rules

- V1 uses monotonically increasing per-repository counters
- each object type increments independently
- deleted objects do not cause old ids to be reused
- assigned ids must stay stable across executions

### 8.3 Display Names and Titles Are Separate

- machines identify objects by `id`
- human-facing displays should show both `id` and `title`

Example:

```text
intent-003  Reduce onboarding confusion
cp-012      Landing page candidate B
```

## 9. Shared Object Schema

All objects must contain at least these fields:

```json
{
  "id": "...",
  "object": "intent|checkpoint|adoption|run|decision",
  "schema_version": "0.1",
  "created_at": "2026-03-15T14:00:00Z",
  "updated_at": "2026-03-15T14:00:00Z",
  "title": "...",
  "summary": "...",
  "status": "...",
  "intent_id": "intent-001",
  "run_id": null,
  "git": {
    "branch": "main",
    "head": "a91c3d2",
    "working_tree": "clean",
    "linkage_quality": "stable_commit"
  },
  "metadata": {}
}
```

Field definitions:

| Field | Meaning |
| --- | --- |
| `id` | unique object identifier |
| `object` | object type string; cannot be omitted |
| `schema_version` | fixed to `0.1` in the first version |
| `created_at` / `updated_at` | RFC3339 UTC timestamps |
| `title` | short human-facing title |
| `summary` | optional summary; empty string is allowed in V1 |
| `status` | enum value; free text is not allowed |
| `intent_id` | all objects except intent itself must point to their owning intent |
| `run_id` | may be `null` in V1 |
| `git` | Git linkage context |
| `metadata` | extension field; V1 core logic must not depend on it |

## 10. Object-Level Contracts

### 10.1 Intent

```json
{
  "id": "intent-001",
  "object": "intent",
  "schema_version": "0.1",
  "created_at": "2026-03-15T14:00:00Z",
  "updated_at": "2026-03-15T14:00:00Z",
  "title": "Reduce onboarding confusion",
  "summary": "Improve first-run understanding and reduce drop-off.",
  "status": "active",
  "parent_intent_id": null,
  "tags": [],
  "latest_checkpoint_id": "cp-003",
  "latest_adoption_id": "adopt-002",
  "metadata": {}
}
```

`status` enum:

- `active`
- `paused`
- `completed`
- `archived`

Constraints:

- a new intent created by `itt start` defaults to `active`
- `state.active_intent_id` must switch to it
- by default, V1 assumes only one active intent at a time as the current workspace context

### 10.2 Checkpoint

```json
{
  "id": "cp-001",
  "object": "checkpoint",
  "schema_version": "0.1",
  "created_at": "2026-03-15T14:10:00Z",
  "updated_at": "2026-03-15T14:10:00Z",
  "title": "Landing page candidate B",
  "summary": "Progressive disclosure layout with shorter hero copy.",
  "status": "candidate",
  "intent_id": "intent-001",
  "run_id": null,
  "ordinal": 1,
  "selected": true,
  "adopted": false,
  "adopted_by": null,
  "git": {
    "branch": "main",
    "head": "a91c3d2",
    "working_tree": "dirty",
    "linkage_quality": "working_tree_context"
  },
  "metadata": {}
}
```

`status` enum:

- `candidate`
- `adopted`
- `superseded`
- `reverted`

Constraints:

- a checkpoint created by `itt snap` defaults to `candidate`
- a new checkpoint automatically becomes `state.current_checkpoint_id`
- multiple `candidate` checkpoints may exist under the same intent
- only a checkpoint with `selected=true` can serve as the human default current checkpoint
- after a successful adoption, the checkpoint is updated to:
  `status=adopted`, `adopted=true`, `adopted_by=<adoption_id>`, `selected=false`
- after a successful revert, the reverted checkpoint is updated to:
  `status=reverted`, `adopted=false`, `adopted_by=null`, `selected=false`
- V1 does not automatically write `superseded`; that status is reserved for later versions or explicit migration logic

### 10.3 Adoption

```json
{
  "id": "adopt-001",
  "object": "adoption",
  "schema_version": "0.1",
  "created_at": "2026-03-15T14:20:00Z",
  "updated_at": "2026-03-15T14:20:00Z",
  "title": "Adopt progressive disclosure layout",
  "summary": "Choose candidate B as the official direction for onboarding.",
  "status": "active",
  "intent_id": "intent-001",
  "run_id": null,
  "checkpoint_id": "cp-001",
  "rationale": "Lower cognitive load and clearer first action.",
  "reverts_adoption_id": null,
  "git": {
    "branch": "main",
    "head": "a91c3d2",
    "working_tree": "clean",
    "linkage_quality": "stable_commit"
  },
  "metadata": {}
}
```

`status` enum:

- `active`
- `reverted`

Constraints:

- by default, a checkpoint can have at most one active adoption in V1
- `itt revert` reuses the adoption object schema rather than introducing a separate revert object
- a revert record uses the same schema, and `reverts_adoption_id` must point to the adoption being reverted
- a revert record reuses the original adoption's `intent_id` and `checkpoint_id`
- the new revert record is created with `status=active`
- the reverted adoption is marked `reverted`
- adoption does not modify Git directly; it records Git linkage state only

Example revert record:

```json
{
  "id": "adopt-002",
  "object": "adoption",
  "schema_version": "0.1",
  "created_at": "2026-03-15T14:30:00Z",
  "updated_at": "2026-03-15T14:30:00Z",
  "title": "Revert progressive disclosure layout",
  "summary": "Revert the previously adopted onboarding direction.",
  "status": "active",
  "intent_id": "intent-001",
  "run_id": null,
  "checkpoint_id": "cp-001",
  "rationale": "Testing showed higher confusion than expected.",
  "reverts_adoption_id": "adopt-001",
  "git": {
    "branch": "main",
    "head": "b02d441",
    "working_tree": "clean",
    "linkage_quality": "stable_commit"
  },
  "metadata": {}
}
```

### 10.4 Run

```json
{
  "id": "run-001",
  "object": "run",
  "schema_version": "0.1",
  "created_at": "2026-03-15T14:05:00Z",
  "updated_at": "2026-03-15T14:25:00Z",
  "title": "Agent exploration",
  "summary": "",
  "status": "active",
  "intent_id": "intent-001",
  "run_id": null,
  "git": {
    "branch": "main",
    "head": "a91c3d2",
    "working_tree": "clean",
    "linkage_quality": "stable_commit"
  },
  "metadata": {}
}
```

`status` enum:

- `active`
- `completed`

Constraints:

- `itt run start` requires an active intent
- `itt run start` creates a new run object and sets `state.active_run_id`
- only one active run may exist at a time in V1
- `itt run end` marks the active run as `completed`
- `itt run end` clears `state.active_run_id`
- checkpoints and adoptions created while a run is active should record that `run_id`

### 10.5 Decision

```json
{
  "id": "decision-001",
  "object": "decision",
  "schema_version": "0.1",
  "created_at": "2026-03-15T14:40:00Z",
  "updated_at": "2026-03-15T14:40:00Z",
  "title": "Prefer progressive disclosure over dense hero copy",
  "summary": "",
  "status": "active",
  "intent_id": "intent-001",
  "run_id": null,
  "adoption_id": "adopt-001",
  "checkpoint_id": "cp-001",
  "rationale": "Lower cognitive load and make the first action clearer.",
  "git": {
    "branch": "main",
    "head": "a91c3d2",
    "working_tree": "clean",
    "linkage_quality": "stable_commit"
  },
  "metadata": {}
}
```

`status` enum:

- `active`

Constraints:

- `decision` records a tradeoff or principle worth preserving beyond an adoption title
- `itt decide` / `itt decision create` requires an active intent
- `decision` may optionally point to an adoption and its checkpoint
- if no explicit adoption is passed, the latest adoption under the active intent may be linked when available
- if no adoption is available, the decision may still be recorded with `adoption_id=null` and `checkpoint_id=null`
- creating a decision does not change `workspace_status`

## 11. `state.json` Contract

At minimum, the first-version `state.json` contains:

```json
{
  "schema_version": "0.1",
  "mode": "human",
  "active_intent_id": "intent-001",
  "active_run_id": null,
  "current_checkpoint_id": "cp-001",
  "last_adoption_id": null,
  "workspace_status": "candidate_ready",
  "updated_at": "2026-03-15T14:20:00Z"
}
```

Field definitions:

| Field | Meaning |
| --- | --- |
| `mode` | `human` / `agent` / `ci` |
| `active_intent_id` | current default intent |
| `active_run_id` | current run; may be `null` in V1 |
| `current_checkpoint_id` | current default checkpoint |
| `last_adoption_id` | most recent adoption |
| `workspace_status` | aggregate workspace status |
| `updated_at` | most recent refresh time |

`workspace_status` enum:

- `idle`
- `blocked_no_active_intent`
- `intent_active`
- `candidate_ready`
- `adoption_recorded`
- `conflict_multiple_candidates`

Derivation rules:

| Status | Trigger Condition |
| --- | --- |
| `idle` | no intent has been created yet, or the state has not been fully initialized |
| `blocked_no_active_intent` | there is no current `active_intent_id` |
| `intent_active` | there is an active intent, but no current checkpoint |
| `candidate_ready` | a current checkpoint exists and has not yet been adopted, making it a recommended adoption target |
| `adoption_recorded` | the most recent action was an adoption or revert record, and no higher-priority conflict exists |
| `conflict_multiple_candidates` | multiple unadopted candidates exist and there is no unique `selected=true` current checkpoint |

Update principles:

- every successful write command must refresh `updated_at`
- `state.json` is a current snapshot, not a history log
- historical events must live in object files rather than only in `state.json`

## 12. Core Write-Command Behavior Rules

### 12.1 `itt init`

Role: initialize the `.intent/` metadata layer in the current Git repository.

Requirements:

- the current directory must be inside a Git worktree
- create `.intent/`
- create the required subdirectories
- create `config.json`
- create `state.json`
- if initialization already exists, do not overwrite by default and return a recognizable error
- if the current directory is not inside a Git worktree, return `GIT_STATE_INVALID`

Git prerequisite rules:

- all V1 commands require the current directory to be inside a Git worktree
- Git environment validation happens before `.intent/` initialization validation
- therefore, a non-Git directory does not return `NOT_INITIALIZED`; it always returns `GIT_STATE_INVALID`

### 12.2 `itt start <title>`

Role: begin work on a problem and create a new active intent.

Example:

```bash
itt start "Reduce onboarding confusion"
```

Canonical form:

```bash
itt intent create --title "Reduce onboarding confusion"
```

Rules:

- create a new intent object
- set it as `active_intent_id`
- clear `current_checkpoint_id`
- set `workspace_status=intent_active`
- by default, every invocation creates a new intent in V1; it is not idempotent

### 12.3 `itt snap <title>`

Role: surface-level fast path for saving a checkpoint.

Example:

```bash
itt snap "Landing page candidate B"
```

Canonical form:

```bash
itt checkpoint create --title "Landing page candidate B"
```

Rules:

- requires `active_intent_id` to exist
- create a checkpoint object
- automatically make it `current_checkpoint_id`
- default to `selected=true`
- if an old current checkpoint exists, that old checkpoint becomes `selected=false`
- set `workspace_status=candidate_ready`

### 12.4 `itt checkpoint select <id>`

Rules:

- require the checkpoint to exist and belong to the active intent
- set the target checkpoint to `selected=true`
- set other checkpoints under the same intent to `selected=false`
- update `current_checkpoint_id`

### 12.5 `itt adopt`

Role: formally adopt a checkpoint.

Recommended fast path:

```bash
itt adopt -m "Adopt progressive disclosure layout"
```

Explicit path:

```bash
itt adopt --checkpoint cp-012 -m "Adopt progressive disclosure layout"
```

Canonical form:

```bash
itt adoption create \
  --checkpoint cp-012 \
  --title "Adopt progressive disclosure layout"
```

Rules:

- default to `current_checkpoint_id`
- if there is no current checkpoint, return `STATE_CONFLICT`
- if multiple candidates exist and the current object is not clear, return `STATE_CONFLICT`
- on success, create an adoption object
- update checkpoint adoption fields to:
  `status=adopted`, `adopted=true`, `adopted_by=<adoption_id>`, `selected=false`
- clear `current_checkpoint_id`
- update `last_adoption_id`
- set `workspace_status=adoption_recorded`
- successful output should emphasize that a candidate was adopted, not that an adoption object was created

### 12.6 `itt revert`

Rules:

- by default, revert the most recent active adoption
- if no active adoption exists, return an object/state error
- create a new adoption object as a revert record, with `reverts_adoption_id`
- the new revert record inherits the target adoption's `intent_id` and `checkpoint_id`
- the new revert record uses `status=active`
- the reverted adoption is marked `reverted`
- the reverted checkpoint is updated to:
  `status=reverted`, `adopted=false`, `adopted_by=null`, `selected=false`
- `current_checkpoint_id` remains `null`
- update `last_adoption_id`
- set `workspace_status=adoption_recorded`
- checkpoint state preserves the historical fact and does not automatically return to `candidate`

### 12.7 `itt run start`

Rules:

- requires an active intent
- creates a run object with `status=active`
- sets `state.active_run_id`
- does not change `workspace_status`
- if an active run already exists, return `STATE_CONFLICT`

### 12.8 `itt run end`

Rules:

- requires an active run
- marks the run object as `status=completed`
- clears `state.active_run_id`
- does not change `workspace_status`
- if no active run exists, return an object/state error

### 12.9 `itt decide`

Rules:

- requires an active intent
- creates a decision object
- if `--adoption <id>` is passed, the adoption must belong to the active intent
- if no explicit adoption is passed, the latest adoption for the active intent may be linked automatically
- a decision may be created without an adoption link
- does not change `workspace_status`

### 12.10 `itt status`

Role: show the current semantic workspace state to humans and recommend the next action.

It must answer these four things first:

- which intent is currently active
- what the default current object is
- what the overall workspace state is
- what the most reasonable next action is

`status` is not a semi-structured form of `inspect`. It is a human entry point first.

V1 boundary:

- default text output focuses only on the present, not historical lists
- output should be organized around four blocks: active intent, current checkpoint, workspace status, next action
- if a latest adoption exists, it may appear as a supplementary block
- `status --json` returns only a lightweight workspace summary, not `pending_items` or object arrays
- `status` does not enumerate objects, replay timelines, or export complete context

### 12.11 `itt inspect`

Role: return stable, complete, machine-consumable semantic context.

Design position:

- `inspect` is the standard entry point for agents, Skills, IDEs, and automation
- the goal is not "pretty"; it is "stable"
- missing objects should return `null`, not silently disappear from the payload

V1 boundary:

- only `inspect --json` has a frozen stable contract
- `inspect` returns the current workspace snapshot, not a full semantic history dump
- derived information such as `pending_items` and `suggested_next_actions` is allowed
- it does not return full lists of intents / checkpoints / adoptions
- it does not replace the timeline role of `log`

### 12.12 `itt log`

Role: let humans inspect semantic history, especially adoption history.

V1 boundary:

- `log` is primarily human-readable text
- default order is reverse chronological adoption / revert timeline
- each record must show at least: time, adoption id, title, checkpoint reference, intent reference, and git head
- checkpoint and intent titles may be included to help humans quickly understand what was adopted
- linked decisions may appear beneath the relevant adoption or revert record as supplementary context
- if decisions exist without an adoption link, `log` may show them in a separate standalone section
- if the repo contains no adoptions or decisions yet, return a clear empty state with a recommended next step
- it must not collapse into a list of object files
- V1 does not define `log --json`
- V1 does not add `log --intent`, `log --checkpoint`, pagination, or complex filters
- see the output-text baseline below for human examples

## 13. Git Linkage Contract

### 13.1 Required Git Fields

```json
{
  "git": {
    "branch": "main",
    "head": "a91c3d2",
    "working_tree": "clean|dirty|unknown",
    "linkage_quality": "stable_commit|working_tree_context|explicit_ref"
  }
}
```

### 13.2 `linkage_quality` Values

- `stable_commit`
- `working_tree_context`
- `explicit_ref`

### 13.3 Behavior Rules

Checkpoint:

- may be created on a dirty working tree
- does not require a commit to exist
- if `HEAD` exists, record it; if not, record `null` and emit a warning

Adoption:

- should bind to the current `HEAD` whenever possible
- a dirty working tree may proceed, but must emit a warning or degrade linkage quality
- strict mode may require a clean tree plus a stable commit

Additional notes:

- V1 does not run any Intent command outside a Git repository
- errors for non-Git directories are returned uniformly as `GIT_STATE_INVALID` at command entry, rather than degrading into a Git-linkage state

### 13.4 strict mode

The first version keeps `strict_adoption` in scope but as a later capability within the contract:

```json
{
  "git": {
    "strict_adoption": false
  }
}
```

When `strict_adoption=true`:

- `itt adopt` requires a Git repo
- `HEAD` must resolve
- the working tree must be clean

## 14. Read-Command JSON Contract

### 14.1 `itt status --json`

```json
{
  "ok": true,
  "object": "status",
  "schema_version": "0.1",
  "active_intent": {
    "id": "intent-001",
    "title": "Reduce onboarding confusion",
    "status": "active"
  },
  "active_run": null,
  "current_checkpoint": {
    "id": "cp-001",
    "title": "Landing page candidate B",
    "status": "candidate"
  },
  "latest_adoption": null,
  "workspace_status": "candidate_ready",
  "workspace_status_reason": "A current checkpoint is available for adoption.",
  "git": {
    "branch": "main",
    "head": "a91c3d2",
    "working_tree": "clean"
  },
  "next_action": {
    "command": "itt adopt --checkpoint cp-001 -m \"Adopt candidate\"",
    "args": ["adopt", "--checkpoint", "cp-001", "-m", "Adopt candidate"],
    "reason": "Current checkpoint is ready for adoption."
  },
  "warnings": []
}
```

### 14.2 `itt inspect --json`

```json
{
  "ok": true,
  "object": "inspect",
  "schema_version": "0.1",
  "mode": "human",
  "state": {
    "active_intent_id": "intent-001",
    "active_run_id": null,
    "current_checkpoint_id": "cp-001",
    "last_adoption_id": null,
    "workspace_status": "candidate_ready"
  },
  "active_intent": {
    "id": "intent-001",
    "title": "Reduce onboarding confusion",
    "status": "active"
  },
  "current_checkpoint": {
    "id": "cp-001",
    "title": "Landing page candidate B",
    "status": "candidate",
    "adopted": false
  },
  "latest_adoption": null,
  "latest_decision": null,
  "latest_event": null,
  "candidate_checkpoints": [
    {
      "id": "cp-001",
      "title": "Landing page candidate B",
      "status": "candidate",
      "selected": true,
      "adopted": false
    }
  ],
  "workspace_status_reason": "A current checkpoint is available for adoption.",
  "pending_items": [
    {
      "type": "candidate",
      "id": "cp-001",
      "reason": "Ready for adoption"
    }
  ],
  "suggested_next_actions": [
    {
      "command": "itt adopt --checkpoint cp-001 -m \"Adopt candidate\"",
      "args": ["adopt", "--checkpoint", "cp-001", "-m", "Adopt candidate"],
      "reason": "Checkpoint is current and not yet adopted"
    }
  ],
  "git": {
    "branch": "main",
    "head": "a91c3d2",
    "working_tree": "clean"
  },
  "warnings": []
}
```

### 14.3 Stability Requirements

- top-level fields must stay fixed
- missing objects return `null`
- empty lists return `[]`
- all enum values must be documented

Null / empty rules:

- if the current directory is not inside a Git worktree, `status --json` and `inspect --json` return an error object with:
  `ok=false`, `error.code=GIT_STATE_INVALID`
- if `.intent/` has not been initialized yet, `status --json` and `inspect --json` return an error object with:
  `ok=false`, `error.code=NOT_INITIALIZED`
- in successful `status --json` responses, these top-level fields must always exist:
  `ok`, `object`, `schema_version`, `active_intent`, `active_run`, `current_checkpoint`, `latest_adoption`, `workspace_status`, `workspace_status_reason`, `git`, `next_action`, `warnings`
- within that response, `active_intent`, `active_run`, `current_checkpoint`, `latest_adoption`, and `next_action` may be `null`
- `git` must always be an object; `warnings` must always be an array
- in successful `inspect --json` responses, these top-level fields must always exist:
  `ok`, `object`, `schema_version`, `mode`, `state`, `active_intent`, `active_run`, `current_checkpoint`, `latest_adoption`, `latest_decision`, `latest_event`, `candidate_checkpoints`, `workspace_status_reason`, `pending_items`, `suggested_next_actions`, `git`, `warnings`
- `state.active_intent_id`, `state.active_run_id`, `state.current_checkpoint_id`, and `state.last_adoption_id` may be `null`
- `active_intent`, `active_run`, `current_checkpoint`, `latest_adoption`, `latest_decision`, and `latest_event` may be `null`
- `candidate_checkpoints`, `pending_items`, `suggested_next_actions`, and `warnings` must always be arrays
- `workspace_status_reason` must always be a string
- if `next_action` or `suggested_next_actions` exists, they must contain `command`, `args`, and `reason`

Minimum successful-state conventions:

| Status | `status --json` | `inspect --json` |
| --- | --- | --- |
| `idle` | `active_intent=null`, `current_checkpoint=null`, `latest_adoption=null`, `next_action` points to `itt start` | matching objects are `null`, `candidate_checkpoints=[]` |
| `blocked_no_active_intent` | `active_intent=null`, `current_checkpoint=null` | matching objects are `null`, array fields are `[]` |
| `intent_active` | `current_checkpoint=null` | `current_checkpoint=null`, `candidate_checkpoints=[]`, `pending_items=[]` |
| `candidate_ready` | `current_checkpoint` is an object, `next_action` points to `itt adopt` | `current_checkpoint` is an object, `candidate_checkpoints` contains at least the current candidate |
| `adoption_recorded` | `current_checkpoint=null` | `state.current_checkpoint_id=null`, `current_checkpoint=null`, `latest_event` points to the adoption or revert |

## 15. Write-Command JSON Contract

All write commands support `--json` and return a shared structure:

```json
{
  "ok": true,
  "object": "checkpoint",
  "action": "create",
  "id": "cp-001",
  "state_changed": true,
  "workspace_status": "candidate_ready",
  "workspace_status_reason": "A current checkpoint is available for adoption.",
  "result": {},
  "next_action": {
    "command": "itt adopt --checkpoint cp-001 -m \"Adopt candidate\"",
    "args": ["adopt", "--checkpoint", "cp-001", "-m", "Adopt candidate"],
    "reason": "Checkpoint created and selected"
  },
  "warnings": []
}
```

Minimum required fields:

- `ok`
- `object`
- `action`
- `id`
- `state_changed`
- `workspace_status`
- `workspace_status_reason`
- `result`
- `warnings`

If `next_action` exists, it must minimally contain:

- `command`
- `args`
- `reason`

### 15.1 `--id-only`

Supports machine-call scenarios:

```text
cp-001
```

Requirements:

- output only the object id
- do not include explanatory text
- errors still go through stderr / non-zero exit code

### 15.2 Baseline Parameter Boundary

V1 parameter boundary:

- `start`, `snap`, `adopt`, `revert`, `run start`, and `run end` must support `--json`
- `start`, `snap`, `adopt`, `revert`, `run start`, and `run end` must support `--id-only`
- `init`, `start`, `snap`, `adopt`, `revert`, `run start`, `run end`, and `checkpoint select` must support `--no-interactive`

`itt adopt` must additionally support:

- `--if-not-adopted`
- `--checkpoint <id>`
- `--link-git <hash|HEAD>`

Public syntax frozen in V1:

- V1 freezes only `itt adopt --checkpoint <id>` as the explicit checkpoint-targeting syntax
- V1 does not support positional syntax such as `itt adopt <checkpoint-id>`

V1 does not require:

- `--yes`
- global `--verbose`
- global `--quiet`
- dedicated filter flags for `log`

## 16. Error Model and Exit Codes

### 16.1 exit codes

| code | meaning |
| --- | --- |
| `0` | success |
| `1` | general failure |
| `2` | invalid input |
| `3` | state conflict |
| `4` | object not found |

### 16.2 JSON Error Shape

```json
{
  "ok": false,
  "error": {
    "code": "STATE_CONFLICT",
    "message": "Multiple candidate checkpoints exist and no current checkpoint is selected.",
    "details": {
      "intent_id": "intent-001",
      "candidate_count": 2
    },
    "suggested_fix": "Run `itt checkpoint select <id>` or pass `--checkpoint <id>` explicitly."
  }
}
```

### 16.3 V1 Error Code Set

- `GENERAL_FAILURE`
- `INVALID_INPUT`
- `STATE_CONFLICT`
- `OBJECT_NOT_FOUND`
- `ALREADY_EXISTS`
- `NOT_INITIALIZED`
- `GIT_STATE_INVALID`

### 16.4 Typical Error Scenarios

| Scenario | exit code | error code |
| --- | --- | --- |
| any command run outside a Git worktree | `1` | `GIT_STATE_INVALID` |
| running `itt init` again in an already initialized repo | `1` | `ALREADY_EXISTS` |
| running `itt snap` with no active intent | `3` | `STATE_CONFLICT` |
| checkpoint id does not exist | `4` | `OBJECT_NOT_FOUND` |
| missing parameter or invalid flag | `2` | `INVALID_INPUT` |

## 17. Idempotency and Non-Interactive Behavior

### 17.1 Idempotency Rules

`itt start`

- non-idempotent by default
- each invocation creates a new intent

`itt snap`

- non-idempotent by default
- each invocation creates a new checkpoint

`itt adopt`

- must support `--if-not-adopted`
- if the target checkpoint already has an active adoption, return a success-like no-op structure

Example:

```json
{
  "ok": true,
  "object": "adoption",
  "action": "create",
  "id": "adopt-001",
  "state_changed": false,
  "noop": true,
  "reason": "Checkpoint already adopted",
  "warnings": []
}
```

`itt init`

- defined as non-idempotent in V1
- fails if the directory already exists

### 17.2 Non-Interactive Policy

Rules:

- the CLI must not enter selectors, prompts, or confirmation flows
- ambiguous state must fail directly
- stable error objects must be returned
- because V1 does not rely on confirmation flows, command correctness must not depend on `--yes`

When multiple candidates exist without a unique current checkpoint:

- human mode may suggest the next step
- non-interactive mode must fail directly with `STATE_CONFLICT`

## 18. Agent-Friendly Requirements

- all read commands support `--json`
- all write commands return stable result structures
- all core write commands support non-interactive mode
- all core write commands support basic idempotency protection
- `inspect --json` is the standard context entry point

Recommended agent call order:

1. `itt inspect --json`
2. evaluate context and pending actions
3. execute an explicit object command
4. run `itt inspect --json` again to verify the state change

Default semantic-recording protocol:

1. if the user request represents a substantive new work slice and there is no suitable active intent, derive a concise intent title and create one
2. start a run for one meaningful execution pass when implementation work begins
3. create a checkpoint when a candidate state is worth naming, comparing, or revisiting
4. record an adoption when a candidate is explicitly chosen
5. record a decision when the rationale should outlive the immediate edit
6. end the run when that execution pass is complete

This protocol is a functional direction for agent integrations. Its purpose is to test whether Intent actually improves agent work quality and efficiency; it is not a claim that more recording is automatically better.

Restraint rules:

- do not create semantic objects for trivial read-only questions or one-line clarifications
- if the existing active intent still matches the user request, continue it rather than starting a new one
- if intent fit is ambiguous, surface the assumption before creating a fresh intent
- `decision` should be reserved for durable tradeoffs, constraints, or principles, not every explanation

Additional boundaries:

- in V1, agent integrations should prefer the surface CLI with explicit flags, or the corresponding canonical action
- agents should not rely on text `status` / `inspect` output for stable parsing
- use `status --json` if only a lightweight current summary is needed
- use `inspect --json` if stable context and pending-action derivation are needed

## 19. Output Text Principles

CLI copy should emphasize the action result before object-creation details.

Not recommended:

```text
Created adoption object adopt-007
```

Recommended:

```text
Adopted checkpoint cp-012
Intent: Reduce onboarding confusion
Git: a91c3d2
Next: itt log
```

Users should see these things first:

- what action succeeded
- which object it applied to
- what state the workspace is now in
- what should happen next

### 19.1 Human Text Contract

V1 does not freeze text word for word, but it does freeze the information hierarchy and output structure.

Rules:

- the first line must state the result first, not object-creation details
- the following lines should prioritize object references directly related to the action
- `Git:` appears when helpful, but not every command must print full Git context
- `Next:` is the default closing line and should recommend the most reasonable next action
- `Warning:` is shown only for quality degradation, dirty working trees, or state risk
- recoverable human-facing errors may include an `Error:` line, but the first line should still explain what happened
- missing information should simply be omitted; do not print placeholders such as `null` or `N/A`

Recommended field order:

- action headline
- `Intent:`
- `Checkpoint:` / `Adoption:`
- `Status:` / `Git:`
- `Warning:`
- `Error:`
- `Next:`

Empty-state and error-state rules:

- empty states use a neutral headline and should not begin with `Error:`
- recoverable errors should explain the blocking reason first, then give a clear next step
- if an error maps directly to a stable error code, `Error: <CODE>` can appear on the next line or later
- human text does not need to show exit codes
- even in empty states, `status` and `log` should try to give a concrete next command

### 19.2 Human Output Examples

The following examples provide the V1 baseline for human-readable output, mainly freezing information structure and emphasis order.

`itt init`

```text
Initialized Intent in .intent/
Git: main @ a91c3d2
Next: itt start "Describe the problem"
```

`itt start "Reduce onboarding confusion"`

```text
Started intent intent-001
Title: Reduce onboarding confusion
Status: intent_active
Next: itt snap "First candidate"
```

`itt snap "Landing page candidate B"`

```text
Saved checkpoint cp-001
Intent: intent-001  Reduce onboarding confusion
Checkpoint: Landing page candidate B
Git: main @ a91c3d2 (dirty)
Next: itt adopt -m "Adopt progressive disclosure layout"
```

`itt adopt -m "Adopt progressive disclosure layout"`

```text
Adopted checkpoint cp-001
Intent: intent-001  Reduce onboarding confusion
Adoption: adopt-001  Adopt progressive disclosure layout
Git: a91c3d2
Next: itt log
```

`itt status`

```text
Semantic workspace
Intent: intent-001  Reduce onboarding confusion
Current checkpoint: cp-001  Landing page candidate B
Status: candidate_ready
Next: itt adopt -m "Adopt candidate"
```

`itt status` empty state

```text
Semantic workspace
Status: idle
No active intent
Next: itt start "Describe the problem"
```

`itt status` not initialized

```text
Intent is not initialized in this repository
Error: NOT_INITIALIZED
Next: itt init
```

`itt status` outside Git worktree

```text
Intent requires a Git repository
Error: GIT_STATE_INVALID
Next: git init
```

`itt status` conflict state

```text
Semantic workspace
Intent: intent-001  Reduce onboarding confusion
Status: conflict_multiple_candidates
Warning: Multiple candidate checkpoints exist and no unique current checkpoint is selected
Next: itt checkpoint select cp-002
```

`itt log`

```text
Semantic history

2026-03-15 14:20  adopt-001  Adopt progressive disclosure layout
  Intent: intent-001  Reduce onboarding confusion
  Checkpoint: cp-001  Landing page candidate B
  Git: a91c3d2

2026-03-15 14:30  adopt-002  Revert progressive disclosure layout
  Intent: intent-001  Reduce onboarding confusion
  Checkpoint: cp-001  Landing page candidate B
  Reverts: adopt-001
  Git: b02d441
```

`itt log` empty state

```text
Semantic history
No adoptions recorded yet
Next: itt status
```

`itt log` not initialized

```text
Intent is not initialized in this repository
Error: NOT_INITIALIZED
Next: itt init
```

`itt log` outside Git worktree

```text
Intent requires a Git repository
Error: GIT_STATE_INVALID
Next: git init
```

`itt revert`

```text
Reverted adoption adopt-001
Intent: intent-001  Reduce onboarding confusion
Checkpoint: cp-001  Landing page candidate B
Adoption: adopt-002  Revert progressive disclosure layout
Next: itt log
```

`itt adopt` conflict error

```text
Cannot adopt because the current checkpoint is not unambiguous
Error: STATE_CONFLICT
Candidates:
- cp-002: Landing page candidate C
- cp-001: Landing page candidate B
Next: itt checkpoint select cp-002
```

`itt snap` without active intent

```text
Cannot save a checkpoint without an active intent
Error: STATE_CONFLICT
Next: itt start "Describe the problem"
```

any command outside Git worktree

```text
Intent requires a Git repository
Error: GIT_STATE_INVALID
Next: git init
```

## 20. First-Version Test Matrix

- initialization: first `itt init` succeeds, repeated init fails, and directory structure is correct
- start: intent creation succeeds, `active_intent_id` is updated, `workspace_status=intent_active`
- snap: checkpoint creation succeeds, new checkpoint is selected automatically, old selection is cleared, and `current_checkpoint_id` is updated
- adopt: current checkpoint can be adopted by default, checkpoint and adoption are linked correctly, and `last_adoption_id` is updated
- revert: a new revert record is created, the original adoption is marked `reverted`, and `last_adoption_id` is updated
- conflict cases: `snap` fails without an active intent; `adopt` fails without a current checkpoint; `adopt` fails when multiple candidates exist and the default object is unclear
- inspect/status: `status --json` and `inspect --json` keep stable top-level fields; missing objects return `null`
- object transitions: checkpoint becomes `adopted` after adoption and `reverted` after revert; after adoption, `current_checkpoint_id=null`
- config/init: `config.json` schema is correct; `itt init` returns `GIT_STATE_INVALID` outside a Git repo
- Git prerequisite: all commands return `GIT_STATE_INVALID` outside a Git repo before `NOT_INITIALIZED`
- human output: `init`, `start`, `snap`, `adopt`, `status`, `log`, and `revert` keep the expected information hierarchy, headline, and `Next:` line
- empty/error output: `status` copy is correct for idle / not initialized / outside Git / conflict; `log` copy is correct for empty / not initialized / outside Git; recoverable errors include a clear `Next:`
- Git linkage: clean repos record `HEAD`; dirty working trees degrade quality; dirty-tree adoption fails in strict mode

## 21. Recommended Implementation Order

### Phase 1

- `.intent/` initialization
- id generation
- JSON file read/write
- `state.json` read/write and `workspace_status` derivation

### Phase 2

- `itt start`
- `itt snap`
- `itt adopt`

### Phase 3

- `itt status`
- `itt log`
- `itt inspect --json`

### Phase 4

- exit codes
- `--json`
- `--id-only`
- `--no-interactive`
- `--if-not-adopted`

### Phase 5

- `itt checkpoint select`
- `itt revert`
- strict mode

## 22. Frozen Items Before Implementation

- `.intent/` directory name
- minimum `config.json` schema: `schema_version`, `git.strict_adoption`
- `state.json` filename
- V1 public command surface: `init/start/status/snap/adopt/log/inspect/checkpoint select/revert`
- all commands run only inside a Git worktree; non-Git directories uniformly return `GIT_STATE_INVALID`
- object type names: `intent` / `checkpoint` / `adoption` / `run` / `decision`
- ID prefixes: `intent` / `cp` / `adopt` / `run` / `decision`
- checkpoint state transitions after `adopt/revert`
- `workspace_status` enum
- `linkage_quality` enum
- `itt adopt --checkpoint <id>` as the only explicit checkpoint-targeting syntax
- top-level fields for `status --json`
- top-level fields for `inspect --json`
- `log` stays human-readable and does not freeze `log --json`
- exit codes `0/1/2/3/4`
- stable error-code strings such as `STATE_CONFLICT` / `OBJECT_NOT_FOUND`

## 23. One-Sentence Conclusion

What should be frozen first is not a larger narrative, but one unified CLI source of truth: the local object layer, the state machine, the JSON contract, the error model, and the minimum usable workflow around `start -> snap -> adopt`.
