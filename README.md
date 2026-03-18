English | [简体中文](https://github.com/dozybot001/Intent/blob/main/README.CN.md)

# Intent

> Git records code changes. Intent records why.

## The Problem

Agent-driven development produces code fast, but reasoning disappears between sessions. Every new session starts from zero — the agent doesn't know what problem was being solved, what was tried, or why a path was chosen.

## What's Missing

Git records *what* changed. Commit messages and comments add some context. But three things consistently fall through:

**Goal continuity.** Commits are isolated snapshots. There's no structure connecting five commits to one task, or saying "this is what we're trying to accomplish."

**Decision rationale.** Why JWT over cookies? Why 15-minute expiry? This rarely makes it into commit messages — and when it does, it's unstructured text that agents must parse and guess from.

**Work state.** `git status` can be clean while a task is half-done. The next session has no signal that work was interrupted or what comes next.

## The Solution

Intent adds a `.intent/` directory to your repository — structured, machine-readable metadata that captures semantic history alongside code history.

```
.git/    ← how code changed
.intent/ ← what you were doing and why
```

Two objects: **intent** (the goal) and **snap** (a step taken, with rationale). All JSON. Any agent platform can read it.

### What changes

**Without `.intent/`** — new agent session opens. It reads `git log` and source code. Understands what the code does *now*, but doesn't know the JWT migration was for compliance (might revert it), doesn't know the refresh token is intentionally incomplete, can't tell there's unfinished work. Asks: *"What would you like me to do?"*

**With `.intent/`** — new agent session opens. Runs `itt inspect`. Sees an active intent ("Migrate auth to JWT"), last snap ("Add refresh token — incomplete"), and rationale ("token rotation not done, security priority"). Says: *"I'll implement the token rotation next."*

The difference: 10 seconds of reading structured metadata vs. minutes of re-explaining context.

## Core Loop

```
start → snap → done
```

- `start` — open an intent (what problem you're solving)
- `snap` — record a snap (what you did and why)
- `done` — close when complete

## Example

```bash
pipx install git-intent
itt init                    # creates .intent/
itt start "Fix login timeout"
itt snap "Increase timeout to 30s" -m "5s too short for slow networks"
git add . && git commit -m "fix timeout"
itt done
```

## Why Not Just…

| Approach | What it does well | What falls through |
| --- | --- | --- |
| **Git commit messages** | Records what changed per commit | No goal structure across commits; rationale is afterthought; no work-in-progress state |
| **CLAUDE.md / .cursorrules** | Gives agents project-level instructions | Static — doesn't track active tasks, decisions, or progress; must be manually maintained |
| **TODO comments** | Marks incomplete work in-place | Scattered across files; no lifecycle; no rationale; agents must grep and guess priority |
| **Notion / Linear / Jira** | Rich project tracking for humans | External to the repo; agents can't read them without API integration; overhead is high for solo/agent workflows |
| **Agent memory** (e.g. Claude Code memory) | Persists user preferences across sessions | Tied to one platform; not versioned with code; not shareable across agents or teammates |
| **Ad-hoc context files** (e.g. `context.md`) | Quick, zero-tooling setup | No schema — every project invents its own format; no lifecycle management; grows stale silently |

**Intent occupies a specific gap**: structured, versioned, task-scoped context that lives *in the repo* and works across any agent platform.

- **Structured** — JSON objects with defined schema, not free text an agent must interpret
- **Task-scoped** — an intent has a lifecycle (`open → done`); snaps are ordered steps, not a pile of notes
- **Versioned** — `.intent/` is committed alongside code; `git blame` works on your decisions too
- **Platform-agnostic** — any agent that reads JSON can use it; no vendor lock-in
- **Minimal** — two objects (intent, snap), one CLI, zero dependencies; adds seconds to a workflow, not minutes

The closest alternative is writing a `context.md` by hand. Intent trades that flexibility for consistency: a schema agents can rely on without per-project prompt engineering.

## Where This Is Going

`.intent/` is a protocol, not just a tool.

1. **Agent memory** — agents read `.intent/` on startup, recover last session's context in seconds
2. **Context exchange** — `.intent/` becomes the standard way to hand off work between agent platforms
3. **Network effects** — when enough repos contain `.intent/`, new tooling emerges: intent-aware review, decision archaeology, semantic dashboards

## Install

**Users:**

```bash
pipx install git-intent
```

**Configure your agent:** Intent ships a ready-to-use skill file ([`SKILL.md`](SKILL.md)). Copy it into your agent's skill directory so it knows the Intent workflow:

```bash
# Claude Code
mkdir -p .claude/skills
curl -o .claude/skills/git-intent.md \
  https://raw.githubusercontent.com/dozybot001/Intent/main/SKILL.md
```

For other agents, adapt `SKILL.md` to your platform's instruction format.

**Contributors:**

```bash
git clone https://github.com/dozybot001/Intent.git
cd Intent
python3 ./itt   # dev entry point, no install needed
```

## Commands

| Command | Purpose |
| --- | --- |
| `itt init` | Initialize `.intent/` |
| `itt start <title>` | Open an intent |
| `itt snap <title> [-m why]` | Record a snap |
| `itt done` | Close the active intent |
| `itt inspect` | Machine-readable workspace snapshot |
| `itt list <intent\|snap>` | List objects |
| `itt show <id>` | Show a single object |
| `itt suspend` | Suspend the active intent |
| `itt resume [id]` | Resume a suspended intent |
| `itt adopt [id]` | Adopt a candidate snap |
| `itt revert` | Revert the latest snap |

## Documentation

- [CLI spec](https://github.com/dozybot001/Intent/blob/main/docs/cli.EN.md) — objects, commands, JSON output contract
- [Dogfooding](https://github.com/dozybot001/Intent/blob/main/docs/dogfooding.md) — how we built Intent with Intent
