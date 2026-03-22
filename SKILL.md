---
name: intent-cli
description: Track what you're doing and why with structured semantic history (.intent/) — goals, decisions, and work state that persist across agent sessions.
---

# Intent — semantic history

This repo uses Intent (`.intent/`) to track what you're doing and why.
Install: `git clone https://github.com/dozybot001/Intent.git && cd Intent && pip install .`

Structured `itt` command outputs are JSON — parse them, don't guess. `argparse` help and usage text are not JSON.

## Why this matters

Git records how code changes. It does not record why you're changing it, what you tried, how the user reacted, or which decisions are still in effect.

Intent does not replace Git; it supplies the semantic layer Git lacks. Git records how code changes. Intent should only capture the goal-level semantics Git cannot independently preserve for recovery: why this work exists, what state it reached, and what should happen next.

These semantics already exist — scattered across commit messages, PR discussions, chat, and agent conversations. The problem is not missing information but **missing stable object boundaries**: they can be read but not reliably tracked, referenced, or queried by the next session. Intent gives them formal object status.

In agent-driven development, the central activity is no longer "writing code" — it is **guiding, connecting, and crystallizing**: proposing goals, progressing toward them, correcting course based on feedback, and distilling long-lived decisions. Recording these objects is not overhead on top of your work — it **is** part of the work.

Intent serves two linked purposes:

- **Operational recovery** — a new agent session can run `itt inspect` and resume work without the user re-explaining anything
- **Product formation history** — future sessions can understand how the product, workflow, or design direction was gradually shaped

`itt inspect` is optimized for the first purpose. The semantic history as a whole should satisfy both.

## Core concepts

### Three objects

- **Intent** = a goal you identified from a user query. Not a task, not a ticket — a goal. "Fix the login timeout bug", not "Change line 42 in config.py". Multiple intents can be active simultaneously. The `query` field preserves the original user words that led you to recognize this goal. The `why` field captures **why** this goal matters — fill it when the user's query contains explanatory context (e.g. "users on slow networks get logged out"), leave it `""` otherwise.

- **Snap** = a semantic snapshot under an intent, aligned to a user query. It captures what was done (`what`), why (`why`), what's next (`next`), and the user query that triggered it (`query`). The AI already thinks before acting; snap just makes that thinking survive the session boundary. This is not extra documentation — it externalizes reasoning that already exists in context but would be lost when the session ends.

- **Decision** = the highest-level object. A long-lived choice that outlives any single intent and constrains future work. "Timeout must stay configurable", "All API responses use envelope format". Decisions carry `why` — why this was decided. Active decisions auto-attach to every new intent, ensuring future work inherits these constraints. **The test:** would a future intent on a different problem still need to respect this? If yes → decision. If it only matters for the current intent → record it in a snap why instead.

### Relationships

All relationships are **bidirectional** and **append-only**:
- Creating an intent auto-attaches all active decisions (both sides updated)
- Creating a decision auto-attaches all active intents (both sides updated)
- No detach — to retire a decision, deprecate it

### Immutability

Objects are **immutable after creation**. Correct mistakes by writing a new snap.

## Workflow

### 0. First time

If `.intent/` does not exist, run `itt init`.

### 1. Session start — inspect and recover

**Every session begins with `itt inspect`.** This is not optional.

```bash
itt inspect
```

Then act on what you find:

1. **Read `active_intents` first.** Continue from each intent's `latest_snap`. If `latest_snap` is `null`, use the intent `what` plus the current user request as the recovery boundary. Do not ask the user to re-explain.
2. **Read `active_decisions` next.** These are standing constraints. Respect them throughout the session.
3. **Check `suspended`.** Mention suspended work if relevant, or reactivate it when the current request clearly resumes it.
4. **Check `warnings`.** If warnings exist or the graph looks inconsistent, run `itt doctor` before acting.
5. **If everything is empty, treat it as a fresh workspace.** Create an intent only when the user's query implies a goal a future session may need to resume.

### 2. Recognize intents from user queries

**This is your job, not the user's.** The user will not say "create an intent." They will say "why does login timeout after 5s?" and it is your responsibility to recognize that this implies a goal — fixing the login timeout — and create the intent.

```bash
itt intent create "Fix the login timeout bug" \
  --query "why does login timeout after 5s?" \
  --why "users on slow networks get logged out mid-session"
```

When a new query arrives, determine which path applies:

1. Quick factual question with no follow-up work → respond directly, no objects
2. Falls under an already-active intent → snap under that intent
3. Relates to a suspended intent → activate it, then snap
4. Implies a new goal not covered by active intents → create a new intent, then snap

