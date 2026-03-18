---
name: intent-cli
description: Track what you're doing and why with structured semantic history (.intent/) — goals, decisions, and work state that persist across agent sessions.
---

# Intent — semantic history

This repo uses Intent (`.intent/`) to track what you're doing and why.
Install: `pipx install intent-cli-python`

All `itt` output is JSON — parse it, don't guess.

## Why this matters

Every new agent session starts from zero — the reasoning, rejected approaches, and half-finished work are all gone. Intent solves this: `itt inspect` gives you the active goal, the last step taken, active decisions, and a rationale that tells you exactly where to pick up. The entire design serves one purpose: **cross-session recovery without re-explanation**. Everything below — how to write snaps, how to record decisions, when to suspend — exists to make that recovery seamless.

## Workflow

0. **First time** → if `.intent/` does not exist, run `itt init` to initialize
1. **Session start** → run `itt inspect` to check workspace state
   - **active** → read the intent, latest snap rationale, and active decisions — continue where it left off
   - **suspended intents** → consider `itt resume [id]`
   - **idle** → `itt start "<goal>"` if this session involves substantive work
2. **Begin substantive work** → `itt start "What goal am I pursuing"`
   - An intent is a goal, not a task — keep it high-level
   - Skip for trivial questions or tiny edits
3. **Before each git commit** → `itt snap "What I did" -m "Why, and what comes next"`
   - Snap before commit, not after — this is the key trigger point
4. **Record a cross-cutting decision** → `itt decide "Use JWT for auth" -m "Evaluated SAML, OAuth, JWT — JWT fits our stateless API"`
5. **Switching context** → `itt suspend`, then `itt start` or `itt resume`
6. **Goal complete** → `itt done`

## Object semantics

- **Intent** = a goal, not a task. One intent may span multiple snaps and commits.
  Title answers: "What problem am I solving?"
  Example: "Migrate auth to JWT", not "Add JWT token generation".
  An intent carries `decision_ids` — the list of decisions attached during its lifetime.
- **Snap** = a step taken toward the intent. Title answers: "What did I do?"
  Each snap is a recovery point — a future session can read it and understand where work stands.
  Status is `active` (current) or `reverted` (undone).
- **Decision** = a cross-cutting choice that outlives any single intent. Title answers: "What did we decide?"
  Decisions are created from an intent (`created_from_intent_id`) and carry `intent_ids` — every intent they've been attached to.
  Status is `active` (in effect) or `deprecated` (superseded or abandoned).
  Example: "Use PostgreSQL for persistence", "All API responses use envelope format".
- **Rationale** (`-m`) = the most valuable field. It is the bridge between sessions.
  It must give the next session everything it needs to continue without re-explaining. Include:
  - What's done, what's in progress, what's remaining
  - Decisions made and why
  - Strategic context (constraints, deadlines, dependencies)

## Complete command reference

### init — initialize

```
itt init
```

Creates `.intent/` directory with `config.json`, `state.json`, `intents/`, `snaps/`, `decisions/`.
Fails if `.intent/` already exists or not in a Git worktree.

### start — begin a new intent

```
itt start "Fix the login timeout bug"
```

Creates and activates a new intent with status `open`. Only one intent can be open at a time.
Fails if an intent is already open — use `itt done` or `itt suspend` first.

Returns `attached_decisions` — all active decisions are automatically attached to the new intent.

### snap — record a step

```
itt snap "Increase timeout to 30s" -m "Default 5s was too short for slow networks"
```

- **title** (required) — what was done
- **-m, --message** (optional) — rationale (why, and what comes next)

Snap status is `active` by default.

Each snap automatically captures git context: branch, HEAD, working tree status, and linkage quality.

### revert — undo the latest active snap

```
itt revert
itt revert -m "Approach caused regression in tests"
```

Changes the latest active snap from `active` → `reverted`.
Fails if no active snap exists in the active intent.

### decide — record a cross-cutting decision

