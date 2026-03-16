English | [简体中文](../CN/demo.md)

# Intent Demo

This document provides reproducible local demos for comparing what `git log` and `itt log` answer, and for showing how an agent can move forward from `itt inspect --json`.

## Human Demo

Goal: show that `git log` is centered on commit history, while `itt log` is centered on adoption history.

Run:

```bash
scripts/demo_log.sh
```

The script will:

- create a temporary Git repository
- initialize Intent
- create one intent
- create two checkpoints
- record one adoption
- print `git log --oneline`
- print `itt log`

What to look for:

- `git log` shows commit order and commit messages
- `itt log` shows an adoption timeline, including the related intent, checkpoint, and Git head

You can also reproduce the same flow manually:

```bash
itt init
itt start "Reduce onboarding confusion"

# candidate A
itt snap "Landing page candidate A"
git add .
git commit -m "landing candidate A"

# candidate B
itt snap "Landing page candidate B"
git add .
git commit -m "landing candidate B"

itt adopt --checkpoint cp-002 -m "Adopt progressive disclosure layout"
git log --oneline
itt log
```

## Agent Demo

The repository also includes a runnable agent demo:

```bash
scripts/demo_agent.sh
```

The script will:

- create a temporary Git repository
- initialize Intent
- repeatedly read `itt inspect --json`
- extract `suggested_next_actions[0].args`
- execute the next command from the returned arguments

What to look for:

- `inspect --json` returns machine-consumable `suggested_next_actions`
- each action payload contains both a display-friendly `command` and executable `args`
- an agent can move forward through the workflow without depending on long prose instructions

## Full Validation

If you want one command that runs the current local verification set, use:

```bash
scripts/check.sh
```
