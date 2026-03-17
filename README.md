English | [简体中文](README.CN.md)

# Intent

> Git records code changes. Intent records why.

## The Problem

In agent-driven development, code is produced fast, but the reasoning behind it disappears between sessions. Git tells you *how* code changed — not what problem was being solved, what was tried, or why a particular path was chosen.

In the human era, this context lived in memory and conversation. In the agent era, every new session starts from zero. There is no persistent "why."

## The Solution

Intent adds a `.intent/` directory to your repository — structured metadata that captures semantic history alongside code history.

```
.git/    ← how code changed
.intent/ ← what you did and why
```

Any agent platform can read `.intent/`. It is a protocol, not just a tool.

## Core Loop

```
start → snap → done
```

- `start` — begin work on a problem
- `snap` — record a step with rationale
- `done` — close when work is complete

Two objects: **intent** (the goal) and **checkpoint** (a step taken). All output is JSON.

## Example

```bash
itt init
itt start "Fix login timeout"
itt snap "Increase timeout to 30s" -m "5s too short for slow networks"
git add . && git commit -m "fix timeout"
itt done
```

## Where This Is Going

1. **Agent memory layer** — agents read `.intent/` on startup, instantly know what happened last session
2. **Semantic exchange protocol** — `.intent/` becomes the standard way to hand off context between agent platforms
3. **Network effects** — when enough repos contain `.intent/`, new tooling emerges: intent-aware code review, decision archaeology, semantic dashboards

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/dozybot001/Intent/main/setup/install.sh | bash
```

For contributors:

```bash
git clone https://github.com/dozybot001/Intent.git && cd Intent
python3 -m venv .venv && . .venv/bin/activate && pip install -e .
```

## Commands

| Command | Purpose |
| --- | --- |
| `itt init` | Initialize `.intent/` in a Git repo |
| `itt start <title>` | Open an intent |
| `itt snap <title> [-m why]` | Record a checkpoint |
| `itt done` | Close the active intent |
| `itt inspect` | Machine-readable workspace snapshot |
| `itt list <intent\|checkpoint>` | List objects |
| `itt show <id>` | Show a single object |
| `itt adopt [id]` | Adopt a candidate checkpoint |
| `itt revert` | Revert the latest checkpoint |

## Documentation

- [Changelog](CHANGELOG.md)
- [CLI spec](docs/EN/cli.md) — objects, commands, JSON output contract
