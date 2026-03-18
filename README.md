# Intent CLI

[中文](README.CN.md) | English

Semantic history for agent-driven development. Records **what you did** and **why**.

Intent CLI gives AI agents a structured way to track goals, interactions, and decisions across sessions. Instead of losing context when a conversation ends, agents persist their understanding into three simple objects stored alongside your code.

## Three objects, one graph

| Object | What it captures |
|---|---|
| **Intent** | A goal the agent identified from your query |
| **Snap** | One agent interaction — query, summary, feedback |
| **Decision** | A long-lived decision that spans multiple intents |

Objects link automatically: creating an intent attaches all active decisions; creating a decision attaches all active intents. Relationships are always bidirectional and append-only.

### How decisions are created

Decisions require human involvement. Two paths:

- **Explicit**: include `decision-[text]` (or `决定-[text]`) in your query and the agent creates it directly. E.g. "decision-all API responses use envelope format"
- **Agent-proposed**: the agent spots a potential long-term constraint in conversation and asks you to confirm before recording it

## Install

```bash
# Clone the repository
git clone https://github.com/dozybot001/Intent.git

# Install the CLI (pipx recommended)
pipx install intent-cli-python

# Or using pip
pip install intent-cli-python
```

Requires Python 3.9+ and Git.

### Add the Claude Code skill

```bash
npx skills add dozybot001/Intent
```

## Quick start

```bash
# Initialize in any git repo
itt init

# Agent identifies a new intent from user query
itt intent create "Fix the login timeout bug" \
  --query "why does login timeout after 5s?"

# Record what the agent did
itt snap create "Raise timeout to 30s" \
  --intent intent-001 \
  --query "login timeout still fails on slow networks" \
  --summary "Updated timeout config and ran the login test"

# Capture a long-lived decision
itt decision create "Timeout must stay configurable" \
  --rationale "Different deployments have different latency envelopes"

# See the full object graph
itt inspect
```

## Commands

### Global

| Command | Description |
|---|---|
| `itt version` | Print version |
| `itt init` | Initialize `.intent/` in current git repo |
| `itt inspect` | Show the live object graph snapshot |

### Intent

| Command | Description |
|---|---|
| `itt intent create TITLE --query Q` | Create a new intent |
| `itt intent list [--status S]` | List intents |
| `itt intent show ID` | Show intent details |
| `itt intent activate ID` | Resume a suspended intent |
| `itt intent suspend ID` | Suspend an active intent |
| `itt intent done ID` | Mark intent as completed |

### Snap

| Command | Description |
|---|---|
| `itt snap create TITLE --intent ID` | Record an interaction snapshot |
| `itt snap list [--intent ID] [--status S]` | List snaps |
| `itt snap show ID` | Show snap details |
| `itt snap feedback ID TEXT` | Set or overwrite feedback |
| `itt snap revert ID` | Mark a snap as reverted |

### Decision

| Command | Description |
|---|---|
| `itt decision create TITLE --rationale R` | Create a long-lived decision |
| `itt decision list [--status S]` | List decisions |
| `itt decision show ID` | Show decision details |
| `itt decision deprecate ID` | Deprecate a decision |
| `itt decision attach ID --intent ID` | Manually link a decision to an intent |

## Design principles

- **Agent-first**: designed to be called by AI agents, not typed by hand
- **Append-only history**: content fields are immutable after creation; correct mistakes in new snaps, don't rewrite old ones
- **Relationships only grow**: no detach — deprecate a decision instead
- **All output is JSON**: machine-readable by default
- **Zero dependencies**: pure Python, stdlib only

## Storage

All data lives in `.intent/` at your git repo root:

```
.intent/
  config.json
  intents/
    intent-001.json
  snaps/
    snap-001.json
  decisions/
    decision-001.json
```

## Docs

- [Vision](docs/EN/vision.md) — why semantic history matters. **If this project interests you, start here.**
- [CLI Design](docs/EN/cli.md) — object model, commands, JSON contract
- [Roadmap](docs/EN/roadmap.md) — phase plan

## License

MIT
