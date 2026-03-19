# Intent CLI

[中文](README.CN.md) | English

Semantic history for agent-driven development. Records **what you did** and **why**.

Intent CLI gives AI agents a structured way to track goals, interactions, and decisions across sessions. Instead of losing context when a conversation ends, agents persist their understanding into three simple objects stored alongside your code.

## Why

Git records how code changes. But it doesn't record **why you're on this path**, what you decided along the way, or where you left off.

Today that context lives in chat logs, PR threads, and your head. It works — until the session ends, the agent forgets, or a teammate picks up your work blind.

Intent treats these as a missing layer: **semantic history**. Not more docs, not better commit messages — a small set of formal objects that capture goals, interactions, and decisions so they survive context loss.

> The shift is simple: development is moving from *writing code* to *guiding agents and distilling decisions*. The history layer should reflect that.

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

### IntHub boundary

`pipx install intent-cli-python` installs the CLI only.

This repository is the umbrella project for both `Intent` and `IntHub`, but the distribution boundary is narrower than the repository boundary:

- PyPI ships only the `itt` CLI
- IntHub Web is a separate static frontend and is a good fit for GitHub Pages
- IntHub API is a separate service and is not part of the PyPI package

If you are running IntHub from source inside this repository, the current local entrypoints are:

```bash
python -m apps.inthub_api --db-path .inthub/inthub.db
python -m apps.inthub_web --api-base-url http://127.0.0.1:8000
```

Then use `itt hub login`, `itt hub link`, and `itt hub sync` from a local Intent workspace to populate the read-only IntHub project view.

### Versioning and releases

`Intent` is the umbrella project and monorepo. GitHub keeps a single project version line for the repository.

Release responsibilities:

- The repository-level GitHub release uses the project version from the root `VERSION` file and tags like `v1.4.0`.
- The release notes for that project release explain which CLI version and Hub version belong to it.
- The CLI package keeps its own version in `pyproject.toml`, but that version is published on PyPI rather than as a separate GitHub release line.
- IntHub does not currently publish a separate GitHub release line.

This means:

- the root `VERSION` file is the source of truth for the GitHub project release version
- `pyproject.toml` still describes only the CLI package version
- GitHub should show one latest project release, not parallel CLI and Hub release tracks

Historical bare tags such as `v1.3.0` remain part of the same project-version line. New GitHub releases continue that single `vX.Y.Z` sequence.

### Install the skills.sh skill

```bash
npx skills add dozybot001/Intent -g
```

This installs the `intent-cli` skill into your global skills library for supported agents such as Codex and Claude Code.

> **Tip:** `itt` is a new tool — current models have never seen it in training data. Your agent may forget to call it mid-conversation. A short nudge like *"use itt to record this"* is usually enough to bring it back on track.
>
> This isn't busywork — every record is a **semantic asset**. An upcoming platform, **IntHub**, will turn these assets into searchable, shareable project intelligence.

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
| `itt doctor` | Validate the object graph for broken references and invalid states |

### Intent

| Command | Description |
|---|---|
| `itt intent create TITLE --query Q` | Create a new intent |
| `itt intent list [--status S] [--decision ID]` | List intents |
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
| `itt decision list [--status S] [--intent ID]` | List decisions |
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

`.intent/` is local semantic-workspace metadata. It should stay out of Git history and should remain ignored by `.gitignore`.

## Docs

- [Vision](docs/EN/vision.md) — why semantic history matters. **If this project interests you, start here.**
- [CLI Design](docs/EN/cli.md) — object model, commands, JSON contract
- [Roadmap](docs/EN/roadmap.md) — phase plan
- [IntHub MVP](docs/EN/inthub-mvp.md) — first remote collaboration-layer scope
- [IntHub Sync Contract](docs/EN/inthub-sync-contract.md) — first sync, identity, and API contract

## License

MIT
