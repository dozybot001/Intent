---
name: intent-cli
description: Track what you're doing and why with structured semantic history (.intent/) — goals, decisions, and work state that persist across agent sessions.
---

# Intent — semantic history

This repo uses Intent (`.intent/`) to track what you're doing and why.
Install: `git clone https://github.com/dozybot001/Intent.git && cd Intent && pip install .`

Structured `itt` command outputs are JSON — parse them, don't guess. `argparse` help and usage text are not JSON.

## Objects

| Object | What it is | States |
|--------|-----------|--------|
| **Intent** | A recoverable goal. `query` = user's words, `why` = context (fill when available, `""` otherwise). | `active` → `suspend` ↔ `active` → `done` (terminal) |
| **Snap** | Semantic snapshot under an intent: `what` / `why` / `next` / `query`. | Immutable; correct via new snap |
| **Decision** | Long-lived constraint that outlives any single intent. **Test:** would a future intent on a different problem still need to respect this? Yes → decision. No → snap it. | `active` → `deprecated` (terminal) |

- Relationships are **bidirectional**, **append-only**: creating an intent auto-attaches all active decisions; creating a decision auto-attaches all active intents. Both sides update.
- Objects are **immutable** after creation. Correct mistakes by writing a new snap.

## Workflow

### 1. Session start

**Every session begins with `itt inspect`.** Not optional.

1. Continue from each active intent's `latest_snap`. Do not ask user to re-explain.
2. Respect `active_decisions` — they are standing constraints.
3. Check `suspended` — mention or reactivate if relevant.
4. If `warnings` exist, run `itt doctor`.
5. Everything empty → fresh workspace.

### 2. Work freely

Focus on the user's request. Semantic recording happens when the user asks for it, not during work.

### 3. Record when asked

When the user tells you to record (e.g. "记录一下", "let's record what we did", or signals the goal is achieved), look back at the work and create:

1. **One intent** — summarize the goal of this interaction
2. **Snaps** — one per milestone or meaningful chunk of work, capturing what/why/next
3. **`itt intent done`** — if the goal is fully resolved

```bash
itt intent create "Implemented auth retry logic" \
  --query "fix the login timeout" \
  --why "users on slow networks were getting logged out"
itt snap create "Added exponential backoff to API client" \
  --why "transient 503s from upstream caused cascading failures" \
  --next "monitoring dashboard needs retry metrics"
itt snap create "Updated error handling in login flow" \
  --why "old handler swallowed retry errors silently"
itt intent done
```

Snap fields:
- `WHAT`: concise action description for scanning
- `--query`: the user query that triggered the work (optional)
- `--why`: reasoning behind this approach (optional; fill when meaningful)
- `--next`: remaining work, direction, blockers (optional)
- `--intent`: required only when multiple intents are active (CLI infers single active)

### 4. Record decisions

**Never create a decision without user involvement.**

| Path | Trigger | Action |
|------|---------|--------|
| Explicit | User says `decision-[text]` or `决定-[text]` | Create directly |
| Discovered | You spot a long-lived constraint | Ask user: "Should I record this as a decision?" → create only after confirmation |

If a user request conflicts with an active decision, say so and ask whether to deprecate.

### 5. Context switching

```bash
itt intent suspend intent-001            # pause current work
itt intent create "Urgent fix" --query "..."  # handle interruption
# ... work ...
itt intent done intent-002               # complete the fix
itt intent activate intent-001           # resume; active decisions are caught up
```

### 6. Goal complete

`itt intent done` — terminal. If the problem resurfaces, create a new intent.

## Key rules

- **Recording is user-initiated** — like git commit, record when the user asks
- **Decisions require user confirmation** — never create on your own judgment alone
- **Always `done` completed intents** — stale intents pollute inspect and auto-attach to unrelated decisions
- **Snap reasoning, not mechanics** — capture why and what's next, not diffs or command logs
- **One intent per goal, not per step** — "Migrate auth to JWT", not "Add JWT token generation"
- **Decision hygiene** — when `active_decisions` exceeds 20, prompt the user: "当前有 N 条 active decision，要做一轮清理吗？" If yes, review all active decisions, propose merging same-topic ones into a consolidated decision, and deprecate the originals after user confirmation

