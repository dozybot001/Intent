English | [简体中文](README.CN.md)

Paired file: [README.CN.md](README.CN.md)

# Intent Documentation

`docs/` exists to split the project documentation into clear layers, with each document answering a different kind of question.

The repository is currently in a bilingual migration. GitHub shows the English README first, and core documents are available as EN/CN pairs.

## Document Map

| Document | Primary Question | Out of Scope | Language Status |
| --- | --- | --- | --- |
| [Glossary](glossary.EN.md) | What do the core terms mean? | project background, command design, implementation details | EN/CN pair available |
| [Vision and problem definition](vision.EN.md) | Why does the agent era need Intent? | command syntax, JSON schema | EN/CN pair available |
| [Unified CLI spec](cli.EN.md) | What are the CLI boundaries, command semantics, and implementation contract? | longer-term platform questions | EN/CN pair available |
| [Demo](demo.EN.md) | How can `itt log` and `git log` be compared quickly? | CLI contract definitions, long-term roadmap | EN/CN pair available |
| [Roadmap](roadmap.EN.md) | What comes after the initial CLI? | current CLI contract details | EN/CN pair available |
| [Documentation i18n plan](i18n.EN.md) | How should bilingual documentation be organized and migrated? | CLI contract details, implementation sequencing | EN/CN pair available |

## Suggested Reading Paths

- New to the project: start with [Glossary](glossary.EN.md), then read [Vision and problem definition](vision.EN.md)
- Want a runnable example first: read [Demo](demo.EN.md)
- Want to discuss bilingual documentation structure: read [Documentation i18n plan](i18n.EN.md)
- Want to discuss command semantics or implementation: read [Unified CLI spec](cli.EN.md)
- Want to discuss upcoming priorities: read [Roadmap](roadmap.EN.md)

## Current Source of Truth

- problem definition and long-term direction: [Vision and problem definition](vision.EN.md)
- command semantics, object exposure order, state machine, JSON contract, and error model: [Unified CLI spec](cli.EN.md)
- implementation sequencing and next-step priorities: [Roadmap](roadmap.EN.md)

If two documents disagree on a CLI detail, sync the EN/CN pair and keep the contract aligned.

## Current Focus

- `init -> start -> snap -> adopt -> log`
- the `.intent/` local object layer
- `status --json` / `inspect --json`
- Git linkage, error handling, and idempotent semantics

## Notes

- the root [README](../README.md) is the English GitHub entry point; [README.CN.md](../README.CN.md) is the Chinese version
- `docs/` tries to avoid duplicated narrative; shared terminology should stay aligned with [Glossary](glossary.EN.md)
