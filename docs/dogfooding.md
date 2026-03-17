English | [简体中文](dogfooding.CN.md)

# Dogfooding: Building Intent with Intent

Intent was built using itself. This document records what happened — not as marketing, but as an honest log of how `.intent/` shaped an agent-driven development session.

## Context

One developer, one AI agent (Claude), one afternoon. The goal: take Intent from a working prototype to a published tool. The session covered PyPI publishing, documentation rewrites, bug fixes, a new feature (suspend/resume), and a Hacker News launch.

## What actually happened

### 13 intents, 35 snaps

Over the course of the session, 13 intents were created. Some highlights:

| Intent | Title | Snaps |
|---|---|---|
| intent-004 | Simplify Intent to agent-only minimal CLI | 1 |
| intent-007 | Unify naming: checkpoint → snap | 1 |
| intent-008 | Publish to PyPI and provide agent integration templates | 2 |
| intent-010 | Align intent object granularity | 2 |
| intent-011 | Three-phase adoption plan | 5 |
| intent-012 | Fix PyPI Chinese README link | 1 |

### Context switching without loss

The critical moment: while working on intent-011 (three-phase adoption plan), a PyPI bug was discovered — the Chinese README link was broken. Instead of losing context:

```
itt suspend                          # pause adoption plan
itt start "Fix PyPI README link"     # handle the bug
itt snap "..." -m "..."
itt done                             # bug fixed
itt resume                           # back to adoption plan
```

The agent picked up exactly where it left off. No re-explanation needed.

### The rationale gap

Midway through the session, the developer asked: "what are the snaps under intent-011?" The list showed snap-031 with rationale:

> PyPI (git-intent 0.3.2) + GitHub Release + agent integration templates ready. Next: phase two, HN Show HN launch.

Phase 3's goal was missing entirely. Without it, a future session would know there's a "three-phase plan" but not what phase 3 actually is. This led to two changes:

1. A new snap (snap-033) captured the full strategic picture in its rationale
2. The agent integration guide was updated: **rationale for progress snaps should capture the complete picture — what's done, what's in progress, what's remaining, and strategic context**

### The naming lesson

The agent was recording snaps mechanically — "what I did" — without capturing "where we are." This revealed that teaching agents the *commands* isn't enough. They need to understand *object semantics*: what an intent represents (a goal, not a task), what a snap represents (a step), and what rationale should contain (decisions, progress, and forward state).

## What we learned

1. **suspend/resume is essential.** Real work isn't linear. You get interrupted. Without suspend, you either close an unfinished intent (losing state) or ignore the interruption.

2. **Rationale needs the full picture.** A snap that says "did X because Y" is useful. A snap that says "did X because Y; A is done, B is in progress, C is next; constraint: deadline Thursday" is what makes the next session actually autonomous.

3. **Agents need semantics, not just commands.** Telling an agent "run `itt snap` before each commit" produces low-value snaps. Telling it "the rationale should capture what the next session needs to reconstruct the plan" produces high-value ones.

4. **The tool discovers its own gaps.** By using Intent to build Intent, we found missing features (suspend/resume, `list --intent` filter), documentation gaps (object semantics guide), and design insights (rationale as full-picture capture) that wouldn't have surfaced from pure design thinking.
