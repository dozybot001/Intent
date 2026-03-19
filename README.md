# Intent CLI

[中文](README.CN.md) | English

Semantic history for agent-driven development. Records **what you did** and **why**.

## Why

Git records how code changes. But it doesn't record **why you're on this path**, what you decided along the way, or where you left off.

Today that context lives in chat logs, PR threads, and your head. It works until the session ends, the agent forgets, or a teammate picks up your work blind.

Intent adds that missing layer: **semantic history**. Not more docs or better commit messages, but a small set of formal objects that survive context loss.

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

The CLI provides the commands; the skill teaches the agent when to use them.

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
- Current GitHub releases use a single project version line such as `v1.6.0`
- The CLI keeps its own package version in `pyproject.toml` and is published on PyPI

The first user-facing path is **IntHub Local**: download the asset from a GitHub release, start it locally, then connect your repo with:

```bash
itt hub login --api-base-url http://127.0.0.1:7210
itt hub link
itt hub sync
```

Then open `http://127.0.0.1:7210` in the browser.

Current limitations:
- IntHub V1 expects your local repo to have a GitHub `origin` remote
- IntHub Local currently depends on Python 3.9+
- hosted IntHub is still a later step; the first distributable path is local-instance-first

## Docs

- [Vision](docs/EN/vision.md) — why semantic history matters. **If this project interests you, start here.**
- [CLI Design](docs/EN/cli.md) — object model, commands, JSON contract
- [Roadmap](docs/EN/roadmap.md) — phase plan
- [Dogfooding](docs/EN/dogfooding.md) — a real cross-agent case study built from the snap chain
- [IntHub MVP](docs/EN/inthub-mvp.md) — first remote collaboration-layer scope
- [IntHub Sync Contract](docs/EN/inthub-sync-contract.md) — first sync, identity, and API contract
- [IntHub Local](docs/EN/inthub-local.md) — how to run the first local IntHub instance from a release asset

## License

MIT
