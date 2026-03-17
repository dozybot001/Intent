English | [简体中文](../CN/glossary.md)

# Intent Glossary

This document aligns terminology only. It does not explain the project vision or define implementation contracts.

## Core Sentence

Git records code changes. Intent records what you did and why.

## Terms

- `semantic history`: history of intents, steps, and rationale rather than code diffs
- `intent`: the current problem or goal being worked on
- `checkpoint`: a recorded step with optional rationale — the unit of semantic history
- `inspect`: the primary machine-readable interface; returns the full workspace state as JSON
- `rationale`: the reason behind a checkpoint, recorded via `-m`

## Object Model

Intent has two object types:

- **Intent**: `open` → `done`
- **Checkpoint**: `adopted` (default), `candidate`, or `reverted`

## Core Loop

`problem → step → done`

At the command level:

`start → snap → done`

## What Intent Is Not

- not a replacement for Git
- not a replacement for issues, PRs, or documentation systems
- not a "record everything" archive
