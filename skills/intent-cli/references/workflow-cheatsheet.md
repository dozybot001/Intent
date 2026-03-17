# Workflow Cheatsheet

## Core loop

```bash
itt init
itt start "Problem description"
itt snap "What I did" -m "Why"
itt done
```

## Read

| Need | Command |
| --- | --- |
| full workspace state | `itt inspect` |
| list objects | `itt list intent` / `itt list checkpoint` |
| single object | `itt show <id>` |

## Candidate comparison (rare)

```bash
itt snap "Option A" --candidate
itt snap "Option B" --candidate
itt adopt cp-002 -m "B is better"
```

## Other

```bash
itt revert -m "Changed mind"
itt done intent-001                   # close specific intent by ID
```

## Workspace status

| Status | Meaning | Next move |
| --- | --- | --- |
| `idle` | no active intent | `itt start` |
| `active` | intent is open | `itt snap` or `itt done` |
| `conflict` | multiple candidates | `itt adopt <id>` |

## All output is JSON

No flags needed. Every command returns structured JSON.
