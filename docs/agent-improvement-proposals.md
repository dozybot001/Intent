# Agent-Facing Improvement Proposals

Source: feedback from Claude Code (Opus 4.6) on the Intent CLI experience, 2026-03-22.

---

## 1. SKILL.md is too heavy (already being addressed)

The current file is about 23 KB. Loading it in full costs roughly 6,000 tokens per session, and much of the instructional material becomes dead weight once an agent is already proficient.

**Proposal:** split it into a core SKILL (~10 KB) plus an on-demand `SKILL-guide.md`.

## 2. Missing `list` / `show` / `search` commands

`list` and `show` were removed, but agents still often need to:

- inspect all snaps under a given intent (`inspect` only exposes `latest_snap`)
- search decisions by keyword to confirm whether a constraint already exists
- review the history of completed intents

Right now the only option is manual file reads such as `cat .intent/intents/intent-001.json`, which goes against the goal of a structured CLI.

**Proposal:** bring back `itt intent show <ID>` and `itt decision list [--status active]`.

## 3. Active decisions accumulate forever, making `inspect` noisy

At the time of writing, 13 active decisions are flattened directly into the `inspect` output, and every new intent auto-attaches all of them.

**Proposal:**

- support decision groups or tags such as `--tag architecture`
- sort or group `inspect` output by relevance
- or introduce decision scope so only matching intents receive the attachment

## 4. Immutable objects without a correction path create noise over time

If a snap's `what` is wrong, the only option is to create a separate correction snap. If an intent's `why` is weak, there is no repair path at all.

**Proposal:** add `itt snap amend <ID>` or `itt intent annotate <ID> --note "..."`. The original object would remain immutable, but the system could create an explicit correction record and let `inspect` surface the latest correction first.

## 5. Missing cross-intent relationships

Different intents often have causal relationships such as discovery leading to a new intent or one intent blocking another, but the model cannot express that today.

**Proposal:** support `itt intent create ... --follows intent-005`, `--blocked-by intent-008`, or a simpler `related_ids` field.

## 6. `--why` is optional on intents but required on snaps

Sometimes a snap does not have a meaningful `why` because the change is purely mechanical. Requiring it can encourage filler text.

**Proposal:** either make `why` optional on both object types and highlight missing reasoning in `inspect`, or require it on both. The main goal is consistency.

## 7. ID format ceiling

Zero-padded three-digit IDs top out at 999. This repository already has 44+ intents, so long-running projects will eventually hit that limit.

**Proposal:** move to four digits or dynamic width.

## 8. `itt hub start` had to run from the Intent repo root (already solved)

The fix was to package `apps/` into the pip distribution so `itt hub start` can run from any directory.

---

## Bigger Framing: Optimize for Resume Quality in `inspect`

The core value of Intent is whether `inspect` lets the next session immediately resume useful work. The biggest leverage points are:

- **`inspect` output quality:** today it shows `what`, but not the latest snap's `next`, which is often the key resume detail
- **reducing agent judgment burden:** the current SKILL contains many prompts like "evaluate whether..." and "determine which path...", which consume reasoning tokens and can produce inconsistent behavior
