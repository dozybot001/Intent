English | [简体中文](../CN/roadmap.md)

# Intent Roadmap

Purpose: define what should come after `v0.1.0`. This document is the current roadmap, not the historical one that led to the first tagged release.

Historical roadmap for the first release: [roadmap-v0.1.0.md](archive/roadmap-v0.1.0.md)

## Current Stage

`v0.1.0` is now tagged. The initial local CLI loop is established, and the project has moved out of its "prove the prototype" phase.

The next work should focus on using, hardening, and learning from the current implementation rather than replaying the milestones that are already complete.

## What Is Already Done

- the `.intent/` local object layer
- `init -> start -> snap -> adopt -> log`
- `status --json` / `inspect --json`
- read-side commands for `intent`, `checkpoint`, `adoption`, `run`, and `decision`
- `run` and `decision`
- human and agent demos
- CI, build verification, and wheel-install verification
- a first tagged release: `v0.1.0`

## Priority Principles

- prioritize feedback from real use over object-surface expansion
- prioritize reliability, maintainability, and release quality
- keep the local semantic layer at the center
- avoid introducing platform-style scope before local workflows are clearly proven

## Phase 1: Dogfooding and Hardening

Goal: use `v0.1.0` in real repositories and tighten rough edges.

Suggested items:

- use Intent in one or more real repos instead of only synthetic demos
- collect friction in command wording, state transitions, and recovery paths
- improve help text, examples, and release materials from actual usage
- refine the local check path and CI only when real usage exposes gaps

Completion signals:

- repeated real-repo usage does not require ad hoc workarounds
- the common failure modes are understood and documented

## Phase 2: Internal Structure Cleanup

Goal: make the codebase easier to maintain before expanding the semantic model again.

Suggested items:

- extract `.intent/` storage and ID allocation from the remaining core logic
- keep rendering, git, state transitions, and storage as separate responsibilities
- reduce test duplication with better fixtures where it clearly helps

Completion signals:

- core domain logic is smaller and easier to evolve
- new features no longer need to touch too many unrelated code paths

## Phase 3: Decide the `v0.2.0` Direction

Goal: choose the next meaningful step after the first tagged release.

Candidate directions:

- deeper dogfooding and UX refinement without large surface expansion
- better packaging and release ergonomics
- richer query / inspection capabilities
- carefully chosen collaboration or remote-sync experiments

Decision rule:

- pick the smallest next step that is informed by real usage, not by abstract completeness

## Explicitly Deferred

These directions still should not be rushed:

- remote sync as a default assumption
- a platform-style timeline UI
- large object-surface expansion just for symmetry
- complex filters and query languages before usage pressure exists
- replacing Git's version-control role

## One-Sentence Summary

The roadmap after `v0.1.0` is no longer about making the prototype exist; it is about validating, hardening, and learning what the next release should actually optimize for.
