# Intent CLI

[中文](../CN/cli.md) | English

Intent CLI is the local semantic-history CLI for Intent. It manages only three object types:

- `intent`: a recoverable goal
- `snap`: a semantic snapshot per query — what was done, why, what's next
- `decision`: a long-lived constraint across intents

The CLI is intentionally small:

- Recovery uses `itt inspect`
- Structural diagnosis uses `itt doctor`
- Graph browsing belongs to IntHub
- There are no `list` commands

## Commands (10)

| Command | What it does | Notes |
|---|---|---|
| `itt version` | Print CLI version | |
| `itt init` | Initialize `.intent/` in current Git repo | |
| `itt inspect` | Resume-first recovery view | Start every session here. Returns `active_intents`, `active_decisions`, `suspended`, `warnings`. |
| `itt doctor` | Validate object graph | Use when `inspect` shows warnings. Returns `healthy`, `issues`. |
| `itt intent create WHAT --query Q [--why W]` | Create a new intent | Auto-attaches all active decisions. `origin` auto-filled. |
| `itt intent activate [ID]` | `suspend` → `active` | Catches up active decisions. Infers ID when unique. |
| `itt intent suspend [ID]` | `active` → `suspend` | Infers ID when unique. |
| `itt intent done [ID]` | `active` → `done` (terminal) | Infers ID when unique. |
| `itt snap create WHAT [--query Q] --why W [--next N]` | Create a semantic snapshot | Auto-attaches to active intent. If multiple, CLI returns candidates for `--intent ID`. |
| `itt decision create WHAT [--query Q] --why W` | Create a long-lived constraint | Auto-attaches all active intents. `origin` auto-filled. |
| `itt decision deprecate ID [--reason TEXT]` | `active` → `deprecated` (terminal) | Preserves history; stops future auto-attach. |
| `itt hub link [--api-base-url URL] [--project-name NAME]` | Link workspace to IntHub | Writes `.intent/hub.json`. Requires GitHub remote. |
| `itt hub sync [--dry-run]` | Push snapshot to IntHub | Full snapshot, not incremental. Includes Git context. |

## Object Model

```mermaid
flowchart LR
  D1["🔶 Decision 1"]
  D2["🔶 Decision 2"]

  subgraph Intent1["🎯 Intent 1"]
    direction LR
    S1["📸 Snap 1"] --> S2["📸 Snap 2"] --> S3["📸 ..."]
  end

  subgraph Intent2["🎯 Intent 2"]
    direction LR
    S4["📸 Snap 1"] --> S5["📸 Snap 2"] --> S6["📸 ..."]
  end

  D1 -- auto-attach --> Intent1
  D1 -- auto-attach --> Intent2
  D2 -- auto-attach --> Intent2
```

### Snap: what each field carries

```mermaid
flowchart LR
  Q["query\n👤 user said what"] --> W["what\n🤖 AI did what"] --> Y["why\n💡 why"] --> N["next\n➡️ what's next"]
```

### When to create a snap

```mermaid
flowchart TD
  Q["User query completed"] --> C{Code changes?}
  C -->|Yes| B["✅ Snap\nwhat = what was done\nwhy + next"]
  C -->|No| D{Formed conclusions\nworth preserving?}
  D -->|Yes| E["✅ Snap\nrecord conclusions"]
  D -->|No| A["⏭️ No snap\nsimple Q&A"]
```

### State machines

```mermaid
stateDiagram-v2
  state Intent {
    [*] --> active
    active --> suspend
    suspend --> active
    active --> done
  }
  state Decision {
    [*] --> active2: active
    active2 --> deprecated
  }
  state Snap {
    [*] --> immutable
  }
```

## Object Schema

