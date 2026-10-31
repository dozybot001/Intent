---
name: intent-cli
description: >-
  Continuously maintain verified Intent semantic history in projects with local
  maintenance enabled; itt init enables it by default. Read context at turn start,
  preserve meaningful changes, and close hooked turns as recorded, no-op, or failed.
  Also handle requested project setup, Intent recording/recovery, branches, and IntHub
  push, pull, fetch and clone.
  Disabled or legacy projects are not automatically enabled. Network sync needs
  a separate explicit request.
---

# Intent CLI

Preserve enough verified meaning for another agent to continue, not a conversation log. Continuous maintenance is the normal mode; every turn needs assessment, not a new Snap.

## Project scope

- For first-time setup, missing `itt`, or optional IntHub authentication, read [onboarding.md](references/onboarding.md). On first installation, ask once whether to enable real-time recording for this project, together with any needed installation approval; an explicit enable request already answers this. Install, verify, and resume the original workflow. Local recording needs no account.
- Resolve the canonical semantic root; Git is optional. A trusted hook context for this root and turn supplies the opening snapshot. Otherwise check `itt maintenance status`. Read [execution.md](references/execution.md) before executing commands.
- `itt init` enables maintenance and installs project-local Codex hooks for a new history. Existing histories need `itt maintenance on` once. In Claude Code, add `--host claude-code` to `init`, `maintenance on`, and `maintenance status`. `itt maintenance off` disables only this project and removes Intent's Claude Code entries. Skill or plugin installation does not enable other projects.
- When asked to enable real-time recording, finish project configuration, then tell the user to review/trust this project's two hooks: `UserPromptSubmit` (opening context) and `Stop` (closure check). Codex: **Settings → Hooks** or `/hooks`; if absent, check project-directory trust first and follow [codex-hooks.md](references/codex-hooks.md). Claude Code: trust the folder and confirm both in `/hooks`, restarting the session only if they are missing, per [claude-code-hooks.md](references/claude-code-hooks.md). Do not repeat installation; configuration alone is not proof of execution.
- IntHub is optional. When requested and authentication is missing, have the user run `itt auth login` in their own terminal and approve the code in the browser; never request a token in chat. Read [onboarding.md](references/onboarding.md) for the full path.
- A project from Intent 7 answers writes with `REPOSITORY_NOT_MIGRATED`. Run `itt migrate` once when the work needs a write: it keeps every ID and backs up first. Reads work without it.
- Disabled/uninitialized projects do not get automatic semantic writes. Explicit one-off recording remains available; initialize only when requested setup, recording, or restoration needs it. Recovery starts read-only.
- User read-only, skip-this-turn, and disable instructions take precedence. Never automatically sync, log in, publish, or change Git remotes. Explicit push requests use [sync.md](references/sync.md); pull, fetch and clone requests use [pull.md](references/pull.md). Follow the requested sequence; planned later uploads are not current authorization.

## Quiet work loop

1. **Read once.** Reuse current-turn hook context; otherwise run `itt inspect` in the enabled root. For missing facts, run `itt inspect --intent ID --history 3` on the selected Intent only. Treat truncated context as incomplete. Code rediscovery and user explanations are not Intent recovery evidence.
2. **Preserve meaningful progress.** Reuse the matching goal; record verified milestones while fresh, particularly before long/risky phases. Only the coordinating agent writes. Do not record each tool call, intermediate edit, or plan as a completed fact.
3. **Close before responding.** Changed open goals need accurate continuation checkpoints. With a hook token, submit one receipt below; without a token, assess closure without inventing one or claiming enforcement.

```text
itt maintenance close recorded --turn TOKEN [--objects ID ...]
itt maintenance close no-op --turn TOKEN --reason REASON
itt maintenance close failed --turn TOKEN --reason REASON
```

`recorded` verifies actually changed objects (IDs may be derived automatically). `no-op` is normal when there is no continuation-critical change or the user skips recording: give a brief reason, not a filler Snap. `failed` acknowledges unavailable or unverified recording. Receipts are local turn metadata, not semantic objects. A Stop retry finishes closure only; it never authorizes repeating sync or task side effects.

Routine success and no-op stay silent. Briefly disclose unresolved/partial recording with successful IDs. Diagnose recoverable errors and continue after verification; do not blindly retry creates or suggested fixes. An unresolved history error pauses affected history operations, not unrelated authorized work.

## Semantic boundaries

- **Intent:** one coherent objective with its own outcome/lifecycle. Split independently resumable goals; reuse matching active/suspended goals when actually continuing them. No quota; do not split by query, session, file, command, commit, or implementation layer.
- **Snap:** one append-only verified milestone, conclusion, correction, or checkpoint within one Intent. Split independently verifiable/supersedable conclusions; combine evidence for the same conclusion. Cross-Intent work needs separate Snaps. Skip routine logs; correct with a later Snap.
- **Decision:** a rare rule binding future Intents on different problems. Explicit durable user rules are confirmed; inferred implementation choices stay local or omitted. Essential clarification is at most one short batch per workflow, not an interruption per candidate.
- **Relation:** only between Intents, and only when it changes how the work resumes. A goal found inside the current one is `--part-of` it (the parent cannot finish without it) or `--derived-from` it (independent); one that takes over a goal's aim `--succeeds` it, or end the old goal with `--into NEW`; `--depends-on` is a real prerequisite, `--conflicts-with` two goals that cannot both be achieved as stated. Never relate for mere similarity. A Decision that came out of one Intent's work takes `--from ID`; project-wide rules stay sourceless.

Intent `what` names the goal, `why` its motivation. Snap fields preserve the verified change and reasoning. A changed open or paused Intent's latest Snap must independently answer **Verified / Boundary / Next / Blocker / Constraints** with `--verified`, `--boundary`, `--next`, `--blocker` (`none` when absent) and `--constraints`, not labels in `what`/`why`; inspect returns them as each entry's `checkpoint` (older Snaps keep them as text). An unchanged accurate checkpoint needs no rewrite.

A query ending does not end the Intent. Mark done only after verified resolution and recorded completion/deferred boundaries; cancel deliberate abandonment with a reason; suspend a real pause after its checkpoint.

## Explicit recording / recovery

Record only work verified in current context, not “everything since last time”; zero writes is valid. Briefly report a one-off recording result, unlike quiet ongoing maintenance.

For recovery, inspect before old chat/code, then state goal/reason, boundary, next/blocker, and Decisions from Intent alone. Mark gaps honestly; three recent Snaps still insufficient means report the gap, not unlimited history. Merely viewing a suspended goal does not activate it.
