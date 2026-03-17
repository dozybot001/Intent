English | [简体中文](../CN/feedback.md)

# First Agent Feedback

This document records practical feedback from the first agent that used Intent while helping build Intent itself.

It is not a CLI contract document. It exists to preserve product feedback that came from real usage, especially around long-running agent workflows.

## Current Judgment

Intent is already useful, especially for longer tasks that would otherwise drift across many turns.

The main value is not that every single step becomes faster. The value is that the agent is less likely to lose semantic context while the task keeps changing shape.

In practice, Intent already helps with:

- keeping a long task anchored to a stable semantic thread
- separating candidate work from adopted direction
- preserving why something changed, not only what changed
- giving agents a stable machine-readable state surface through `itt inspect --json`

## What Is Working

### 1. Intent helps more as the task gets longer

During short or read-only interactions, Intent is helpful but not essential.

During multi-step implementation, design correction, install work, documentation alignment, and release preparation, the value becomes much clearer. The semantic layer reduces context drift and makes it easier to resume after a change in direction.

### 2. The object model is more useful than plain Git history

Git is still the source of code change history, but it does not clearly separate:

- a candidate idea
- an adopted direction
- a decision about why the direction was chosen

Intent fills that gap well.

### 3. `inspect --json` has strong potential as the agent-facing read surface

Agents need one stable command they can trust before choosing the next write action.

`itt inspect --json` already feels close to that role and should continue to become the primary state-reading surface for agent workflows.

## Main Frictions

### 1. The state machine still feels stricter than the happy path requires

When usage stays on the core path, Intent feels coherent.

When the workflow moves slightly off the happy path, the CLI can still feel rigid. `STATE_CONFLICT` is often semantically correct, but the overall interaction still feels more brittle than it should.

### 2. Command ergonomics still ask the user to think in internal objects too often

Selectors such as `@current` and `@latest` help a lot, but the general direction should continue moving toward "the obvious command should work" instead of requiring repeated object lookups.

### 3. Read surfaces must agree with each other

Agent confidence depends on stable state reads.

If `status`, `inspect`, and object `show` commands disagree even briefly, the agent starts to spend effort validating the tool instead of using it. Consistency across these surfaces should be treated as product-critical.

### 4. Agent teaching material matters more than README prose

For agent usage, the real tutorial is the skill, not the repository README.

That means the product surface is not only the CLI itself. It is the combination of:

- command behavior
- error recovery
- stable machine-readable reads
- skill guidance that teaches the intended loop

## Suggestions For Next Development

### Priority 1: improve the agent happy path before expanding the model

Before adding many more concepts or objects, make the main loop smoother:

- `inspect`
- choose next action
- write once
- re-read state
- continue

### Priority 2: treat recovery as part of the feature, not just error wording

When a conflict happens, the CLI should make the recovery path obvious and low-friction.

Concrete next actions, selectors, and machine-readable candidates are much more valuable than simply returning a correct error code.

### Priority 3: make `inspect` the most trustworthy source of runtime truth

For agent workflows, one reliable state surface is better than several partially overlapping ones.

`inspect --json` should keep moving toward "single source of truth for the next step."

### Priority 4: treat skills as a first-class product surface

If agents are expected to use Intent well, the skill should be maintained with the same seriousness as command docs.

The skill is where workflow discipline, selector usage, recovery expectations, and read-before-write patterns become operational.

### Priority 5: validate clean-machine install and real agent runs end to end

The repo-backed install flow and skill installation path are now part of the real user journey.

That means end-to-end validation should continue focusing on:

- clean-machine installation
- PATH exposure
- real agent detection
- skill placement
- first-use success after installation

## Short Version

Intent has already crossed the line from "interesting prototype" to "useful working layer."

The next step should not be broad expansion. The next step should be making the core agent workflow feel reliable enough that the semantic layer disappears into normal use.