| Field | Intent | Snap | Decision | Notes |
| --- | :---: | :---: | :---: | --- |
| `id` | ✓ | ✓ | ✓ | Auto-incremented, zero-padded (`intent-001`, `snap-001`, `decision-001`) |
| `object` | ✓ | ✓ | ✓ | `"intent"`, `"snap"`, or `"decision"` |
| `created_at` | ✓ | ✓ | ✓ | ISO 8601 UTC timestamp |
| `what` | ✓ | ✓ | ✓ | Intent/Decision: short theme. Snap: what was done (concise action). |
| `query` | ✓ | ✓ | ✓ | User query that triggered the object |
| `origin` | ✓ | ✓ | ✓ | Auto-detected from environment (e.g. `claude-code`, `cursor`, `codex-desktop`) |
| `why` | ✓ | ✓ | ✓ | Intent: why this goal. Snap: why this approach. Decision: why this constraint. |
| `status` | ✓ | | ✓ | Intent: `active` / `suspend` / `done`. Decision: `active` / `deprecated`. |
| `next` | | ✓ | | What comes next — remaining work, direction, blockers |
| `intent_id` | | ✓ | | Parent intent |
| `snap_ids` | ✓ | | | Ordered list of child snaps |
| `decision_ids` | ✓ | | | Linked decisions (auto-attached on create) |
| `intent_ids` | | | ✓ | Linked intents (auto-attached on create) |
| `reason` | | | ✓ | Why the decision was deprecated (set via `--reason`) |

All fields are **immutable after creation**.

### Origin detection

`origin` is auto-detected from the process environment:

| Environment signal | Origin label |
|---|---|
| `ITT_ORIGIN` / `INTENT_ORIGIN` | *(custom label)* |
| `CURSOR_TRACE_ID` | `cursor` |
| `CODEX_INTERNAL_ORIGINATOR_OVERRIDE="Codex Desktop"` | `codex-desktop` |
| `CODEX_THREAD_ID` / `CODEX_SHELL` / `CODEX_CI` | `codex` |
| `TERM_PROGRAM=vscode` | `vscode` |
| Codespaces / GitHub Actions / Gitpod env vars | `codespaces` / `github-actions` / `gitpod` |

Priority: explicit `--origin LABEL` > `ITT_ORIGIN` / `INTENT_ORIGIN` > built-in heuristics.

There are no `show` commands — recovery uses `itt inspect`, browsing uses IntHub.

## JSON Output

### Standard success envelope

All successful commands except `inspect` use:

```json
{
  "ok": true,
  "action": "<command-name>",
  "result": {},
  "warnings": []
}
```

### `inspect`

`inspect` returns:

```json
{
  "ok": true,
  "active_intents": [],
  "active_decisions": [],
  "suspended": [],
  "warnings": []
}
```

### `doctor`

`doctor` returns:

```json
{
  "ok": true,
  "action": "doctor",
  "result": {
    "healthy": true,
    "issues": []
  },
  "warnings": []
}
```

### Error envelope

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

## Error Codes

| Code | Meaning |
| --- | --- |
| `NOT_INITIALIZED` | `.intent/` does not exist |
| `ALREADY_EXISTS` | `.intent/` already exists when running `init` |
| `GIT_STATE_INVALID` | Not inside a Git worktree |
| `STATE_CONFLICT` | Illegal state transition |
| `OBJECT_NOT_FOUND` | Object ID not found |
| `INVALID_INPUT` | Invalid arguments or missing required input |
| `NO_ACTIVE_INTENT` | `snap create`, `intent suspend`, or `intent done` omitted the target intent and none is `active` |
| `MULTIPLE_ACTIVE_INTENTS` | `snap create`, `intent suspend`, or `intent done` omitted the target intent and several are `active` |
| `NO_SUSPENDED_INTENT` | `intent activate` omitted the target intent and none is `suspend` |
| `MULTIPLE_SUSPENDED_INTENTS` | `intent activate` omitted the target intent and several are `suspend` |
| `HUB_NOT_CONFIGURED` | IntHub API base URL is missing |
| `NOT_LINKED` | Current workspace has not been linked to IntHub |
| `PROVIDER_UNSUPPORTED` | Current Git remote is not supported |
| `NETWORK_ERROR` | IntHub could not be reached |
| `SERVER_ERROR` | IntHub returned an error or invalid JSON |

## Operational Notes

- `.intent/` is local workspace metadata and should stay out of Git history
- All objects are immutable after creation
- IDs are zero-padded and monotonic per object type: `intent-001`, `snap-001`, `decision-001`
