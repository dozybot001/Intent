English | [简体中文](../CN/roadmap.md)

# Intent Roadmap

Purpose: define what should come after the v0.2 simplification. This document is the current roadmap.

Historical roadmap for the first release: [roadmap-v0.1.0.md](archive/roadmap-v0.1.0.md)

## Current Stage

The CLI has been simplified from a 5-object model (intent, checkpoint, adoption, run, decision) to a 2-object model (intent, checkpoint). Schema version is now 0.2.

The core loop is now `start → snap → done`, with all output as JSON. The focus has shifted from "prove the prototype" to "validate that this minimal model is useful in practice."

## What Is Already Done

- the `.intent/` local object layer with 2 object types
- `init → start → snap → done` core loop
- `adopt` and `revert` for candidate comparison workflow
- `inspect` as the primary machine-readable entry point
- `list` and `show` for object queries
- JSON-only output (no human-readable text mode)
- CI, build verification, and agent integration setup
- bilingual documentation (EN/CN)

## Priority Principles

- prioritize feedback from real agent use over feature expansion
- prioritize simplicity — resist adding objects or states
- keep the local semantic layer at the center
- avoid platform-style scope before local workflows are proven

## Phase 1: Agent Dogfooding

Goal: use Intent in real agent workflows and validate the 2-object model.

Key questions:

- does `start → snap → done` feel natural for agents?
- does `inspect` give agents enough context to work without friction?
- is the candidate/adopt workflow useful, or is default-adopted sufficient?
- are the error messages and suggested fixes actionable?

Completion signals:

- repeated real use without ad hoc workarounds
- clear understanding of which parts work and which need change

## Phase 2: Hardening

Goal: make the implementation reliable based on real usage feedback.

- fix edge cases found during dogfooding
- stabilize the JSON contract
- ensure tests cover real failure modes

## Phase 3: Decide the Next Direction

Candidate directions:

- richer inspection and query capabilities
- IntHub for remote organization and human-readable views
- collaboration features beyond the local CLI

Decision rule: pick the smallest next step informed by real usage.

## Explicitly Deferred

- remote sync as a default assumption
- platform-style timeline UI
- re-introducing removed objects (adoption, run, decision) unless proven necessary
- complex filters and query languages before usage pressure exists
- replacing Git's version-control role

## One-Sentence Summary

The roadmap after simplification is about validating that two objects and a simple loop are enough to make agent-driven development more traceable.
