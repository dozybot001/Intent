---
name: intent-cli
description: Record semantic history (.intent/) — goals, snapshots, and decisions that persist across agent sessions. Triggered when user asks to record semantics.
---

# Intent — semantic recording guide

This repo uses Intent (`.intent/`) to record semantic history: **what you did and why**, structured as formal objects that survive context loss across sessions and agents.

`itt` commands output JSON — parse them, don't guess.

## When this activates

- User invokes `/intent-cli`
- User says "记录语义", "record what we did", "记录一下", or similar

## Recording flow

Recording is **retrospective**. You look back at the work **from the last semantic recording to now** and summarize. This ensures semantic continuity — each recording picks up exactly where the previous one left off.

1. Run `itt inspect` to check current state (active intents, decisions, suspended work)
2. Create **one intent** — the goal of this interaction
3. Create **snaps** — one per meaningful milestone
4. Identify **decisions** — long-lived constraints worth formalizing (requires user confirmation)
5. `itt intent done` — if the goal is fully resolved

```bash
itt intent create "Implemented auth retry logic" \
  --why "users on slow networks were getting logged out"
itt snap create "Added exponential backoff to API client" \
  --why "transient 503s from upstream caused cascading failures"
itt snap create "Updated error handling in login flow" \
  --why "old handler swallowed retry errors silently"
itt intent done
```

## Writing high-quality semantics

Every object has two core fields: **`what`** (concise action/theme) and **`why`** (reasoning).

### Intent: `what` + `why`

- `what`: one sentence summarizing the goal — **not** a step, not a file name
- `why`: the context or motivation behind the goal

| Good | Bad |
|------|-----|
| "Migrate auth middleware to JWT" | "Update auth.py" |
| "Fix cascading timeout on slow networks" | "Fix bug" |

**One intent per recording, not per step.** A recording session typically produces exactly one intent.

### Snap: `what` + `why`

A snap is a **milestone** — a meaningful chunk of completed work under the intent.

- `what`: what was done, scannable in a list
- `why`: why this approach was chosen, not a restatement of what

| Good | Bad |
|------|-----|
| what: "Added retry with exponential backoff" | what: "Modified api_client.py lines 42-78" |
| why: "Linear retry overwhelmed the upstream during recovery" | why: "Because we needed retries" |

### Snap boundary judgment

```
Ask: "If I removed this snap, would the intent's story have a gap?"
  Yes → keep it as a snap
  No  → too granular, merge into another snap or skip
```

Rules of thumb:
- **Snap it**: architectural choice, non-obvious trade-off, significant code change, a conclusion from investigation
- **Skip it**: routine edits, formatting, dependency bumps, trivial fixes that need no explanation

### Decision: `what` + `why`

A decision is a **long-lived constraint** that outlives the current intent.

**The test:** would a future intent on a completely different problem still need to respect this? Yes → decision. No → it's just a snap.

| Decision | Not a decision (snap it) |
|----------|--------------------------|
| "All API responses must include request_id for tracing" | "Added request_id to the auth endpoint response" |
| "SKILL must be self-contained — agent reads only SKILL" | "Rewrote SKILL to clarify the recording flow" |

**Never create a decision without user involvement.**

| Path | Trigger | Action |
|------|---------|--------|
| Explicit | User says `decision-[text]` or `决定-[text]` | Create directly |
| Discovered | You spot a long-lived constraint | Ask: "Should I record this as a decision?" → create only after confirmation |

If a user request conflicts with an active decision, say so and ask whether to deprecate.

## Session recovery

When activated, always run `itt inspect` first:

1. **Active intents** → continue from `latest_snap`, don't ask user to re-explain
2. **Active decisions** → respect them as standing constraints
3. **Suspended intents** → mention if relevant
4. **Warnings** → run `itt doctor`
5. **Everything empty** → fresh workspace

## Key rules

- **Recording is user-initiated** — like git commit, only when asked
- **One intent per recording** — summarize the goal, not each step
- **Snap reasoning, not mechanics** — capture why, not diffs
- **Decisions require user confirmation** — never create on your own judgment
- **Always `done` completed intents** — stale intents pollute inspect
- **Decision hygiene** — when `active_decisions > 20`, prompt: "当前有 N 条 active decision，要做一轮清理吗？"

## Objects

| Object | Fields | States |
|--------|--------|--------|
| **Intent** | `what`, `why`, `snap_ids[]`, `decision_ids[]` | `active` → `suspend` ↔ `active` → `done` |
| **Snap** | `what`, `why`, `intent_id` | Immutable |
| **Decision** | `what`, `why`, `intent_ids[]`, `reason` | `active` → `deprecated` |

All objects also carry: `id`, `object`, `created_at`, `origin` (auto-detected).

Relationships are **bidirectional** and **append-only**. Objects are **immutable** after creation — correct via new snap.

## Command reference

### Global

| Command | What it does |
|---|---|
| `itt init` | Create `.intent/` in current git repo |
| `itt inspect` | Recovery view — start every recording here |
| `itt doctor` | Validate object graph |
| `itt version` | Print version |

### Intent

| Command | What it does |
|---|---|
| `itt intent create WHAT [--why W]` | New intent (auto-attaches active decisions) |
| `itt intent activate [ID]` | `suspend` → `active` (catches up decisions; infers ID when unique) |
| `itt intent suspend [ID]` | `active` → `suspend` (infers ID when unique) |
| `itt intent done [ID]` | `active` → `done` (infers ID when unique) |

### Snap

| Command | What it does |
|---|---|
| `itt snap create WHAT [--why W]` | Semantic snapshot (auto-attaches to active intent; `--intent ID` if multiple) |

### Decision

| Command | What it does |
|---|---|
| `itt decision create WHAT [--why W]` | New decision (auto-attaches active intents) |
| `itt decision deprecate ID [--reason TEXT]` | `active` → `deprecated` |

### Hub

| Command | What it does |
|---|---|
| `itt hub start [--port PORT] [--no-open]` | Launch IntHub Local |
| `itt hub link [--project-name NAME] [--api-base-url URL]` | Link workspace to IntHub |
| `itt hub sync [--dry-run]` | Push semantic history to IntHub |

## JSON output

**Success:** `{"ok": true, "action": "...", "result": {...}, "warnings": []}`

**Inspect:** `{"ok": true, "active_intents": [], "active_decisions": [], "suspended": [], "warnings": []}`

**Error:** `{"ok": false, "error": {"code": "...", "message": "...", "suggested_fix": "itt ..."}}`

When `suggested_fix` is present, follow it.
