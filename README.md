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
pipx install intent-cli-python
```

Requires Python 3.9+ and Git.

`.intent/` is local semantic-workspace metadata. It should stay out of Git history and remain ignored by `.gitignore`.

## Agent skill

If you use Codex, Claude Code, or another skill-capable agent, install the `intent-cli` skill too:

```bash
npx skills add dozybot001/Intent -g
```

This matters. The CLI gives the commands, but the skill teaches the agent when and how to use them during real work.

## Quick start

```bash
itt init

itt intent create "Fix the login timeout bug" \
  --query "why does login timeout after 5s?"

itt snap create "Raise timeout to 30s" \
  --intent intent-001 \
  --query "login timeout still fails on slow networks" \
  --summary "Updated timeout config and ran the login test"

itt decision create "Timeout must stay configurable" \
  --rationale "Different deployments have different latency envelopes"

itt inspect
```

For the full command surface and JSON contract, see the CLI design doc below.

## IntHub

IntHub is the remote collaboration layer built on top of Intent.

- PyPI ships only the `itt` CLI
- IntHub Web and API are not part of the PyPI package
- Current GitHub releases use a single project version line such as `v1.5.0`
- The CLI keeps its own package version in `pyproject.toml` and is published on PyPI

If you want to run the current IntHub prototype from source:

```bash
python -m apps.inthub_api --db-path .inthub/inthub.db
python -m apps.inthub_web --api-base-url http://127.0.0.1:8000
```

## Docs

- [Vision](docs/EN/vision.md) — why semantic history matters. **If this project interests you, start here.**
- [CLI Design](docs/EN/cli.md) — object model, commands, JSON contract
- [Roadmap](docs/EN/roadmap.md) — phase plan
- [Dogfooding](docs/EN/dogfooding.md) — a real cross-agent case study built from the snap chain
- [IntHub MVP](docs/EN/inthub-mvp.md) — first remote collaboration-layer scope
- [IntHub Sync Contract](docs/EN/inthub-sync-contract.md) — first sync, identity, and API contract

## Agent use

`itt` is new enough that models will sometimes forget to call it. A short reminder such as `use itt to record this` is usually enough.

## License

MIT
