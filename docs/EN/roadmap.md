# Intent Roadmap

[中文](../CN/roadmap.md) | English

## What this document answers

- What to do first and what to do later in the current phase
- Why the current implementation is CLI-centric
- Which directions belong to future phases, not the current deliverable

## Relationship to other documents

- For vision and invariant judgments, see [vision](vision.md)
- For implementation and behavior contracts, see the [CLI design doc](cli.md)
- For a concrete cross-agent case study, see [dogfooding](dogfooding.md)
- For the first IntHub collaboration-layer scope, see the [IntHub MVP design doc](inthub-mvp.md)

## Current guiding principles

- The current implementation follows the [CLI design doc](cli.md)
- This roadmap describes phase ordering, not long-term invariant principles
- The roadmap may be adjusted based on dogfooding and real usage feedback

## Phase 1: Make the local semantic layer solid

Current focus:

- Align CLI implementation with [cli.md](cli.md)
- Validate through real agent workflows whether `intent / snap / decision` is a stable enough object set
- Validate core scenarios: interrupt recovery, continuation, long-term decision crystallization
- Converge basic behaviors: inspect, list, show, create, state transitions

The goal of this phase is not "as many features as possible" but "as stable a semantic layer as possible."

## Phase 2: Converge agent usage patterns

Once the local semantic layer is stable enough, the next step is converging how agents naturally use it.

Focus areas:

- When to create new objects vs. reuse existing ones
- How to keep recording cost low enough that it's not an extra burden
- How to make agents maintain semantic continuity during real work, not just backfill after the fact
- How to use dogfooding to find high-signal, low-noise usage patterns

This phase is about workflow, not platformization.

## Phase 3: Then consider remote organization and collaboration

Later directions include:

- Shared timelines
- Cross-person and cross-agent collaboration context
- Clearer display, search, and retrospective views
- Team-level handoffs, reviews, and decision inheritance

These directions are important, but they depend on the local semantic layer being stable first.

## Current non-goals

Not prioritized in the current phase:

- Heavyweight project management platform
- Complete raw conversation archival system
- Over-designing complex mechanisms for remote collaboration prematurely
- Abstract platformization divorced from real workflows

## Judging whether the roadmap is on track

Whether the roadmap is correct depends on these signals:

- Is the CLI model requiring fewer and fewer rewrites
- Are agents relying less on ad-hoc explanations to continue work
- Can humans more easily understand the current semantic state
- Is added complexity yielding real benefits, not just documentation and process overhead
