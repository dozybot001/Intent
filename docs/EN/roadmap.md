English | [简体中文](../CN/roadmap.md)

# Intent Roadmap

Purpose: define the work sequence after the initial CLI. This document answers "what should come next?" without redefining the CLI contract.

## Current Stage

The current implementation already covers the minimum local loop:

- the `.intent/` local object layer
- `init -> start -> snap -> adopt -> log`
- `status --json` / `inspect --json`
- the surface CLI and the minimum canonical actions
- Git prerequisites, the error model, and baseline tests
- baseline read-side commands
- demo scripts for human and agent flows
- the initial `run` lifecycle and minimum `decision` support
- baseline CI, local install instructions, and package build verification

The next stage should continue by strengthening this implementation in this order:

1. stabilize the v1 CLI for practical use
2. strengthen read paths and agent entry points
3. introduce `run` / `decision`
4. only then consider more distant collaboration layers

## Priority Principles

- prioritize capabilities that improve reliability and usability
- prioritize capabilities that make both human and agent integration easier
- prioritize capabilities that quickly produce demos and validation material
- do not implement low-frequency features early just for object completeness
- do not move into remote sync, platform-style collaboration, or complex filters yet

## Milestone 1: Polish the v1 CLI

Goal: complete the baseline usability and demo material for the current CLI.

Suggested items:

- add read-only commands: `intent show`, `checkpoint show`, `adoption show`
- add baseline list commands: `intent list`, `checkpoint list`, `adoption list`
- provide a minimal config entry point such as `itt config show`
- add an official smoke script for quickly validating the main path
- prepare a human demo that uses `itt log` to show adoption history
- align human-readable output more closely with the documented text baseline
- add more error-path tests and JSON contract tests

Completion signals:

- common read/write commands can be used coherently in a local repo
- major error scenarios have test coverage
- a new user can complete one full demo by following the README

## Milestone 2: Improve Agent / Automation Experience

Goal: make Intent easier for agents, scripts, and automation to consume reliably.

Suggested items:

- complete the minimum read-side coverage for the canonical CLI
- make `inspect --json` richer for conflict states, empty states, and post-revert states
- prepare an agent demo that uses `inspect --json` to drive the next action
- add more machine-friendly fields to write-command responses, such as more consistent `next_action`
- expand the regression matrix for `--id-only` and `--json`
- add reusable fixtures and helpers to reduce long-term test maintenance cost

Completion signals:

- an agent can complete the main path using only `inspect --json` plus canonical actions
- JSON response structures remain stable across the main state transitions

## Milestone 3: Introduce `run`

Goal: record one agent execution or one exploration round as a semantic span for provenance and automation.

Suggested items:

- implement `run start` / `run end`
- maintain `active_run_id` correctly in `state.json`
- allow checkpoints and adoptions to attach `run_id`
- define the minimum inspect output for runs

Completion signals:

- one agent execution round can be modeled formally
- `run` does not disturb the existing `start -> snap -> adopt` loop

## Milestone 4: Introduce `decision`

Goal: elevate "why this and not that" from adoption notes into a longer-lived reusable object.

Suggested items:

- add `decision create`
- define how decisions relate to adoptions and intents
- design a minimum schema suitable for preserving principle-level judgments
- define when decisions should appear so they do not become mandatory noise

Completion signals:

- important tradeoffs can be referenced reliably
- `decision` does not crowd the front-page path

## Milestone 5: Distribution and Collaboration

Goal: make the CLI easier to install, try, and share, while preparing for future collaboration layers.

Suggested items:

- improve installation and versioning
- add CI to run tests automatically
- add usage examples, demo scripts, and release notes
- dogfood the CLI in real repositories
- evaluate Skill / IntHub integration points after the local layer is stable

Completion signals:

- external users can install and try the CLI easily
- each change is covered by automated validation

## Immediate Next Steps

If there is time for only one more implementation pass, use this order:

1. human demo: compare `itt log` with `git log`
2. agent demo: drive the next step from `inspect --json`
3. stronger JSON / error-path tests
4. `run start/end`

## Explicitly Deferred

These directions should not be rushed right now:

- remote sync
- a platform-style timeline UI
- complex filters and query languages
- large object-surface expansion
- turning `log` into a full JSON timeline API

## One-Sentence Summary

The current roadmap keeps the local semantic layer at the center: strengthen demos, validation, and baseline capabilities first, then expand into later objects and collaboration layers.