```
itt decide "Use PostgreSQL for persistence"
itt decide "All API responses use envelope format" -m "Evaluated flat vs envelope — envelope supports pagination metadata"
```

- **title** (required) — what was decided
- **-m, --message** (optional) — rationale for the decision

Creates a decision with status `active`. The decision is linked to the current intent via `created_from_intent_id` and added to the intent's `decision_ids`.
Fails if no intent is currently active.

### deprecate — retire an active decision

```
itt deprecate                                    # auto-selects if exactly one active decision
itt deprecate decision-002                       # by ID
itt deprecate decision-002 -m "Switched to MySQL after benchmarking"
```

Changes a decision from `active` → `deprecated`.
Fails if no active decisions exist, or multiple active decisions exist without specifying an ID.

### suspend — pause current work

```
itt suspend
```

Intent status: `open` → `suspended`. Workspace becomes `idle`.
Use this when you need to handle an interruption without losing context.

### resume — continue suspended work

```
itt resume                   # auto-selects if exactly one suspended intent
itt resume intent-001        # by ID
```

Intent status: `suspended` → `open`. Workspace becomes `active`.
Fails if an intent is already active, or multiple suspended intents exist without specifying an ID.

Returns `attached_decisions` — catches up on any decisions created while the intent was suspended, attaching all currently active decisions.

### done — complete the goal

```
itt done                     # closes the active intent
itt done intent-001          # closes a specific intent by ID
```

Intent status → `done`. Workspace becomes `idle`.

### inspect — read workspace state (most important read command)

```
itt inspect
```

Returns a flat JSON snapshot of the entire workspace. This is the primary way to understand current state. Example output:

```json
{
  "ok": true,
  "schema_version": "0.3",
  "workspace_status": "active",
  "intent": { "id": "intent-001", "title": "Fix login timeout", "status": "open", "decision_ids": ["decision-001"] },
  "latest_snap": { "id": "snap-002", "title": "Increase timeout to 30s", "status": "active", "rationale": "Default 5s was too short" },
  "active_decisions": [{ "id": "decision-001", "title": "Use 30s as default timeout", "status": "active" }],
  "suspended_intents": [],
  "suggested_next_action": { "command": "itt snap '...'", "reason": "Intent is active." },
  "git": { "branch": "main", "head": "a1b2c3d", "working_tree": "clean" },
  "warnings": []
}
```

When idle: `intent` and `latest_snap` are `null`, `suggested_next_action` recommends `itt start` (or `itt resume` if suspended intents exist).

### list — list objects

```
itt list intent              # all intents, newest first
itt list snap                # all snaps, newest first
itt list snap --intent intent-001  # snaps for a specific intent
itt list decision            # all decisions, newest first
```

### show — show a single object

```
itt show intent-001
itt show snap-003
itt show decision-001
```

Object type is inferred from the ID prefix.

### version

```
itt version
```

## Suspend/resume (context switching without loss)

Real work isn't linear. When interrupted, suspend preserves the full recovery chain — the intent, all snaps, and their rationale stay intact. When resumed, `itt inspect` returns the same state as before the interruption (plus any new decisions), so the agent picks up exactly where it left off.

```
itt suspend                          # pause current intent
itt start "Urgent: fix broken link"  # handle interruption
itt snap "Fixed link" -m "Was a relative path issue"
itt done                             # complete the fix
itt resume                           # back to original work, context preserved
```

**Critical:** snap a good rationale before suspending. That rationale is what the future `resume` session will read to reconstruct context.

## State machine

### Intent lifecycle

```
open → done
open → suspended → open → done
```

### Snap lifecycle

```
active → reverted
```

### Decision lifecycle

```
active → deprecated
```

### Workspace status (derived, not set manually)

| Status   | Condition        |
| -------- | ---------------- |
| `idle`   | No active intent |
| `active` | One open intent  |

## JSON output contract

### Success

