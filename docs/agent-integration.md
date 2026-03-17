# Agent Integration

Copy the snippet for your platform into your project. Your agent will start using `.intent/` automatically.

## Claude Code (CLAUDE.md)

Add to your project's `CLAUDE.md`:

```markdown
## Intent workflow

This repo uses Intent to record semantic history. Follow this workflow:

1. **Session start** → run `itt inspect` to see current state
   - If workspace is `active`, continue the existing intent
   - If workspace is `idle`, decide whether this session needs an intent
2. **Begin substantive work** → `itt start "What problem am I solving"`
   - Skip for trivial questions or tiny edits
3. **Before each git commit** → `itt snap "What I did" -m "Why"`
4. **Work complete** → `itt done`
```

## Cursor (.cursor/rules)

Create `.cursor/rules/intent.mdc`:

```markdown
---
description: Use Intent to record semantic history
alwaysApply: true
---

This repo uses Intent (`itt`) to record what you do and why.

On session start, run `itt inspect` to check workspace state.
Before each git commit, run `itt snap "What I did" -m "Why"`.
Use `itt start` / `itt done` to open and close work units.
```

## AGENTS.md

Add to your `AGENTS.md`:

```markdown
## Semantic History

This repo uses [Intent](https://github.com/dozybot001/Intent) to record decision context.

- Run `itt inspect` at session start to recover prior context
- Run `itt snap "title" -m "rationale"` before each commit
- Run `itt start` / `itt done` to bracket units of work
- All output is JSON — parse it, don't guess
```

## Any Agent

The `.intent/` directory is plain JSON files. Any agent can read them directly:

```
.intent/
  state.json            → workspace status (idle/active/conflict)
  intents/              → goal objects
    intent-001.json
  snaps/                → step objects with rationale
    snap-001.json
```

Or use the CLI:

```bash
itt inspect              # one-call workspace summary
itt show snap-001        # full detail on any object
itt list snap            # all snaps, newest first
```
