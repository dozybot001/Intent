English | [简体中文](../CN/demo.md)

# Intent Demo

This document provides reproducible local demos for seeing how Intent records semantic history alongside Git.

## Agent Demo

The repository includes a runnable agent demo:

```bash
scripts/demo_agent.sh
```

The script will:

- create a temporary Git repository
- initialize Intent
- read `itt inspect` to understand current state
- follow `suggested_next_action` to move through the workflow
- complete the full `start → snap → done` loop

What to look for:

- `inspect` returns machine-consumable `suggested_next_action`
- the action payload contains a display-friendly `command` and a `reason`
- an agent can move through the workflow by following structured suggestions

## Log Demo

```bash
scripts/demo_history.sh
```

The script will:

- create a temporary Git repository
- initialize Intent
- create an intent and record checkpoints with rationale
- show how `inspect` provides a structured workspace snapshot

## Smoke Test

```bash
scripts/smoke.sh
```

Runs the full command set: init, start, snap, snap --candidate, adopt, revert, list, show, inspect, done.

## Full Validation

If you want one command that runs the current local verification set, use:

```bash
scripts/check.sh
```
