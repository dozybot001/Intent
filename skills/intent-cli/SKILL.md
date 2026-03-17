---
name: intent-cli
description: Use when you need to understand, operate, or teach the Intent CLI workflow in a Git repository.
---

# Intent CLI

Use this skill when a repository already uses Intent CLI, or when the user wants
to start using Intent CLI in the current Git workspace.

## Quick start

1. Run `itt inspect --json` before substantive work.
2. If the workspace is not initialized, run `itt init`.
3. Continue the active intent when it already matches the task.
4. Use `itt run start`, `itt snap`, `itt adopt`, and `itt decide` only for meaningful steps.
5. Re-read `itt inspect --json` after every state-changing command before issuing the next write.

## Core loop

```bash
itt init
itt start "Clarify the problem"
itt snap "Candidate A"
itt adopt -m "Adopt candidate A"
itt log
```

## When to read bundled references

- For Intent dogfooding inside the Intent repository itself, read [references/dogfooding.md](references/dogfooding.md).
- For deciding how much semantic recording a user request deserves, read [references/query-examples.md](references/query-examples.md).
- For fast command and selector recall, read [references/workflow-cheatsheet.md](references/workflow-cheatsheet.md).
- For recovery and failure handling, read [references/error-handling.md](references/error-handling.md).

## Important states

- `NOT_INITIALIZED`: initialize Intent in this Git repository.
- `intent_active`: there is an active intent but no current checkpoint yet.
- `candidate_ready`: a selected checkpoint is ready to adopt.
- `adoption_recorded`: the latest event is an adoption or revert.
- `conflict_multiple_candidates`: inspect candidates and select explicitly.

## Guardrails

- do not invent object IDs
- when the target is simply the current checkpoint or latest adoption, prefer `itt adopt --checkpoint @current ...` and `itt decide ... --adoption @latest`
- if `STATE_CONFLICT` lists candidate checkpoints, run `itt checkpoint select <id>` with one of the suggested ids before retrying
- prefer `itt status --json` for lightweight reads
- prefer `itt inspect --json` for stable machine context
- do not create noisy decisions for trivial edits
- if you skip Intent during substantive work, explain why
