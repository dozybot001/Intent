# Intent CLI Workflow Cheatsheet

## Core loop

```bash
itt init
itt start "Problem statement"
itt snap "Candidate A"
itt adopt -m "Adopt candidate A"
itt log
```

## Human reads

| Need | Command |
| --- | --- |
| current summary | `itt status` |
| semantic timeline | `itt log` |
| one object | `itt <object> show <id>` |

## Machine reads

| Need | Command |
| --- | --- |
| lightweight snapshot | `itt status --json` |
| stable full snapshot | `itt inspect --json` |
| object summary list | `itt <object> list --json` |
| exact object payload | `itt <object> show <id> --json` |

## Reserved selectors

When supported, these selectors avoid extra lookups:

- `itt intent show @active`
- `itt checkpoint show @current`
- `itt adoption show @latest`
- `itt run show @active`
- `itt decision show @latest`

## Canonical mapping

| Surface command | Canonical meaning |
| --- | --- |
| `itt start` | `itt intent create --activate` |
| `itt snap` | `itt checkpoint create --select` |
| `itt adopt` | `itt adoption create` |
| `itt revert` | `itt adoption revert` |
| `itt decide` | `itt decision create` |

## Workspace status

| Status | What it means | Usual next move |
| --- | --- | --- |
| `idle` | no usable Intent state yet | inspect whether init/start is needed |
| `blocked_no_active_intent` | no active intent | `itt start "<title>"` |
| `intent_active` | active intent, no current checkpoint | `itt snap "<title>"` |
| `candidate_ready` | current checkpoint is ready to adopt | `itt adopt` |
| `adoption_recorded` | adoption or revert just recorded | inspect next action or continue work |
| `conflict_multiple_candidates` | multiple viable checkpoints, no clear default | inspect and select explicitly |

## Write-command flags

| Flag | Use it when |
| --- | --- |
| `--json` | another agent or step will read the result |
| `--id-only` | you only need the created object ID |
| `--no-interactive` | the workflow must fail fast instead of prompting |
