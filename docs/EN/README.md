English | [简体中文](../CN/README.md)

# Intent Documentation

`docs/` exists to split the project documentation into clear layers, with each document answering a different kind of question.

## Document Map

| Document | Primary Question | Out of Scope |
| --- | --- | --- |
| [Glossary](glossary.md) | What do the core terms mean? | project background, command design, implementation details |
| [Vision and problem definition](vision.md) | Why does the agent era need Intent? | command syntax, JSON schema |
| [Unified CLI spec](cli.md) | What are the CLI boundaries, command semantics, and implementation contract? | longer-term platform questions |
| [Distribution and integration design](distribution.md) | How should Intent CLI and agent integrations be distributed and installed? | CLI contract details, per-platform implementation minutiae |
| [Repository structure](structure.md) | What does the current repository layout look like, and what does each path do? | command contract details, release policy |
| [Demo](demo.md) | How can `itt log` and `git log` be compared quickly? | CLI contract definitions, long-term roadmap |
| [Release baseline](release.md) | What must be true before a staged release? | CLI contract details, long-term roadmap |
| [Roadmap](roadmap.md) | What should happen after `v0.1.0`? | current CLI contract details |
| [Documentation i18n guide](i18n.md) | How is bilingual documentation organized and maintained? | CLI contract details, implementation sequencing |

## Suggested Reading Paths

- New to the project: start with [Glossary](glossary.md), then read [Vision and problem definition](vision.md)
- Want a runnable example first: read [Demo](demo.md)
- Want a quick map of the repository before editing: read [Repository structure](structure.md)
- Want to discuss one-step install and multi-platform agent enablement: read [Distribution and integration design](distribution.md)
- Want to prepare a staged release: read [Release baseline](release.md)
- Want to discuss bilingual documentation structure: read [Documentation i18n guide](i18n.md)
- Want to discuss command semantics or implementation: read [Unified CLI spec](cli.md)
- Want to discuss post-`v0.1.0` priorities: read [Roadmap](roadmap.md)

## Current Source of Truth

- problem definition and long-term direction: [Vision and problem definition](vision.md)
- command semantics, object exposure order, state machine, JSON contract, and error model: [Unified CLI spec](cli.md)
- post-`v0.1.0` priorities and next-step direction: [Roadmap](roadmap.md)

If two documents disagree on a CLI detail, sync the EN/CN pair and keep the contract aligned.

## Current Focus

- `init -> start -> snap -> adopt -> log`
- the `.intent/` local object layer
- `status --json` / `inspect --json`
- Git linkage, error handling, and idempotent semantics
- the fixed bootstrap path: `~/.intent/repo` plus `~/.intent/bin/itt`

## Notes

- the root [README](../../README.md) is the English GitHub entry point; [README.CN.md](../../README.CN.md) is the Chinese version
- `docs/` tries to avoid duplicated narrative; shared terminology should stay aligned with [Glossary](glossary.md)
- the current install journey source of truth is [Distribution and integration design](distribution.md)
