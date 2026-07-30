# Intent

[中文](README_CN.md) | English

A semantic history layer above Git for development. It records **goals**, **semantic snapshots**, and **decisions**.

## Why

Git records how code changes. But it doesn't record **why you're on this path**, what you decided along the way, or where you left off.

Intent adds that missing layer: **semantic history** — a small set of formal objects that preserve product formation history and survive context loss.

> Development is moving from *writing code* to *guiding agents and distilling decisions*. The history layer should reflect that.

```mermaid
flowchart LR
  subgraph traditional["Traditional Coding"]
    direction TB
    H1["Human"]
    C1["Code"]
    H1 -->|"Git"| C1
  end
  subgraph agent["Agent Driven Development"]
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
| 🎯 **Intent** | A goal summarized from the interaction |
| 📸 **Snap** | A semantic snapshot — what was done and why |
| 🔶 **Decision** | A long-lived constraint that spans multiple intents |

Objects link automatically. Relationships are bidirectional and append-only.

```mermaid
flowchart LR
  D1["🔶 Decision 1"]
  D2["🔶 Decision 2"]

  subgraph Intent1["🎯 Intent 1"]
    direction LR
    S1["📸 Snap 1"] --> S2["📸 Snap 2"] --> S3["📸 ..."]
  end

  subgraph Intent2["🎯 Intent 2"]
    direction LR
    S4["📸 Snap 1"] --> S5["📸 Snap 2"] --> S6["📸 ..."]
  end

  D1 -- auto-attach --> Intent1
  D1 -- auto-attach --> Intent2
  D2 -- auto-attach --> Intent2
```

## How to record

Early versions used a **Snap–Query** model where the agent autonomously captured snapshots after each interaction. It worked — but it was noisy, expensive on tokens, and interrupted the natural flow of work.

Early dogfooding led us to the **Intent–Session** model: the agent works freely, and you decide when to record. Recording moves from every interaction to the end of a meaningful goal stage, reducing in-flow interruptions and letting the agent summarize milestones that have already settled. The user trigger can be as small as saying “record semantics” at the right checkpoint.

Whether this model costs less than Git or a fact-matched flat summary, or improves continuation quality in a fresh session, remains a testable hypothesis. The current engineering smoke test validates the evaluation path but does not establish an effectiveness result. The next frozen-checkpoint, Session B-only study is governed by a public [continuation benchmark preregistration](docs/benchmarks/continuation-benchmark-preregistration.md); no positive result is claimed before its holdout thresholds are met. See the [evaluation design](docs/EN/evaluation.md) and [engineering smoke report](docs/benchmarks/2026-07-30-low-resource-smoke.md).

1. Work with the agent on your goal
2. When the goal is achieved, ask the agent to look back and build the semantic history
3. The agent creates one intent (the goal) + snaps (milestones) + marks it done

"Session" doesn't strictly mean a full conversation — it represents any purposeful interaction where you know what you set out to do. Like `git commit`, recording is user-initiated.

[MAARS](https://github.com/dozybot001/MAARS) uses this approach — each session's semantic history was recorded retrospectively.

## Quick Start

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/dozybot001/Intent/main/scripts/install.sh | bash

# Windows (PowerShell)
irm https://raw.githubusercontent.com/dozybot001/Intent/main/scripts/install.ps1 | iex

# Clone repo & add agent skill
git clone https://github.com/dozybot001/Intent.git
npx skills add dozybot001/Intent -g --all
```

Requires Python 3.9+ and Git. The install script handles pipx automatically.
Re-run the installer anytime to upgrade or repair an existing `itt` install.

To browse semantic history in a browser, start **IntHub Local** (works from any directory):

```bash
itt hub start
```

Then, in your project repo:

```bash
itt hub link --api-base-url http://127.0.0.1:7210
itt hub sync
```

> **Tips:** Type `/intent-cli` to load the recording guide, or simply say "record semantics" / "记录语义" if the agent already knows about Intent.

## Showcase

This project manages its own development with Intent. Browse the live semantic history:

**[IntHub Showcase](https://dozybot001.github.io/Intent/)** — interactive viewer for Intent project history, MAARS, and legacy data.

Or run `itt hub start` locally.

## Docs

- [Vision](docs/EN/vision.md) — why semantic history matters
- [CLI Design](docs/EN/cli.md) — object model, commands, JSON contract
- [Evaluation Design](docs/EN/evaluation.md) — how to reproducibly validate cost, resume value, and object boundaries
- [Benchmark CLI](docs/EN/benchmark-cli.md) — run generic continuation tasks with `itt benchmark`
- [Benchmark Preregistration](docs/benchmarks/continuation-benchmark-preregistration.md) — frozen questions, fairness controls, stopping rules, and permitted claims

## Community

- [Contributing](.github/CONTRIBUTING.md)
- [Code of Conduct](.github/CODE_OF_CONDUCT.md)
- [Security Policy](.github/SECURITY.md)

## License

MIT
