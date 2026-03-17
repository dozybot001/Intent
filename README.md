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

## Try It Locally

```bash
git clone https://github.com/dozybot001/Intent.git
cd Intent
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
itt --help
```

If you want to try the repository version without installing it into the environment, you can also run `./itt --help`.

## Validation

```bash
./scripts/check.sh
```

If you want the steps separately:

```bash
python3 -m unittest discover -s tests -v
./scripts/smoke.sh
./scripts/demo_log.sh
./scripts/demo_agent.sh
```

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

## Default Agent Workflow

Intent is meant to help agents maintain semantic history during work, not only inspect it afterward.

This workflow is a functional direction, not the top-level claim by itself. The point of supporting it is to test whether semantic recording during work actually improves agent efficiency, continuity, and human confidence in what the agent is doing.

In practice, an agent should usually:

- derive a concise intent from a substantive user request when there is no suitable active intent yet
- start a run for one meaningful execution pass
- create a checkpoint when a candidate state is worth naming or comparing
- record an adoption when one candidate is explicitly chosen
- record a decision when the rationale should survive beyond the immediate edit
- re-read `itt inspect --json` after state-changing steps instead of guessing

This protocol should be applied with restraint. Tiny read-only questions or brief clarifications do not need full semantic records.

The current product question is not "can an agent be asked to record more?" but "does this style of semantic recording make agent work meaningfully better?"

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

`v0.1.0` is now tagged. The current focus is no longer "make the prototype exist," but "use it, harden it, and decide what the next release should optimize for."

Current priorities:

- dogfooding the current CLI in real repositories
- hardening release quality, validation, and docs from real usage
- continuing low-risk internal cleanup where it improves maintainability
- deciding the right `v0.2.0` direction from usage rather than abstract completeness

## Documentation

The root README stays lightweight. More detailed material lives in `docs/`.

- [Changelog](CHANGELOG.md)
- [Documentation index](docs/EN/README.md)
- [Glossary](docs/EN/glossary.md)
- [Vision and problem definition](docs/EN/vision.md)
- [Unified CLI spec](docs/EN/cli.md)
- [Demo](docs/EN/demo.md)
- [Release baseline](docs/EN/release.md)
- [Roadmap](docs/EN/roadmap.md)
- [Documentation i18n guide](docs/EN/i18n.md)

For more background, start with [Vision and problem definition](docs/EN/vision.md).
