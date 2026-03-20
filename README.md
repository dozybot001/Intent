# Intent

[中文](README.CN.md) | English

Semantic history for agent-driven development. Records **what you did** and **why**.

## Why

Git records how code changes. But it doesn't record **why you're on this path**, what you decided along the way, or where you left off.

Intent adds that missing layer: **semantic history** — a small set of formal objects that survive context loss.

> Development is moving from *writing code* to *guiding agents and distilling decisions*. The history layer should reflect that.

```mermaid
flowchart LR
  subgraph traditional["Traditional"]
    direction TB
    H1["Human"]
    C1["Code"]
    H1 -->|"Git"| C1
  end
  subgraph agent["Agent Era"]
    direction TB
    H2["Human"]
    AG["Agent"]
    C2["Code"]
    H2 -."❌ no semantic history".-> AG
    AG -->|"Git"| C2
  end
  subgraph withintent["Agent with Intent"]
    direction TB
    H3["Human"]
    AG2["Agent"]
    C3["Code"]
    H3 -->|"Intent"| AG2
    AG2 -->|"Git"| C3
  end
  traditional ~~~ agent ~~~ withintent
```

## Three objects, one graph

| Object | What it captures |
|---|---|
| **Intent** | A goal recognized from your query |
| **Snap** | One query-response interaction — query, summary, feedback |
| **Decision** | A long-lived constraint that spans multiple intents |

Objects link automatically. Decisions auto-attach to every active intent; intents auto-attach to every active decision. Relationships are bidirectional and append-only.

```mermaid
flowchart LR
  D1["🔶 Decision 1"]
  D2["🔶 Decision 2"]

  subgraph Intent1["🎯 Intent 1"]
    direction LR
    S1["Snap 1"] --> S2["Snap 2"] --> S3["..."]
  end

  subgraph Intent2["🎯 Intent 2"]
    direction LR
    S4["Snap 1"] --> S5["Snap 2"] --> S6["..."]
  end

  D1 -- auto-attach --> Intent1
  D1 -- auto-attach --> Intent2
  D2 -- auto-attach --> Intent2
```

## Install

```bash
pipx install intent-cli-python   # CLI
npx skills add dozybot001/Intent -g  # Agent skill
```

Requires Python 3.9+ and Git. The CLI provides the commands; the skill teaches the agent when to use them.

## IntHub

IntHub is the remote collaboration layer on top of Intent. The first path is **IntHub Local** — download from a [GitHub release](https://github.com/dozybot001/Intent/releases), then:

```bash
itt hub login --api-base-url http://127.0.0.1:7210
itt hub link
itt hub sync
```

Open `http://127.0.0.1:7210` in the browser.

## Docs

- [Vision](docs/EN/vision.md) — why semantic history matters
- [CLI Design](docs/EN/cli.md) — object model, commands, JSON contract
- [Roadmap](docs/EN/roadmap.md) — phase plan
- [Dogfooding](docs/EN/dogfooding.md) — cross-agent case study
- [IntHub Local](docs/EN/inthub-local.md) — run a local IntHub instance

## License

MIT
