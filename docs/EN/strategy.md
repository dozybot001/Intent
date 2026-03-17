English | [简体中文](../CN/strategy.md)

# Intent Development Strategy

This document defines the path from the current local CLI to a new development paradigm. It is not a feature roadmap — it is a strategic direction.

## The Gap Intent Fills

Git records how code changed. It does not record why.

In the human era, this gap was filled by memory, discussion, and asking the person who wrote the code. In the agent era, all these compensations fail:

- agents have no persistent memory
- agents cannot ask the previous agent
- every new session starts from zero context

This means Intent is not solving a "nice to have" problem. It is solving a "cannot work without" problem — one that becomes undeniable as agent-driven development becomes mainstream.

## Phase 1: Agent Memory Layer

**The most painful problem today is not "recording history" — it is "recovering context."**

Every user of Claude Code, Codex, or Cursor has experienced this: a previous session did half the work, and the new session has no idea what was done, why it stopped, or which paths were already tried.

This is Intent's first killer scenario: **cross-session context recovery**.

What to build:

- make `itt inspect` output consumable as part of an agent's startup context
- write a lightweight hook: agent reads `inspect` on startup, runs `snap` or `done` on exit
- target experience: user opens a new session, agent immediately says "last time you were working on X, reached step Y, stopped because of Z — I suggest continuing from here"

The user should not need to understand what Intent is. They should just notice that the agent somehow knows what happened last time. **The best infrastructure is infrastructure the user does not perceive.**

## Phase 2: Semantic Exchange Protocol

Git became a paradigm not because Linus wrote a good CLI, but because GitHub turned Git into social infrastructure.

Intent's equivalent is IntHub. But the more pragmatic path right now is to become **the semantic exchange protocol between agent platforms**.

The current problem: work done in Claude Code cannot be handed off to Codex with any standardized way to transfer "what was done and why." Every platform invents its own context management.

Intent can be the middle layer:

- define `.intent/` as a minimal, open specification (already exists)
- build native integrations for major agent platforms (not just skill files — real plugins)
- the value anchor shifts from the CLI tool to **the `.intent/` directory itself as protocol**

When developers start deciding whether to `.gitignore` or commit their `.intent/` directory, Intent has become infrastructure.

## Phase 3: Network Effects

When enough repositories contain `.intent/` directories, new possibilities emerge:

- **Intent-aware code review**: PRs show not just diffs, but which intent they solve, what steps were taken, and the key rationale
- **Team-level semantic dashboard**: not who committed how many lines, but what problems the team is solving and where they are stuck
- **AI-assisted decision archaeology**: months later, look up why a particular approach was chosen — without relying on git blame guesswork

This is what IntHub should eventually do. But it must be built on proven Phase 1 and Phase 2 foundations.

## What Would Kill Intent

1. **Agent platforms build native context management.** If Claude Code ships persistent cross-session memory, Intent's first scenario disappears. But platforms tend toward generic memory, not structured semantic history — these are different things.

2. **Premature platform ambition.** Building IntHub, collaboration features, or UI before proving local value would scatter focus on the wrong things.

3. **Becoming "just another dev tool."** If Intent's narrative is "a tool to help you manage your development process," it drowns in hundreds of similar tools. Intent's narrative must be: **Git records how code changed. Intent records why. Together they form the complete engineering history.**

## Immediate Next Steps

1. Write a Claude Code hook that makes Intent work automatically at session boundaries — zero manual operation
2. Create a demo: first session does half the work, second session picks up seamlessly, user explains nothing
3. Commit `.intent/` into one or two real open-source projects so other developers and agents encounter it naturally

Paradigms are not designed. They grow. But the seed must be planted in the right place.