Before choosing path 4, apply the recovery test: **if a new agent session saw this in `itt inspect`, would it need this goal boundary to resume unfinished work or preserve an in-progress objective?** If no, do not create an intent.

If you are about to begin a meaningful code work chunk and no active intent explains the goal behind it, stop and create the intent first. Git will capture the diff; use Intent only when the next session would not be able to recover the goal or state from Git alone.

When in doubt, prefer semantic clarity over raw coverage. Requests to read a skill, learn a workflow, align on collaboration conventions, or discuss whether something should be recorded are usually **not** intents by themselves. Create an intent only when the query implies a concrete goal worth resuming across sessions.

Conversely, lack of code changes does **not** automatically mean "no intent". Documentation work, releases, migrations, investigations, or other non-code efforts can still be intents when they create a recoverable goal.

### 3. Create snaps after each query

After each user query, evaluate whether to create a snap. The evaluation follows three clear categories:

#### Category A: No snap

The query is a simple question, explanation, or clarification. No reasoning was formed that a future session would need. Examples: "what does this function do?", "explain this error message", "how does this API work?"

#### Category B: Snap with code changes

The query led to code changes. The snap captures what was done, why, and what's next. Git already records the diff; the snap records the semantics around it.

```bash
itt snap create "Timeout changed to 30s with async refresh" \
  --query "why does login timeout after 5s?" \
  --why "Race condition in refresh flow was blocking login synchronously. Async refresh decouples the paths." \
  --next "Token refresh endpoint still hardcoded 5s — separate service, needs its own fix."
```

#### Category C: Snap without code changes

The query did not produce code changes, but you formed conclusions that would require re-derivation in a future session. Three common situations:

1. **Investigation concluded** — you traced a bug, identified root cause, determined an approach, but haven't started coding yet
2. **Direction established** — you and the user discussed options, chose or rejected an approach for specific reasons
3. **Non-code work** — documentation, release, configuration, migration, design discussion that produced actionable conclusions

```bash
itt snap create "Root cause identified" \
  --query "why does login timeout after 5s?" \
  --why "Not a config issue — race condition in token refresh blocks login synchronously." \
  --next "Fix should be async refresh, not raising the timeout."
```

#### Snap fields

- `TITLE`: what was done — concise action description for scanning
- `--query`: the user query that triggered this snap
- `--why`: why — the reasoning behind this approach (required)
- `--next`: what comes next — remaining work, direction, blockers (optional)
- `--intent`: optional when exactly one intent is `active` (CLI infers it; check `warnings`). If several are `active`, omitting `--intent` returns `MULTIPLE_ACTIVE_INTENTS` with `error.details.candidates` — pick an `id` and re-run with `--intent`
- `origin`: stored automatically from the `itt` process environment. You do **not** need to pass `--origin` unless overriding
- Only `active` intents accept new snaps

### 4. Recognize and record decisions

Decisions are the highest-level object — they constrain future work beyond the current intent. **You must never create a decision without user involvement.** There are two paths:

#### Path A: User explicitly specifies

If the user's query contains `decision-[text]` or `决定-[text]`, treat it as an explicit decision request. Create the decision directly.

User says: "decision-所有 API 返回 envelope 格式" or "决定-所有 API 返回 envelope 格式" →

```bash
itt decision create "All API responses use envelope format" \
  --why "User-specified constraint"
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
  --why "Different deployments have different latency envelopes; hardcoding breaks staging and on-prem"
```

Active intents are auto-attached. The decision will also auto-attach to every future intent, ensuring the constraint is inherited.

### 5. Respect active decisions

When you start work, check `active_decisions` from inspect. These are not suggestions — they are standing constraints. Concrete behaviors:

- Before implementing, verify your approach doesn't violate any active decision
- If a user's new request conflicts with an active decision, say so: "This would conflict with decision-001: 'Timeout must stay configurable'. Should we proceed anyway and deprecate that decision?" If the user confirms, deprecate the old decision — then ask whether the new direction should also be recorded as a decision. A deprecated decision without a replacement leaves a gap: the next session sees the old constraint was removed but doesn't know what replaced it.
- If a decision no longer applies, deprecate it explicitly — don't silently ignore it

### 6. Context switching

```bash
itt intent suspend intent-001            # pause current work
itt intent create "Urgent: fix broken link" --query "..."  # handle interruption
itt snap create "Fixed link" --why "..."   # or --intent intent-002 when multiple active
itt intent done intent-002               # complete the fix
itt intent activate intent-001           # back to original; active decisions are caught up
```

### 7. Goal complete

```bash
itt intent done intent-001
```

