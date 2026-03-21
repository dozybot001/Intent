# Intent CLI

[中文](../CN/cli.md) | English

Schema version: **1.0**

Intent CLI is the local semantic-history CLI for Intent. It manages only three object types:

- `intent`: a recoverable goal
- `snap`: a semantic checkpoint under an intent
- `decision`: a long-lived constraint across intents

The CLI is intentionally small:

- Recovery uses `itt inspect`
- Structural diagnosis uses `itt doctor`
- Graph browsing belongs to IntHub
- There are no `list` commands

## Command Surface

### Global

| Command | Role |
| --- | --- |
| `itt version` | Print CLI version |
| `itt init` | Initialize `.intent/` in the current Git repo |
| `itt inspect` | Resume-first recovery view |
| `itt doctor` | Structure diagnosis view |

### Intent

| Command | Role |
| --- | --- |
| `itt intent create TITLE --query Q [--rationale R]` | Create a new intent |
| `itt intent activate [ID]` | `suspend` → `active` |
| `itt intent suspend [ID]` | `active` → `suspend` |
| `itt intent done [ID]` | `active` → `done` |

### Snap

| Command | Role |
| --- | --- |
| `itt snap create TITLE [--intent ID] [--origin LABEL] --summary S` | Create one semantic checkpoint (omit `--intent` when exactly one active intent; `origin` is auto-filled from env unless overridden) |
| `itt snap feedback ID TEXT` | Overwrite snap feedback |

### Decision

| Command | Role |
| --- | --- |
| `itt decision create TITLE --rationale R` | Create a new decision |
| `itt decision deprecate ID` | `active` → `deprecated` |
### Hub

| Command | Role |
| --- | --- |
| `itt hub link [--project-name NAME] [--api-base-url URL] [--token TOKEN]` | Configure local IntHub access if needed, then link the current workspace |
| `itt hub sync [--api-base-url URL] [--token TOKEN] [--dry-run]` | Push the local semantic snapshot to IntHub |

## Global Commands

### `itt version`

Print the current CLI version.

```bash
itt version
```

### `itt init`

Initialize `.intent/` inside the current Git repository.

```bash
itt init
```

### `itt inspect`

Resume-first recovery view.

- Use it at the start of a session.
- Default output: `active_intents`, `active_decisions`, `suspended`, `warnings`.
- It is not a full graph browser.

```bash
itt inspect
```

### `itt doctor`

Structure diagnosis view.

- Use it when `inspect` shows warnings or the graph looks inconsistent.
- Default output: `healthy`, `issues`.
- It validates broken references, invalid statuses, and one-way links.

```bash
itt doctor
```

## Object Commands

### Intent

`create` recognizes a new recoverable goal. `activate`, `suspend`, and `done` are state transitions.

```bash
itt intent create "Fix the login timeout bug" \
  --query "why does login timeout after 5s?" \
  --rationale "users on slow networks get logged out mid-session"

itt intent suspend intent-001
itt intent activate intent-001
itt intent done intent-001
```

Notes:

- New intents start as `active`
- Creating an intent auto-attaches all current `active` decisions
- Reactivating an intent catches up any current `active` decisions
- `activate`, `suspend`, and `done` accept `ID` or infer it when there is exactly one matching candidate
- Omitting `ID` when none match returns `NO_ACTIVE_INTENT` or `NO_SUSPENDED_INTENT`
- Omitting `ID` when several match returns `MULTIPLE_ACTIVE_INTENTS` or `MULTIPLE_SUSPENDED_INTENTS`, with `error.details.candidates`

### Snap

`create` writes one semantic checkpoint under an active intent. A semantic checkpoint preserves what changed, what was learned, and later user feedback. `feedback` is deliberately separate and overwrite-only.

```bash
itt snap create "Raise timeout to 30s" \
  --summary "Updated timeout config and ran the login test"

# When several intents are active at once, disambiguate:
itt snap create "Raise timeout to 30s" \
  --intent intent-001 \
  --summary "Updated timeout config and ran the login test"

itt snap feedback snap-001 "works in staging"
```

Notes:

- `--summary` is required
- `--intent` is optional: if omitted and exactly one intent is `active`, that intent is used; if none are active, the CLI errors with `NO_ACTIVE_INTENT`; if more than one is active, it errors with `MULTIPLE_ACTIVE_INTENTS` and lists `candidates` in `error.details` for the agent to choose
- `origin` on the stored snap is filled automatically from the process environment (inherited by the `itt` subprocess). Set `ITT_ORIGIN` or `INTENT_ORIGIN` to a stable label in your shell profile or IDE integration when heuristics are not enough. Built-in hints include: `CURSOR_TRACE_ID` → `cursor`, `CODEX_INTERNAL_ORIGINATOR_OVERRIDE="Codex Desktop"` → `codex-desktop`, `CODEX_THREAD_ID` / `CODEX_SHELL` / `CODEX_CI` → `codex`, `TERM_PROGRAM=vscode` → `vscode`, plus Codespaces / GitHub Actions / Gitpod. Use `--origin LABEL` only when you need to override detection for that one command.
- New snaps start as `active`
- Creating a snap writes both `snap.intent_id` and the parent intent's `snap_ids`
- Feedback is stored later via `itt snap feedback`
- Correction happens by feedback or by writing a later snap, not by reverting the old one

### Decision

`create` records a long-lived constraint.

```bash
itt decision create "Timeout must stay configurable" \
  --rationale "Different deployments have different latency envelopes"

itt decision deprecate decision-001
```

Notes:

- New decisions start as `active`
- Creating a decision auto-attaches all current `active` intents
- `deprecate` preserves history; it only stops future auto-attachment

There are no `show` commands.

- Default recovery belongs to `itt inspect`
- Human-oriented browsing belongs to IntHub

## Hub Commands

### `itt hub link`

Configure local IntHub access if needed, then link the current GitHub-backed workspace.

```bash
itt hub link --api-base-url http://127.0.0.1:7210 --project-name "Intent"
itt hub link --api-base-url http://127.0.0.1:7210 --token dev-token --project-name "Intent"
```

Notes:

- Requires the current `origin` remote to be a supported GitHub repo
- Writes `.intent/hub.json`
- Persists `api_base_url`, optional local token, `workspace_id`, `project_id`, and `repo_binding`

### `itt hub sync`

Push the current `.intent/` snapshot plus Git context to IntHub.

```bash
itt hub sync
itt hub sync --dry-run
```

Notes:

- Sync uploads a full snapshot, not an incremental patch
- Sync includes Git context such as `branch`, `head_commit`, `dirty`, and `remote_url`
- `--dry-run` prints the outgoing payload instead of sending it

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
- Object content is append-only; do not rewrite old titles or summaries
- `snap feedback` is the only post-creation overwrite path
- IDs are zero-padded and monotonic per object type: `intent-001`, `snap-001`, `decision-001`
