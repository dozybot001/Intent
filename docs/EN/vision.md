English | [简体中文](../CN/vision.md)

# Intent Vision and Problem Definition

## Core Judgment

Git remains core infrastructure for the code layer. That has not changed.

What has changed is the way software gets built:

- people increasingly shape code indirectly through agents
- implementation looks like "set a goal, generate candidates, choose an outcome"
- the center of gravity is shifting from "write code" to "record why"

The new question is not "how do we replace Git?" It is:

**How do we add a semantic history layer on top of Git for agent-driven development?**

That is the role of Intent.

## The Missing Piece Is Not Information, but Objects

High-level semantic information is not rare. It is scattered across commit messages, issues, PR discussions, docs, team chat, and agent conversations.

The problem is not that the information does not exist. The problem is that it is:

- readable, but unstable
- discussable, but hard to track over time
- workable for humans, but unreliable for agents

We can usually see how code changed, but not reliably answer:

- what problem is being worked on
- what steps were taken and why
- what was the rationale behind key choices

Intent promotes these higher-level semantics into first-class objects.

## Why the Existing Tool Stack Is Not Enough

`Git + PR + issue + docs + chat` is useful, but it does not make semantic history into a unified system:

- semantics are expressed in fragments rather than formally modeled
- semantic boundaries are unstable — hard to reference and revisit
- agents lack stable IDs, explicit states, and structured entry points

## Which Layer Intent Adds

| Layer | Responsibility | Typical Objects |
| --- | --- | --- |
| Git | code history | commit, branch, diff |
| Intent | semantic history | intent, checkpoint |
| IntHub | remote organization and collaboration | later |

**Git records code changes. Intent records what you did and why.**

## Project Boundary

Intent does not aim to:

- replace Git's version control role
- replace issues, PRs, or documentation systems
- preserve every raw conversation or intermediate artifact
- become a "record everything" process platform

Its boundary: **record the semantic steps worth tracking, along with their rationale.**

## One-Sentence Definition

Intent is a Git-compatible semantic history layer for agent-driven software development.
