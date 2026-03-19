---
name: intent-cli
description: Track what you're doing and why with structured semantic history (.intent/) — goals, decisions, and work state that persist across agent sessions.
---

# Intent — semantic history

This repo uses Intent (`.intent/`) to track what you're doing and why.
Install: `pip install intent-cli-python`

All `itt` output is JSON — parse it, don't guess.

## Why this matters

Git records how code changes. It does not record why you're changing it, what you tried, how the user reacted, or which decisions are still in effect.

Intent does not replace Git; it supplies the semantic layer Git lacks. At minimum, every code-changing line of work should be explainable by an intent and its snaps, so the next session can recover not just the diff but the goal behind it.

These semantics already exist — scattered across commit messages, PR discussions, chat, and agent conversations. The problem is not missing information but **missing stable object boundaries**: they can be read but not reliably tracked, referenced, or queried by the next session. Intent gives them formal object status.

In agent-driven development, the central activity is no longer "writing code" — it is **guiding, connecting, and crystallizing**: proposing goals, progressing toward them, correcting course based on feedback, and distilling long-lived decisions. Recording these objects is not overhead on top of your work — it **is** part of the work.

Intent exists for one purpose: **a new agent session can run `itt inspect` and resume work without the user re-explaining anything.** If that doesn't happen, Intent isn't working. Every behavior described below serves this goal.

## Core concepts

### Three objects

- **Intent** = a goal you identified from a user query. Not a task, not a ticket — a goal. "Fix the login timeout bug", not "Change line 42 in config.py". Multiple intents can be active simultaneously. The `source_query` field preserves the original user words that led you to recognize this goal. The `rationale` field captures **why** this goal matters — fill it when the user's query contains explanatory context (e.g. "users on slow networks get logged out"), leave it `""` otherwise.

- **Snap** = one query-response interaction under an intent. Created for **every query** — not selectively. Records what the user asked (`query`), what you did (`summary`), and how the user reacted (`feedback`). If the user moves on without commenting, `feedback` stays `""`. The `rationale` field captures **why** this particular approach was chosen — fill it when the user explains their reasoning or when the choice is non-obvious, leave it `""` otherwise. Snaps are the recovery chain: a future session reads them to understand what happened.

- **Decision** = the highest-level object. A long-lived choice that outlives any single intent and constrains future work. "Timeout must stay configurable", "All API responses use envelope format". Decisions carry `rationale` — why this was decided. Active decisions auto-attach to every new intent, ensuring future work inherits these constraints. **The test:** would a future intent on a different problem still need to respect this? If yes → decision. If it only matters for the current intent → record it in a snap summary instead.

### Relationships

All relationships are **bidirectional** and **append-only**:
- Creating an intent auto-attaches all active decisions (both sides updated)
- Creating a decision auto-attaches all active intents (both sides updated)
- There is no detach. To retire a decision, deprecate it — existing links stay, only future auto-attach stops.

### Immutability

Objects are **immutable after creation**. There is no command to update a title, summary, query, or rationale. If you wrote something wrong, correct it in the next snap — don't try to rewrite history. The only exception: `snap feedback` overwrites the feedback field, because feedback is inherently delayed.

## Workflow

### 0. First time

If `.intent/` does not exist, run `itt init`.

### 1. Session start — inspect and recover

**Every session begins with `itt inspect`.** This is not optional.

```bash
itt inspect
```

Then act on what you find:

- **`active_intents` is non-empty** → Read each intent's `decision_ids` and `latest_snap_id`. Run `itt snap show <latest_snap_id>` to read the summary. That summary tells you what was done, what wasn't, and what to do next. Continue from there — do not ask the user to re-explain.

- **`suspend_intents` is non-empty** → The user may want to resume one. Mention what's suspended and ask, or activate it if the user's current query clearly relates.

- **`active_decisions` is non-empty** → These are standing constraints. Read them and respect them throughout this session. If the user's request conflicts with an active decision, flag the conflict before proceeding.

- **`recent_snaps` has entries** → Read summaries to see what was recently attempted, what remains unfinished, and how the user reacted — even across different intents.

- **Everything is empty** → Fresh workspace. Create an intent only when the user's query implies a goal a future session may need to resume.

- **`warnings` is non-empty or the graph looks inconsistent** → Run `itt doctor` before acting. `inspect` is the recovery view; `doctor` is the structural validator.

### 2. Recognize intents from user queries

