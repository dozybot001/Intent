---
name: intent-cli
description: >-
  Maintain Intent semantic history (.intent/) throughout work in a repository or
  task where the user explicitly enabled automatic Intent maintenance; also
  handle explicit one-off Intent recording, recovery, and IntHub push/pull requests.
  Automatic maintenance reads at turn start and assesses closure before the final
  response, recording only verified semantic changes. Installation, existing
  history, generic notes, and mentioning Intent do not enable it.
  Network push or pull always requires a separate explicit request.
---

# Intent CLI

Preserve enough verified meaning for another agent to continue, without turning conversation into a log. Every authorized maintenance/recording turn needs a closure assessment, not a new object. Outside an authorized workflow, closure classification is not applicable.

## Scope and permission

- **Automatic maintenance:** The user explicitly enables it for a named repository or task, directly or through a trusted user-approved project instruction. That grants ongoing local inspect/record permission until revoked; do not ask again each turn. Resolve its scope first. This Skill revision alone does not enable it anywhere.
- **One-off recording:** An explicit request to write with Intent or `.intent/` authorizes that recording workflow only. Generic summaries, notes, and status requests are not permission.
- **Recovery:** An explicit Intent recovery request starts read-only. Continuing work does not grant ongoing recording unless automatic maintenance is already enabled.
- **Sync:** Only an explicit request to push Intent data to IntHub authorizes network synchronization. Read [references/sync.md](references/sync.md) before doing it. Git pushes, recording permission, and automatic maintenance never authorize sync, login, or publication.
- **Pull:** Only an explicit request to pull Intent history from IntHub authorizes a private snapshot download and validated local restoration. Read [references/pull.md](references/pull.md). Recovery and automatic maintenance do not imply pull; pull does not authorize recording, push, login, or publication.

A request to stay read-only, skip recording this turn, or disable maintenance wins. Repository existence, prior history, and Skill installation are not opt-in. Permission does not cross repository boundaries. Without an authorized mode, do not run `itt`.

Follow the requested sequence. “Download and delete online; reorganize/upload later” ends after verified download and deletion. Future plans do not authorize current uploads, temporary online projects, or changes to other local repositories.

## The automatic work loop

1. **Start — read context.** Resolve the authorized semantic root (Git is optional) and run `itt inspect`, or reuse a trusted successful hook result for this root and turn. If it fails, diagnose and recover using [execution.md](references/execution.md); a recovered, verified state permits continuing this turn. Use relevant checkpoints and active Decisions. Read bounded history for the selected Intent when its latest checkpoint is insufficient. Do not guess missing facts.
2. **During work — preserve meaningful changes.** Reuse the matching Intent. Once a goal or independently verified milestone is clear, record it while context is fresh, especially before a long or risky next phase. Do not record plans as completed facts, every tool call, or intermediate edits. Only the coordinating agent writes; subagents return verified facts to it.
3. **Before the final response — assess closure.** For each materially changed objective, preserve its verified outcome or accurate continuation checkpoint and verify final state. Classify the turn as **recorded**, **no-op** (no new continuation-critical semantics, or recording explicitly skipped), or **failed** (recording unavailable, incomplete, or unverified). Already-recorded milestones plus an accurate latest checkpoint need no duplicate end-of-turn Snap.

Routine success and no-op stay quiet. Report unresolved or partial recording briefly, including successful object IDs, without misrepresenting the main task as failed. An unresolved Intent failure pauses affected history operations, not otherwise authorized project work.

Closure here is an agent obligation, not an implemented receipt command. Read [references/codex-hooks.md](references/codex-hooks.md) only when integrating Codex hooks. Do not invent a receipt, enable command, or claim hooks are installed.

## Choose meaning, not a count

- One **Intent** is a coherent objective with its own outcome and lifecycle. Separate independently resumable goals; do not merge them to fit a one-Intent quota. Reuse a matching active Intent; activate a matching suspended one by explicit ID only when actually resuming work or adding a Snap. Create only genuinely new objectives. Do not split by session, query, file, commit, command, or implementation layer.
- One **Snap** is an append-only milestone, verified conclusion, correction, or checkpoint within exactly one Intent. Split independently verifiable or supersedable conclusions; combine evidence for the same conclusion. Cross-Intent work requires separate Snaps. Skip logs and routine mechanical edits. Intent and Snap counts have no quota.
- A changed Intent that remains open must end with a self-contained checkpoint: **Verified / Boundary / Next / Blocker / Constraints**. State what is established, what remains unfinished or out of scope, the next concrete action, blockers (`none` if absent), and local constraints. Encode compactly in `what` and `why`; prerequisite results may be summarized. An unchanged, accurate checkpoint needs no rewrite.
- A **Decision** is a rule that would bind a future Intent on a different problem. An explicit durable user rule is already confirmed; inferred implementation choices are not. Keep unconfirmed candidates local in a Snap or omit them. If confirmation is essential, combine all necessary questions into at most one short batch for the workflow; do not interrupt merely to collect Decisions.

Intent `what` names the objective; `why` explains motivation. Snap `what` states the verified change/checkpoint; `why` carries reasoning and constraints. Correct history with a later Snap; never rewrite old objects.

Query boundaries do not change Intent lifecycle. Leave ongoing goals active. Mark done only after verified resolution, cancel only when deliberately abandoned with a reason, and suspend only when genuinely paused, after preserving its checkpoint. Before done, ensure completion evidence and deliberately deferred boundaries are recorded.

## One-off recording and explicit recovery

One-off recording uses the same inspect, semantic selection, and verified closure rules. Record only work verified in current context; do not claim to know everything since the last recording. Zero writes is valid. Unlike quiet automatic maintenance, briefly report what was recorded or why nothing was written.

For explicit recovery, inspect first without old chat or rediscovering facts in code. Before acting, state the goal and reason, verified boundary, next action/blocker, and applicable Decisions from Intent alone. Mark gaps honestly; code/test rediscovery and user explanations are not Intent recovery evidence. Use bounded history only for the selected Intent; if three recent Snaps are insufficient, report the gap rather than fetching unlimited history. Activate a suspended Intent only when asked to continue it, not merely inspect it.

## Execution guardrails

Read [references/execution.md](references/execution.md) for argv execution and error recovery. Use the target repository cwd, parse JSON results, capture explicit object IDs, and make semantic changes through the CLI.

Initialize when the requested setup, recording, or restoration needs a new history. Read-only recovery does not initialize. Diagnose graph warnings with `itt doctor`; resume affected writes after the problem is resolved and verified. Other warnings require judgment, not an automatic stop.

Do not blindly execute `suggested_fix`, expose credentials, change Git remotes, or automatically run authentication, hub service, or sync commands.

## Local command surface

```text
itt init
itt inspect
itt inspect --intent ID --history 3
itt doctor
itt status [--local]
itt remote
itt remote add origin URL --project NAME
itt intent create WHAT [--why WHY]
itt intent activate ID
itt intent suspend ID
itt intent done ID
itt intent cancel ID [--reason REASON]
itt snap create WHAT --intent ID [--why WHY]
itt decision create WHAT [--why WHY]
itt decision deprecate ID [--reason REASON]
```
