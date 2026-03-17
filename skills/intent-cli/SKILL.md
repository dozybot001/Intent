---
name: intent-cli
description: Use when you need to operate the Intent CLI semantic history layer in a Git repository.
---

# Intent CLI

Intent records semantic history on top of Git: what problem you worked on, what you did, and why.

## Core loop

```bash
itt init                              # initialize
itt start "Describe the problem"      # open an intent
itt snap "What I did" -m "Why"        # record a checkpoint (adopted by default)
itt done                              # close the intent
itt inspect                           # read workspace state (primary read interface)
```

## Commands

All output is JSON. No flags needed.

| Command | Purpose |
|---------|---------|
| `itt init` | Initialize `.intent/` in a Git repo |
| `itt start <title>` | Create and activate an intent |
| `itt snap <title> [-m why]` | Record a checkpoint (adopted by default) |
| `itt snap <title> --candidate` | Record without adopting (for comparison) |
| `itt adopt [cp-id] [-m why]` | Adopt a candidate checkpoint |
| `itt revert [-m why]` | Revert last adopted checkpoint |
| `itt done [intent-id]` | Close the active intent |
| `itt inspect` | Machine-readable workspace snapshot |
| `itt list <intent\|checkpoint>` | List objects |
| `itt show <id>` | Show a single object |

## Protocol

1. Run `itt inspect` before substantive work.
2. If not initialized, run `itt init`.
3. If no active intent, run `itt start`.
4. Use `itt snap` for meaningful steps. Default is adopted — use `--candidate` only when comparing alternatives.
5. Run `itt inspect` after state-changing commands.
6. Run `itt done` when the intent is resolved.

## Object model

Two objects:

- **Intent**: the problem being worked on (`open` → `done`)
- **Checkpoint**: a recorded step with rationale (`adopted`, `candidate`, or `reverted`)

## Workspace status

- `idle` — no active intent
- `active` — intent is open
- `conflict` — multiple candidates need resolution

## Guardrails

- Do not invent object IDs.
- Do not create noisy checkpoints for trivial edits.
- If you skip Intent during substantive work, explain why.