**This is your job, not the user's.** The user will not say "create an intent." They will say "why does login timeout after 5s?" and it is your responsibility to recognize that this implies a goal — fixing the login timeout — and create the intent.

```bash
itt intent create "Fix the login timeout bug" \
  --query "why does login timeout after 5s?" \
  --rationale "users on slow networks get logged out mid-session"
```

When a new query arrives, determine which path applies:

1. Quick factual question with no follow-up work → respond directly, no objects
2. Falls under an already-active intent → snap under that intent
3. Relates to a suspended intent → activate it, then snap
4. Implies a new goal not covered by active intents → create a new intent, then snap

Before choosing path 4, apply the recovery test: **if a new agent session saw this in `itt inspect`, would it need this goal boundary to resume unfinished work or preserve an in-progress objective?** If no, do not create an intent.

If you are about to make a code change and no active intent explains why, stop and create the intent first. Git will capture the diff; Intent must capture the goal that made the diff happen.

When in doubt, prefer semantic clarity over raw coverage. Requests to read a skill, learn a workflow, align on collaboration conventions, or discuss whether something should be recorded are usually **not** intents by themselves. Create an intent only when the query implies a concrete goal worth resuming across sessions.

Conversely, lack of code changes does **not** automatically mean "no intent". Documentation work, releases, migrations, investigations, or other non-code efforts can still be intents when they create a recoverable goal.

### 3. Snap every query interaction

**Every user query that falls under an active intent produces a snap.** This is the atomic unit of interaction history. One query, one snap — no batching, no skipping.

```bash
itt snap create "Raise timeout to 30s" \
  --intent intent-001 \
  --query "login timeout still fails on slow networks" \
  --rationale "30s covers 99th-percentile latency without hurting UX" \
  --summary "Updated timeout config from 5s to 30s in config.py. Login test suite now passes. Token refresh endpoint still uses hardcoded 5s — tracked separately." \
  --feedback ""
```

- `--query`: the user's words this round
- `--rationale`: why this approach was chosen; fill when the user explains reasoning or the choice is non-obvious, `""` otherwise
- `--summary`: what you actually did — see §"Writing good summaries" below
- `--feedback`: user's reaction; `""` if they moved on without commenting
- Only `active` intents accept new snaps

### 4. Capture user feedback

If the user gives feedback after a snap was already created:

```bash
itt snap feedback snap-001 "works in staging, ship it"
```

This overwrites the previous value. One snap, one latest feedback.

### 5. Recognize and record decisions

Decisions are the highest-level object — they constrain future work beyond the current intent. **You must never create a decision without user involvement.** There are two paths:

#### Path A: User explicitly specifies

If the user's query contains `decision-[text]` or `决定-[text]`, treat it as an explicit decision request. Create the decision directly.

User says: "decision-所有 API 返回 envelope 格式" or "决定-所有 API 返回 envelope 格式" →

```bash
itt decision create "All API responses use envelope format" \
  --rationale "User-specified constraint"
```

#### Path B: Agent discovers, user confirms

Watch for these signals in conversation:

- The user states a preference or constraint: "we need to keep backward compatibility with v2"
- You and the user converge on an architectural choice: "let's use PostgreSQL for persistence"
- A policy emerges from discussion that seems to outlive the current intent

When you spot one, **do not create the decision directly**. Instead, ask the user:

> "This sounds like a long-term constraint that should apply to future work: 'Timeout must stay configurable'. Should I record it as a decision?"

Only create the decision after the user confirms:

```bash
itt decision create "Timeout must stay configurable" \
  --rationale "Different deployments have different latency envelopes; hardcoding breaks staging and on-prem"
```

Active intents are auto-attached. The decision will also auto-attach to every future intent, ensuring the constraint is inherited.

### 6. Respect active decisions

When you start work, check `active_decisions` from inspect. These are not suggestions — they are standing constraints. Concrete behaviors:

- Before implementing, verify your approach doesn't violate any active decision
- If a user's new request conflicts with an active decision, say so: "This would conflict with decision-001: 'Timeout must stay configurable'. Should we proceed anyway and deprecate that decision?" If the user confirms, deprecate the old decision — then ask whether the new direction should also be recorded as a decision. A deprecated decision without a replacement leaves a gap: the next session sees the old constraint was removed but doesn't know what replaced it.
- If a decision no longer applies, deprecate it explicitly — don't silently ignore it

### 7. Context switching

