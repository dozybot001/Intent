English | [简体中文](../CN/README.md)

# Intent Documentation

`docs/` splits the project documentation into clear layers, with each document answering a different kind of question.

## Document Map

| Document | Primary Question | Out of Scope |
| --- | --- | --- |
| [Glossary](glossary.md) | What do the core terms mean? | project background, command design |
| [Vision and problem definition](vision.md) | Why does the agent era need Intent? | command syntax, JSON schema |
| [CLI spec](cli.md) | What are the CLI commands, object model, and JSON contract? | longer-term platform questions |
| [Distribution and integration design](distribution.md) | How should Intent CLI and agent integrations be distributed? | CLI contract details |
| [First agent feedback](feedback.md) | What did the first real agent user find useful or frustrating? | CLI contract definitions |
| [Demo](demo.md) | How can Intent be tried quickly? | CLI contract definitions |
| [Release baseline](release.md) | What must be true before a release? | CLI contract details |
| [Strategy](strategy.md) | How does Intent become a paradigm? | current CLI details |
| [Roadmap](roadmap.md) | What should happen after the v0.2 simplification? | current CLI contract details |
| [Documentation i18n guide](i18n.md) | How is bilingual documentation organized? | CLI contract details |

## Suggested Reading Paths

- New to the project: start with [Glossary](glossary.md), then read [Vision](vision.md)
- Want a runnable example first: read [Demo](demo.md)
- Want to understand the CLI: read [CLI spec](cli.md)
- Want product feedback from real agent usage: read [First agent feedback](feedback.md)
- Want to prepare a release: read [Release baseline](release.md)
- Want to understand the long-term direction: read [Strategy](strategy.md)
- Want to discuss priorities: read [Roadmap](roadmap.md)

## Current Source of Truth

- problem definition and long-term direction: [Vision](vision.md)
- command semantics, object model, JSON contract, error model: [CLI spec](cli.md)
- post-simplification priorities: [Roadmap](roadmap.md)

If two documents disagree on a CLI detail, sync the EN/CN pair and keep the contract aligned.

## Current Focus

- `init → start → snap → done`
- 2-object model: intent and checkpoint
- `inspect` as the primary machine-readable entry point
- JSON-only output
- the fixed bootstrap path: `~/.intent/repo` plus `~/.intent/bin/itt`

## Notes

- the root [README](../../README.md) is the English GitHub entry point; [README.CN.md](../../README.CN.md) is the Chinese version
- `docs/` avoids duplicated narrative; shared terminology stays aligned with [Glossary](glossary.md)
- the current install journey source of truth is [Distribution and integration design](distribution.md)
