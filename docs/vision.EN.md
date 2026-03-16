English | [简体中文](vision.CN.md)

Paired file: [vision.CN.md](vision.CN.md)

# Intent Vision and Problem Definition

## What This Document Answers

- why the agent era needs a new semantic history layer
- which layer Intent adds, and what it does not replace
- where Intent CLI, skills, and IntHub sit relative to each other
- how to judge whether the project is working at the current stage

## What This Document Does Not Answer

- exact command design
- JSON schema, state machine, or exit codes
- first-release implementation details

## Boundary with Other Documents

- terminology is defined in [Glossary](glossary.EN.md)
- command semantics, state machines, and machine-readable contracts are defined in [Unified CLI spec](cli.CN.md)

## 1. Core Judgment

Git remains core infrastructure for the code layer. That has not changed.

What has changed is the way software gets built:

- people increasingly shape code indirectly through agents
- implementation increasingly looks like "set a goal, generate candidates, choose an outcome"
- development now produces higher-level objects such as `intent`, `checkpoint`, `adoption`, and `decision`

So the new question is not "how do we replace Git?" It is:

**How do we add a semantic history layer on top of Git for human-agent collaboration?**

That is the role of Intent.

## 2. The Missing Piece Is Not Information, but Objects

High-level semantic information is not rare today. It is usually scattered across:

- commit messages
- issues
- PR discussions
- docs
- team chat
- agent conversations
- temporary notes and spoken agreement

The problem is not that the information does not exist. The problem is that it is usually:

- readable, but unstable
- discussable, but hard to track over time
- rememberable, but not modeled with shared object boundaries
- workable for humans, but unreliable for agents

That creates a practical gap: we can usually see how code changed, but not reliably answer questions like:

- what problem is currently being worked on
- which candidate outcomes appeared along the way
- which one was formally adopted
- why this one was chosen instead of another

Intent is not trying to "record more information." It is trying to:

**promote higher-level semantics into first-class objects.**

## 3. Why the Existing Tool Stack Is Not Enough

`Git + PR + issue + docs + chat` is useful, but it does not make adoption history into a unified system.

The main gaps are:

- semantics are expressed in fragments rather than formally modeled
- semantic node boundaries are unstable, so they are hard to reference, compare, and revisit
- agents lack stable ids, explicit states, and structured entry points
- adoption is not treated as the central system action

In traditional development, the center of gravity is closer to "writing code."

In agent-driven development, the increasingly important actions are:

- propose a goal
- generate candidates
- compare candidates
- formally adopt one
- revert when necessary
- preserve long-lived decisions

The center of gravity is shifting from "write" to "select."

## 4. Which Layer Intent Adds

Intent does not replace Git. It adds the layer Git was never designed to carry by itself.

| Layer | Responsibility | Typical Objects |
| --- | --- | --- |
| Git | code history | commit, branch, diff |
| Intent | semantic history | intent, checkpoint, adoption, decision |
| IntHub | remote organization and collaboration | timeline, sharing, collaboration views |

Intent can therefore be understood as:

**an intention and adoption layer built on top of Git.**

In one sentence:

**Git records code changes. Intent records adoption history.**

## 5. Project Boundary

Intent does not currently aim to:

- replace Git's version control role
- replace issues, PRs, or documentation systems
- preserve every raw conversation or every intermediate artifact
- become a heavyweight "record everything" process platform
- start as a full remote platform in phase one

Its boundary is narrower and more concrete:

**record only the semantic nodes worth tracking, comparing, adopting, reverting, and reusing.**

## 6. Why This Becomes More Common in the Agent Era

In traditional development, higher-level semantics often stayed in a developer's head or across ordinary collaboration artifacts.

In the agent era, the shape of work changes:

- much more implementation is carried out by agents
- humans act more like reviewers, selectors, and directors
- user queries, revisions, adoption, and revert actions become part of the development process itself

That means a system can no longer stop at recording how code changes. It also needs to capture why a path was chosen.

For agents in particular, this matters because they need:

- stable object ids
- explicit states
- queryable context
- executable semantic actions

## 7. Why the First Step Is a CLI

The first phase of Intent is not a platform. It is a local CLI.

That choice is driven by a few practical goals:

- prove the smallest loop locally
- freeze the local object layer and behavior contract first
- give agents, IDEs, and automation a stable entry point
- adjust the interface around real workflows before expanding further

Remote collaboration, timeline views, and broader platform layers depend on the local layer becoming clear first.

## 8. Current Validation Focus

At the current stage, the priority is understanding whether the local semantic layer is useful and whether its interface boundaries are right.

The main questions are:

- does `start -> snap -> adopt` feel natural in real use
- is `itt log` actually closer than `git log` to adoption history
- does `itt inspect --json` really let agents guess less about the current state

These questions can already be explored through two demos:

- human demo: use `itt log` to inspect adoption history during a single round of work
- agent demo: read `itt inspect --json`, then execute the suggested next action

Those observations should guide whether the project keeps refining the local loop or expands into broader collaboration layers.

## 9. Long-Term Structure

The long-term structure of Intent can be thought of in three layers:

| Layer | Role | Current Position |
| --- | --- | --- |
| Intent CLI | local semantic history operation layer | current focus |
| Skill / agent workflow | teach agents when and how to use `itt` | next layer |
| IntHub | remote organization, presentation, and collaboration | later |

This describes sequencing, not hard technical dependency:

**stabilize the local semantic layer first, then expand into remote collaboration.**

That is why IntHub is still a later organizational and collaboration layer rather than the center of the current implementation.

## 10. One-Sentence Definition

Intent is a Git-compatible semantic history layer for agent-driven software development.

## 11. Summary

Intent is not focused on Git's version-control role. It is focused on the semantic history that usually sits outside Git:

- what problem is being worked on
- which candidate outcomes appeared
- what was finally adopted
- how revert and longer-lived decisions should be recorded when needed