```json
{
  "ok": true,
  "action": "<command-name>",
  "result": { ... },
  "warnings": []
}
```

Exception: `inspect` returns a flat structure (no `action`/`result` wrapper).

### Error

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

### Exit codes

| Code | Meaning              |
| ---- | -------------------- |
| 0    | Success              |
| 1    | General failure      |
| 2    | Invalid input        |
| 3    | State conflict       |
| 4    | Object not found     |

### Error codes

| Code                | When                                             |
| ------------------- | ------------------------------------------------ |
| `NOT_INITIALIZED`   | `.intent/` does not exist — run `itt init`       |
| `ALREADY_EXISTS`    | `init` called when `.intent/` already exists     |
| `GIT_STATE_INVALID` | Not inside a Git worktree                        |
| `STATE_CONFLICT`    | Intent already open, no active intent, etc.      |
| `OBJECT_NOT_FOUND`  | ID does not resolve to a stored object           |
| `INVALID_INPUT`     | Bad arguments or conflicting flags               |

When an error includes `suggested_fix`, follow it.

## Git context in snaps

Each snap captures:

```json
{
  "branch": "main",
  "head": "a1b2c3d",
  "working_tree": "clean",
  "linkage_quality": "stable_commit"
}
```

| linkage_quality        | Meaning                           |
| ---------------------- | --------------------------------- |
| `stable_commit`        | Clean tree, HEAD resolved         |
| `working_tree_context` | Dirty tree or HEAD unresolved     |
| `explicit_ref`         | User-supplied ref was resolved    |

## Writing good rationale (the key to cross-session recovery)

The rationale is the single most important field in Intent. A new agent session runs `itt inspect`, reads the latest snap's rationale, and must be able to continue autonomously. If the rationale doesn't contain enough, the session falls back to asking the human — defeating the purpose.

**The test:** if a new agent session starts with zero context, can it read this rationale and know exactly what to do next?

**A rationale must answer three questions:**
1. **What's done?** — completed work the next session should not redo
2. **What's next?** — the immediate next step or remaining work
3. **Why this way?** — decisions made, constraints, context that shapes future choices

Bad: `"Increased timeout"`
— Next session knows nothing: what was the old value? Is there more to do? Why was this change needed?

Good: `"Increased default timeout from 5s to 30s. Login flow now works on slow networks. Still need to add retry logic for the token refresh endpoint. Constraint: must stay backward-compatible with v2 API clients."`
— Next session knows: timeout is done, retry logic is next, and there's a compatibility constraint to respect.

**For progress snaps on multi-step work**, capture the full strategic picture:
- Bad: `"Phase 1 done, starting phase 2"`
- Good: `"Phase 1 (PyPI publish) complete — package is intent-cli-python v0.5.0. Phase 2 is HN launch: need Show HN post + README polish. Phase 3 is agent platform integrations (Claude skill, Cursor rules). Deadline: launch before weekend."`

## Storage layout

```
.intent/
  config.json           # {"schema_version": "0.3"}
  state.json            # workspace state
  intents/
    intent-001.json     # one file per intent
  snaps/
    snap-001.json       # one file per snap
  decisions/
    decision-001.json   # one file per decision
```

IDs are zero-padded to 3 digits, auto-incremented per type: `intent-001`, `snap-001`, `decision-001`.

## Anti-patterns to avoid

- **Too many intents** — one intent per goal, not per task. Don't create an intent for every small change.
- **Vague rationale** — "fixed it" tells the next session nothing. Capture the full picture.
- **Snap after commit** — snap before commit; the snap captures the intent behind the commit.
- **Ignoring inspect** — always start a session with `itt inspect`. It tells you what's in flight.
- **Forgetting to done** — close intents when complete. Stale open intents create confusion.
- **Decisions as snaps** — if a choice outlives the current intent, use `itt decide`, not a snap. Decisions persist across intents.
- **Ignoring active decisions** — check `active_decisions` in inspect output. They represent constraints the current work must respect.
