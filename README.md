English | [简体中文](README.CN.md)

# Intent

> Git records code changes. Intent records adoption history.
> Intent is designed for both humans and agents.

Intent is a new layer built on top of Git for tracking higher-level software development history:

- what problem is being worked on
- which candidate outcomes were explored
- what was formally adopted
- why it was adopted

Intent does not replace Git. It fills in the part of history that Git usually does not preserve clearly.

In more technical terms, Intent is a Git-compatible semantic history layer for the agent era. The current implementation starts with `Intent CLI`.

## Understand It in 30 Seconds

In agent-driven development, code can be produced quickly, but the decision process is often scattered:

- goals live in issues
- candidate solutions live in conversations or drafts
- final choices and rationale live in discussions

Git is excellent at answering "how did the code change?" but much weaker at answering "what did we finally decide?"

Intent focuses on that missing layer.

It provides this history through a CLI and exposes structured entry points that both humans and agents can read.

That means Intent is not just "one more document." It turns higher-level development semantics into:

- a workflow people can follow
- interfaces developers can integrate
- stable objects agents can read and act on

## Why Not Just Use Issues, ADRs, or Commit Messages

Existing tools are useful, but they do not model adoption history itself as a stable object.

| Approach | Good At | Limitation |
| --- | --- | --- |
| commit messages | explaining an individual code change | does not reliably answer "what is the current intent?", "which candidates were tried?", or "what was finally adopted?" |
| issues / PRs | holding discussion and context | context gets fragmented, and there is no stable object boundary or consistent read interface for agents |
| ADRs / docs | preserving long-term architectural decisions | too heavy for high-frequency `start -> snap -> adopt` flows |
| Intent | tracking semantic objects and adoption history | currently focused on the local CLI loop and structured read interfaces |

## Core Loop

Intent starts by formalizing three actions as first-class objects:

- `start`: begin work on a problem
- `snap`: save a candidate result
- `adopt`: formally adopt a candidate result

That gives a minimal path:

`problem -> candidate -> adoption`

This path is designed for both humans and agents.

## Why It Matters for Agents

For agents, Intent provides structured context instead of relying only on prose:

- stable object boundaries
- explicit current state
- predictable next actions
- structured, machine-consumable output

Intent exposes `intent`, `checkpoint`, and `adoption` as formal objects.

## Minimal Example

```bash
itt init
itt start "Reduce onboarding confusion"
itt snap "Landing page candidate B"
git add .
git commit -m "refine onboarding landing layout"
itt adopt -m "Adopt progressive disclosure layout"
itt log
```

This flow says three things:

- Git still manages the codebase normally
- Intent adds a semantic history layer on top
- `itt log` is closer than commit history to "what decision was adopted here?"

## Six Commands to Remember First

```bash
itt init
itt start
itt status
itt snap
itt adopt
itt log
```

If you are integrating with the CLI or building agent workflows, start with:

```bash
itt status --json
itt inspect --json
```

## What Intent Is Not

- not a replacement for Git
- not a replacement for issues, PRs, or documentation systems
- not a "record everything" archive

Intent only tracks semantic events worth formalizing, such as intent creation, candidate checkpoints, adoption, revert, and decision records.

## Human-Friendly, Agent-Friendly

Intent is structured in two layers:

- for humans: `start -> snap -> adopt`
- for developers: a local object layer and CLI contract
- for agents: stable objects, stable states, and stable JSON entry points

## Current Scope

The project is still early. The focus is not breadth yet; it is making the smallest local loop reliable.

Current priorities:

- the `.intent/` local object layer
- `init -> start -> snap -> adopt -> log`
- agent-friendly contracts such as `status --json` and `inspect --json`
- keeping the same semantic model useful for both humans and agents

## Documentation

The root README stays lightweight. More detailed material lives in `docs/`.

- [Documentation index](docs/README.EN.md)
- [Glossary](docs/glossary.EN.md)
- [Vision and problem definition](docs/vision.EN.md)
- [Unified CLI spec](docs/cli.EN.md)
- [Demo](docs/demo.EN.md)
- [Roadmap](docs/roadmap.EN.md)
- [Documentation i18n plan](docs/i18n.EN.md)

For more background, start with [Vision and problem definition](docs/vision.EN.md).