## Command reference

### Global

| Command | What it does |
|---|---|
| `itt init` | Create `.intent/` in current git repo |
| `itt inspect` | Resume-first recovery view — **start every session here** |
| `itt doctor` | Validate object graph structure and links |
| `itt version` | Print version |

### Intent

| Command | What it does |
|---|---|
| `itt intent create WHAT --query Q [--why W] [--origin LABEL]` | New intent (auto-attaches active decisions; `origin` auto-filled from env) |
| `itt intent activate [ID]` | `suspend` → `active` (catches up on active decisions; infers the only suspended intent if unique) |
| `itt intent suspend [ID]` | `active` → `suspend` (infers the only active intent if unique) |
| `itt intent done [ID]` | `active` → `done` (terminal; infers the only active intent if unique) |

### Snap

| Command | What it does |
|---|---|
| `itt snap create WHAT [--query Q] [--why W] [--next N] [--origin LABEL]` | Semantic snapshot. Auto-attaches to active intent; if multiple, re-run with `--intent ID`. |

### Decision

| Command | What it does |
|---|---|
| `itt decision create WHAT [--query Q] [--why W] [--origin LABEL]` | New decision (auto-attaches active intents; `origin` auto-filled from env) |
| `itt decision deprecate ID [--reason TEXT]` | `active` → `deprecated` (terminal); `--reason` records why |

### Hub

| Command | What it does |
|---|---|
| `itt hub start [--port PORT] [--no-open]` | Launch IntHub Local (runs from any directory) |
| `itt hub link [--project-name NAME] [--api-base-url URL] [--token TOKEN]` | Link current workspace to an IntHub project |
| `itt hub sync [--api-base-url URL] [--token TOKEN] [--dry-run]` | Push local semantic history + Git context to IntHub |

Hub does **not** replace local commands. First record locally, then sync.

## JSON output contract

**Success:**
```json
{"ok": true, "action": "snap.create", "result": {...}, "warnings": []}
```

`action` values: `intent.create`, `intent.activate`, `intent.suspend`, `intent.done`, `snap.create`, `decision.create`, `decision.deprecate`, `version`, `init`, `doctor`, `hub.start`, `hub.link`, `hub.sync`.

**`inspect`** is different: top-level `ok`, `active_intents`, `active_decisions`, `suspended`, `warnings` (no `action`/`result` envelope).

**Error:**
```json
{"ok": false, "error": {"code": "ERROR_CODE", "message": "...", "suggested_fix": "itt ..."}}
```

When `suggested_fix` is present, follow it.

Error codes: `NOT_INITIALIZED`, `ALREADY_EXISTS`, `GIT_STATE_INVALID`, `STATE_CONFLICT`, `OBJECT_NOT_FOUND`, `INVALID_INPUT`, `NO_ACTIVE_INTENT`, `MULTIPLE_ACTIVE_INTENTS`, `NO_SUSPENDED_INTENT`, `MULTIPLE_SUSPENDED_INTENTS`, `HUB_NOT_CONFIGURED`, `NOT_LINKED`, `PROVIDER_UNSUPPORTED`, `NETWORK_ERROR`, `SERVER_ERROR`.

**`doctor`:** `result.healthy` (bool) + `result.issues[]` with codes: `MISSING_REFERENCE`, `BROKEN_LINK`, `INVALID_STATUS`, `OBJECT_TYPE_MISMATCH`.

## Storage

```
.intent/
  hub.json                 # local IntHub access + workspace binding
  intents/intent-001.json
  snaps/snap-001.json
  decisions/decision-001.json
```

IDs are zero-padded to 3 digits, auto-incremented per type.