```bash
itt intent suspend intent-001            # pause current work
itt intent create "Urgent: fix broken link" --query "..."  # handle interruption
itt snap create "Fixed link" --intent intent-002 --summary "..." --query "..."
itt intent done intent-002               # complete the fix
itt intent activate intent-001           # back to original; active decisions are caught up
```

### 8. Goal complete

```bash
itt intent done intent-001
```

`done` is terminal. Mark an intent done when the user confirms the goal is resolved, or when your last snap summary shows no remaining work. If the same problem resurfaces, create a new intent.

### 9. IntHub sync (when this repo uses it)

`hub` commands do **not** replace local object commands. You still create intents, snaps, and decisions locally with `itt`. IntHub is the remote sync/share/read layer on top of that local semantic history.

Use them with this boundary:

- `itt hub login` configures local IntHub access (`api_base_url` and optional token) in `.intent/hub.json`
- `itt hub link` binds the current local workspace to an IntHub project/workspace using GitHub repo context
- `itt hub sync` pushes the current local semantic graph and Git context to IntHub

`itt hub sync` is not a substitute for creating local snaps. First record the semantic history locally; then sync it.

## Command reference

### Global

| Command | What it does |
|---|---|
| `itt init` | Create `.intent/` in current git repo |
| `itt inspect` | Full object graph snapshot — **start every session here** |
| `itt doctor` | Validate object graph structure and links when recovery looks inconsistent |
| `itt version` | Print version |

### Hub

| Command | What it does |
|---|---|
| `itt hub login --api-base-url URL [--token TOKEN]` | Configure local IntHub access in `.intent/hub.json` |
| `itt hub link [--project-name NAME] [--api-base-url URL] [--token TOKEN]` | Link current workspace to an IntHub project/workspace |
| `itt hub sync [--api-base-url URL] [--token TOKEN] [--dry-run]` | Push local semantic history + Git context to IntHub |

### Intent

| Command | What it does |
|---|---|
| `itt intent create TITLE --query Q [--rationale R]` | New intent (auto-attaches active decisions) |
| `itt intent list [--status S] [--decision ID]` | List intents (`active` / `suspend` / `done`), optionally filtered by decision |
| `itt intent show ID` | Full intent detail |
| `itt intent activate ID` | `suspend` → `active` (catches up on active decisions) |
| `itt intent suspend ID` | `active` → `suspend` |
| `itt intent done ID` | `active` → `done` (terminal) |

### Snap

| Command | What it does |
|---|---|
| `itt snap create TITLE --intent ID [--query Q] [--rationale R] [--summary S] [--feedback F]` | Record one interaction |
| `itt snap list [--intent ID] [--status S]` | List snaps |
| `itt snap show ID` | Full snap detail |
| `itt snap feedback ID TEXT` | Set or overwrite feedback (latest wins) |
| `itt snap revert ID` | `active` → `reverted` (terminal) |

### Decision

| Command | What it does |
|---|---|
| `itt decision create TITLE --rationale R` | New decision (auto-attaches active intents) |
| `itt decision list [--status S] [--intent ID]` | List decisions (`active` / `deprecated`), optionally filtered by intent |
| `itt decision show ID` | Full decision detail |
| `itt decision deprecate ID` | `active` → `deprecated` (terminal) |
| `itt decision attach ID --intent ID` | Manually link decision ↔ intent |

## State machines

**Intent:** `active` → `suspend` → `active` → `done`
**Snap:** `active` → `reverted`
**Decision:** `active` → `deprecated`

Terminal states (`done`, `reverted`, `deprecated`) cannot be undone. Create a new object instead.

## Writing good summaries

The `summary` on a snap is **the primary vehicle for cross-session recovery**. A future agent will read it and decide what to do next. Every summary must answer three questions:

1. **What's done?** — completed work the next session should not redo
2. **What's not done?** — remaining work or known gaps
3. **What context shapes the next step?** — constraints, blockers, decisions that matter

Bad: `"Fixed timeout"`
— Next session knows nothing. Was 5s changed to 30s or 60s? Is there more to fix? Why was this needed?

Good: `"Changed default timeout from 5s to 30s in config.py. Login flow now passes on slow networks. Token refresh endpoint still uses hardcoded 5s — needs separate fix. Must stay backward-compatible with v2 clients per decision-001."`
— Next session knows: what changed, what's left, and what constraint to respect.