`done` is terminal. Mark an intent done when the user confirms the goal is resolved, or when your last snap shows no remaining work (`next` is empty). If the same problem resurfaces, create a new intent.

### 8. IntHub sync (when this repo uses it)

`hub` commands do **not** replace local object commands. You still create intents, snaps, and decisions locally with `itt`. IntHub is the sync/share/read layer on top of that local semantic history.

Use them with this boundary:

- `itt hub start` launches IntHub Local from the cloned Intent repo source. Run it from the Intent repo directory — it detects `apps/inthub_local/` and starts the server on `http://127.0.0.1:7210` by default. The user must keep this running while using IntHub
- `itt hub link` configures local IntHub access when needed (`api_base_url` and optional token), then binds the current workspace to an IntHub project/workspace using GitHub repo context
- `itt hub sync` pushes the current local semantic graph and Git context to IntHub

`itt hub sync` is not a substitute for creating local snaps. First record the semantic history locally; then sync it.

## Command reference

### Global

| Command | What it does |
|---|---|
| `itt init` | Create `.intent/` in current git repo |
| `itt inspect` | Resume-first recovery view — **start every session here** |
| `itt doctor` | Validate object graph structure and links when recovery looks inconsistent |
| `itt version` | Print version |

### Hub

| Command | What it does |
|---|---|
| `itt hub start [--port PORT] [--no-open]` | Launch IntHub Local from the cloned Intent repo directory (must be run from that directory) |
| `itt hub link [--project-name NAME] [--api-base-url URL] [--token TOKEN]` | Configure local IntHub access if needed, then link current workspace to an IntHub project/workspace |
| `itt hub sync [--api-base-url URL] [--token TOKEN] [--dry-run]` | Push local semantic history + Git context to IntHub |

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
| `itt snap create WHAT [--intent ID] [--query Q] [--why W] [--next N] [--origin LABEL]` | Semantic snapshot (`what` = what was done; `why` = why; `next` = what's next; `query` = user trigger) |

### Decision

| Command | What it does |
|---|---|
| `itt decision create WHAT --why W [--query Q] [--origin LABEL]` | New decision (auto-attaches active intents; `origin` auto-filled from env) |
| `itt decision deprecate ID [--reason TEXT]` | `active` → `deprecated` (terminal); `--reason` records why and/or what replaced it |
There are no `show` commands. For resume, use `itt inspect`. For browsing, use IntHub.

## State machines

**Intent:** `active` → `suspend` → `active` → `done`
**Snap:** no state transitions; immutable after creation, correct via a later snap
**Decision:** `active` → `deprecated`

Terminal states like `done` and `deprecated` cannot be undone. Create a new object instead.

## Writing good snaps

A snap has four fields that carry meaning:

| Field | Carries | Example |
|---|---|---|
| `query` | **User's trigger** | "why does login timeout after 5s?" |
| `what` | **What was done** | "Timeout changed to 30s with async refresh" |
| `why` | **Why** | "Race condition in refresh flow blocks login synchronously. Async refresh decouples the paths." |
| `next` | **What's next** | "Token refresh endpoint still hardcoded — separate service, needs its own fix." |

`what` is the action line — scannable, concise. `why` is the reasoning — why this approach, what was discovered. `next` is the direction — remaining work, blockers. Don't dump terminal output, diffs, or command sequences. Capture the thinking, not the mechanics.

Bad `what`: `"Fixed timeout"` — what was actually done?
Good `what`: `"Timeout changed to 30s with async refresh"` — clear action.

Bad why: `"Changed config.py line 42 from 5 to 30"` — that's the diff, not the reasoning.
Good why: `"Race condition in refresh flow blocks login synchronously. Async refresh decouples the paths."` — clear reasoning.

## When to create what

| Signal | Action |
|---|---|
| User's query implies a recoverable goal not covered by active intents | `itt intent create` |
| You are about to make a code change and no active intent explains it | `itt intent create` before editing |
| Non-code work still creates a recoverable goal (docs, release, migration, investigation) | `itt intent create` |
| Query led to code changes under an active intent | `itt snap create` (record the reasoning behind the changes) |
| Query led to conclusions worth preserving but no code changes (investigation, direction, non-code work) | `itt snap create` (record the conclusions and reasoning) |
| User query contains `decision-[text]` | `itt decision create` directly |
| A choice emerges that should constrain future work | Ask user first, then `itt decision create` if confirmed |
| Switching to a different problem | `itt intent suspend` + new intent |
| Goal is fully resolved | `itt intent done` |
| A past decision no longer applies | `itt decision deprecate` |
| `doctor` shows broken or missing decision ↔ intent links | Stop and inspect `.intent/` data or dedicated repair tooling; there is no public `attach` happy-path command |

## When NOT to create objects

Intent records **only what's worth formally tracking, linking, and reusing across sessions**. Not everything deserves object status.

- Trivial factual questions ("what does this function do?") — no intent, no snap
- Requests to read a skill, understand a workflow, or align on collaboration conventions — do the work, but don't create an intent unless they imply a separate goal that future sessions may need to resume
- Meta-discussion about whether an intent/snap/decision should exist — usually no new intent; correct existing history if needed
- Queries fully satisfied in the current turn that leave no unfinished goal for the next session — no intent
- Implementation details that won't matter next session — not a decision
- A choice that only affects the current intent — snap it, don't decision it
- If recording it wouldn't help the next session recover, continue, or understand why the product took its current shape — skip it

## Anti-patterns

- **Waiting for the user to say "create an intent"** — intent recognition is your job. The user describes a problem; you recognize the goal.
- **Ignoring inspect** — always start with `itt inspect`. It's the single source of truth for recovery.
- **Ignoring active decisions** — they are constraints, not suggestions. Check them before implementing.
- **Intent per task** — one intent per goal, not per step. "Migrate auth to JWT", not "Add JWT token generation".
- **Intent for workflow familiarization** — reading a skill, learning the tooling, or agreeing to use Intent in future turns does not by itself create a cross-session goal.
- **Using code changes as the only test for intent** — code edits are a strong signal that an intent must exist, but non-code recoverable goals can require intents too.
- **Vague summaries** — "fixed it" tells the next session nothing. Capture the reasoning: why this approach, what was discovered, what conclusion was reached.
- **Snapping simple Q&A** — if the query was a factual question or explanation with no reasoning to persist, skip the snap.
- **Summary as execution log** — don't dump commands or diffs. Capture the thinking, not the mechanics.
- **Trying to update objects** — objects are immutable after creation. Correct mistakes in the next snap.
- **Decisions as snaps** — if a choice outlives the current intent, it should be a decision. Propose it to the user; don't silently bury it in a snap why.
- **Creating decisions without user involvement** — decisions require either explicit user specification (`decision-[text]`) or user confirmation after you propose. Never create a decision on your own judgment alone.
- **Forgetting to done** — stale active intents pollute `inspect` and auto-attach to unrelated decisions.

## Quality check

Judge your Intent usage by outcomes, not compliance:

- Could a new session run `itt inspect` and continue without the user re-explaining?
- For code work that requires semantic recovery, can the next session trace it to the relevant intent and snaps?
- Do your snap summaries capture reasoning (why), not just mechanics (what)?
- Are active decisions actually constraining your implementation choices?
- Could someone later understand why the product, workflow, or design direction became what it is — not just how to continue coding?
- Would a human reading `inspect` output understand what's in progress and why?

If the answers are no, your objects are formally correct but semantically empty. Fix the content, not the process.

## JSON output contract

**Success** (all commands except `inspect`): responses use the envelope below. The `action` field is a **dot-separated** operation id (not the raw argv).

```json
{"ok": true, "action": "snap.create", "result": {...}, "warnings": []}
```

Typical `action` values: `version`, `init`, `doctor`, `intent.create`, `intent.activate`, `intent.suspend`, `intent.done`, `snap.create`, `decision.create`, `decision.deprecate`, `hub.start`, `hub.link`, `hub.sync`.

**`inspect`** is different: it returns top-level `ok`, `active_intents`, `active_decisions`, `suspended`, and `warnings` (no `action` / `result` envelope).

**Error:**
```json
{"ok": false, "error": {"code": "ERROR_CODE", "message": "...", "suggested_fix": "itt ..."}}
```

Optional: `details` (object). When `suggested_fix` is present, follow it.

**Error codes (CLI / client):** `NOT_INITIALIZED`, `ALREADY_EXISTS`, `GIT_STATE_INVALID`, `STATE_CONFLICT`, `OBJECT_NOT_FOUND`, `INVALID_INPUT`, `NO_ACTIVE_INTENT`, `MULTIPLE_ACTIVE_INTENTS`, `NO_SUSPENDED_INTENT`, `MULTIPLE_SUSPENDED_INTENTS`, `HUB_NOT_CONFIGURED`, `NOT_LINKED`, `PROVIDER_UNSUPPORTED`, `NETWORK_ERROR`, `SERVER_ERROR`.

**`doctor`:** success envelope with `result.healthy` and `result.issues[]`; each issue has its own `code` (e.g. `SCHEMA_VERSION_MISMATCH`, `MISSING_REFERENCE`, `BROKEN_LINK`, `INVALID_STATUS`, `OBJECT_TYPE_MISMATCH`).

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
