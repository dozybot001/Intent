# Dogfooding: Cross-Agent Collaboration in Practice

This document records a real cross-agent, cross-session collaboration using Intent + IntHub. It is distilled from the snap chain in `.intent/` (snap-050 through snap-061), rather than invented after the fact.

## Context

intent-013's goal is "Plan IntHub's initial design direction." IntHub is Intent's remote collaboration layer — a read-only web interface that lets team members and agents view semantic history without running `itt inspect` locally.

Under this single intent, the user naturally switched between multiple agents to complete a full work chain: from infrastructure setup to frontend rewrite to SKILL synchronization.

## Timeline

### Phase 1: Codex sets up IntHub (snap-050 → 052)

Codex handled the groundwork: pushed skill installation guidance to the README, documented IntHub Web entry points, and launched the local IntHub API + Web services. It completed the full `itt hub login → link → sync` pipeline.

At this point IntHub was live at `http://127.0.0.1:3000`, displaying the project's semantic history.

### Phase 2: Claude Code rewrites the frontend (snap-053 → 059)

After viewing IntHub in the browser, the user found display issues. Claude Code made a quick-fix pass (snap-053), but the user's feedback was clear:

> "I've decided to tear down the entire frontend and start over. The patches are no longer needed."

Claude Code ran `itt inspect`, read the context Codex left in snap-052 (API address, database path, synced data), and executed a complete frontend rewrite (snap-054) — from a single-page scroll to a two-column Handoff-first layout.

What followed was a series of feedback-driven iterations:

| Snap | User feedback | Agent response |
|---|---|---|
| 055 | Overflow bugs, decision redundancy, deprecated display | Fixed overflow, removed redundancy, layered deprecated display |
| 056 | Text is one giant block, no paragraphs | Added formatText() renderer, splits on sentence boundaries |
| 057 | — (agent self-review) | Timeline collapsing, English text support, loading states |
| 058 | Older snaps shouldn't have strikethrough; only 10 snaps shown | Separated collapse styles; removed API truncation |
| 059 | Show full intent history | API returns all intents; frontend groups by status |

Every round followed the same pattern: user gives feedback → `itt snap feedback` records it → agent implements → `itt snap create` records what was done and what wasn't.

### Phase 3: Codex updates the SKILL (snap-060)

The user noticed that newly added CLI commands (`doctor`, `hub`) weren't documented in the SKILL. They switched back to Codex — because Codex designed those commands and better understood their boundaries.

Codex ran `itt inspect` and saw all of Claude Code's frontend work (snap-053 through 059). In snap-060's query, the user wrote:

> "I had Claude Code refactor the frontend. Also, some new commands aren't taught in the skill yet — that needs fixing."

Codex didn't ask what happened. It read the snap chain and went straight to its own task: documenting `doctor`, `hub login/link/sync`, updating filter parameters, and refining intent creation criteria.

### Phase 4: Claude Code catches a mistake (snap-061)

The user switched back to Claude Code and asked: "Did Codex make the changes? Can you see them?"

Claude Code ran `itt inspect`, found snap-060's title and summary, and confirmed what Codex had done. Then it caught something Codex missed: Codex had edited the locally installed skill copy (`~/.agents/skills/intent-cli/SKILL.md`), not the repository source file (`SKILL.md`).

Claude Code recorded feedback on snap-060:

> "Changes are directionally correct but applied to the wrong file — should edit the repo's SKILL.md then reinstall, not the local skill copy directly."

It then diffed the two files, confirmed the quality of Codex's work, and synced the content back to the repository.

## What this demonstrates

**Agent switching needs no handoff meeting.** The user switched between agents multiple times. Not once did they need to re-explain context. Each agent read current state via `itt inspect`, read the previous agent's summary via `itt snap show`, and started working immediately.

**Feedback is consumed where it matters.** snap-053's feedback ("tear it down") directly shaped snap-054's direction. snap-060's feedback ("wrong file") directly caused snap-061's correction. Feedback isn't a post-mortem — it's input to the next step.

**Summaries are written for the next session's agent.** Every snap summary answers three questions: what's done, what's not, what context shapes the next step. This isn't logging — it's a handoff document.

**Decisions are live constraints, not memos.** Throughout the process, 5 active decisions continuously constrained implementation choices (e.g., `.intent/` stays out of Git, Hub isn't distributed via PyPI). These constraints aren't "remembered" by agents — they're structurally loaded from `itt inspect` every session and checked before implementation.

**Mistakes are structurally captured.** Codex edited the wrong file. Claude Code caught it via diff. Without Intent, this error might not surface until the next `npx skills add` — because the local skill looked correct, but the repository source wasn't updated. snap-060's feedback permanently records this mistake and why it happened, making it easier for future agents to see and avoid the same class of error.

## Data source

Everything above can be reproduced with:

```bash
itt inspect
itt snap show snap-050   # through snap-061
```

Or in the IntHub Web interface: open intent-013's detail → Snap Timeline → expand older snaps.