`summary` is a concise summary, not a step-by-step execution log. Don't dump terminal output, file-level diffs, or command sequences. Capture the meaning, not the mechanics.

## When to create what

| Signal | Action |
|---|---|
| User's query implies a recoverable goal not covered by active intents | `itt intent create` |
| You are about to make a code change and no active intent explains it | `itt intent create` before editing |
| Non-code work still creates a recoverable goal (docs, release, migration, investigation) | `itt intent create` |
| You responded to a user query under an active intent | `itt snap create` |
| User query contains `decision-[text]` | `itt decision create` directly |
| A choice emerges that should constrain future work | Ask user first, then `itt decision create` if confirmed |
| User gives feedback on previous work | `itt snap feedback` |
| Switching to a different problem | `itt intent suspend` + new intent |
| Goal is fully resolved | `itt intent done` |
| A past decision no longer applies | `itt decision deprecate` |

## When NOT to create objects

Intent records **only what's worth formally tracking, linking, and reusing across sessions**. Not everything deserves object status.

- Trivial factual questions ("what does this function do?") — no intent, no snap
- Requests to read a skill, understand a workflow, or align on collaboration conventions — do the work, but don't create an intent unless they imply a separate goal that future sessions may need to resume
- Meta-discussion about whether an intent/snap/decision should exist — usually no new intent; correct existing history if needed
- Queries fully satisfied in the current turn that leave no unfinished goal for the next session — no intent
- Implementation details that won't matter next session — not a decision
- A choice that only affects the current intent — snap it, don't decision it
- If recording it wouldn't help the next session recover or continue — skip it

## Anti-patterns

- **Waiting for the user to say "create an intent"** — intent recognition is your job. The user describes a problem; you recognize the goal.
- **Ignoring inspect** — always start with `itt inspect`. It's the single source of truth for recovery.
- **Ignoring active decisions** — they are constraints, not suggestions. Check them before implementing.
- **Intent per task** — one intent per goal, not per step. "Migrate auth to JWT", not "Add JWT token generation".
- **Intent for workflow familiarization** — reading a skill, learning the tooling, or agreeing to use Intent in future turns does not by itself create a cross-session goal.
- **Using code changes as the only test for intent** — code edits are a strong signal that an intent must exist, but non-code recoverable goals can require intents too.
- **Vague summaries** — "fixed it" tells the next session nothing. Answer: what's done, what's not, what context matters.
- **Skipping snaps** — every query under an active intent gets a snap. Don't cherry-pick which interactions to record.
- **Trying to update objects** — objects are immutable after creation (except `snap feedback`). Correct mistakes in the next snap.
- **Decisions as snaps** — if a choice outlives the current intent, it should be a decision. Propose it to the user; don't silently bury it in a snap summary.
- **Creating decisions without user involvement** — decisions require either explicit user specification (`decision-[text]`) or user confirmation after you propose. Never create a decision on your own judgment alone.
- **Forgetting to done** — stale active intents pollute `inspect` and auto-attach to unrelated decisions.

## Quality check

Judge your Intent usage by outcomes, not compliance:

- Could a new session run `itt inspect` and continue without the user re-explaining?
- Can every code diff be traced back to an intent and the relevant snaps?
- Are your summaries written for the **next session's agent**, not as a log for the current one?
- Are active decisions actually constraining your implementation choices?
- Would a human reading `inspect` output understand what's in progress and why?

If the answers are no, your objects are formally correct but semantically empty. Fix the content, not the process.

## JSON output contract

**Success:**
```json
{"ok": true, "action": "<command>", "result": {...}, "warnings": []}
```

**Error:**
```json
{"ok": false, "error": {"code": "ERROR_CODE", "message": "...", "suggested_fix": "itt ..."}}
```

When an error includes `suggested_fix`, follow it.

**Error codes:** `NOT_INITIALIZED`, `ALREADY_EXISTS`, `GIT_STATE_INVALID`, `STATE_CONFLICT`, `OBJECT_NOT_FOUND`, `INVALID_INPUT`, `HUB_NOT_CONFIGURED`, `NOT_LINKED`, `NETWORK_ERROR`.

## Storage

```
.intent/
  config.json              # {"schema_version": "1.0"}
  hub.json                 # local IntHub access + workspace binding
  intents/intent-001.json
  snaps/snap-001.json
  decisions/decision-001.json
```

IDs are zero-padded to 3 digits, auto-incremented per type.
