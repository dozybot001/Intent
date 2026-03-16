English | [简体中文](glossary.CN.md)

Paired file: [glossary.CN.md](glossary.CN.md)

# Intent Glossary

This document aligns terminology only. It does not explain the project vision or define implementation contracts.

## Core Sentence

Git records code changes. Intent records adoption history.

## Terms

- `semantic history`: history of intent, candidates, adoption, and decisions rather than code diffs
- `intent`: the current problem or goal being worked on
- `checkpoint`: a candidate outcome that is concrete enough to compare and track
- `adoption`: the formal adoption of a checkpoint
- `decision`: a tradeoff or principle worth preserving over time
- `run`: one agent execution or one round of exploration; important for automation, but not a front-page object yet
- `active intent`: the current default problem context
- `current checkpoint`: the current default candidate object
- `Surface CLI`: short commands for frequent human use, such as `itt start` and `itt snap`
- `Canonical CLI`: stable object commands for agents, skills, IDEs, and automation, such as `itt checkpoint create`
- `status`: human-facing output that answers "what state are we in, and what should happen next?"
- `inspect`: machine-facing output that returns stable, complete, consumable context

## Minimal Loop

The most important path in Intent right now is:

`problem -> candidate -> adoption`

At the command level, that becomes:

`start -> snap -> adopt`

## What Intent Is Not

- not a replacement for Git
- not a replacement for issues, PRs, or documentation systems
- not a "record everything" archive
