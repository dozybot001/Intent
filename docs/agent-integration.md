# Agent Integration

Copy the snippet for your platform into your project. Your agent will start using `.intent/` automatically.

## Object semantics

Teach your agent what the objects mean, not just the commands:

- **Intent** = a goal or objective, not a single task. One intent may span multiple snaps and commits. Title answers: "What problem am I solving?" Example: "Migrate auth to JWT", not "Add JWT token generation".
- **Snap** = a step taken toward the intent. Title answers: "What did I do?" The `-m` rationale answers: "Why, and what comes next?" Example: `itt snap "Add refresh token" -m "Token rotation not yet done — security priority. Next: implement rotation logic"`.
- **Rationale is the most valuable field.** It should capture decision context and forward state — things the next session can't derive from code alone. For progress-tracking snaps, include the full picture: what's done, what's in progress, what's remaining, and any strategic context (constraints, threats, deadlines). A future session should be able to reconstruct the entire plan from the latest snap's rationale alone.
- **Use `suspend` / `resume`** when switching between goals. Don't close an intent that isn't finished.

## Claude Code (CLAUDE.md)

Add to your project's `CLAUDE.md`:

```markdown
## Intent workflow

This repo uses Intent to record semantic history. Follow this workflow:

1. **Session start** → run `itt inspect` to see current state
   - If workspace is `active`, read the intent and latest snap, then continue
   - If `suspended_intents` is non-empty, consider `itt resume`
   - If workspace is `idle`, decide whether this session needs an intent
2. **Begin substantive work** → `itt start "What goal am I pursuing"`
   - An intent is a goal, not a task — keep it high-level
   - Skip for trivial questions or tiny edits
3. **Before each git commit** → `itt snap "What I did" -m "Why, and what comes next"`
   - The rationale should capture what the next session needs to know
   - Include progress state, pending work, and decision context
4. **Switching context** → `itt suspend` then `itt start` or `itt resume`
5. **Goal complete** → `itt done`
```

## Cursor (.cursor/rules)

Create `.cursor/rules/intent.mdc`:

```markdown
---
description: Use Intent to record semantic history
alwaysApply: true
---

This repo uses Intent (`itt`) to record what you do and why.

**Objects:** Intent = goal (high-level). Snap = step taken, with rationale.

On session start, run `itt inspect` to check workspace state and recover context.
Before each git commit, run `itt snap "What I did" -m "Why, and what comes next"`.
Use `itt start` / `itt done` to open and close goals.
Use `itt suspend` / `itt resume` when switching between goals.

The rationale (`-m`) is the most valuable field — capture decisions, progress, and what the next session needs to know.
```

## AGENTS.md

Add to your `AGENTS.md`:

```markdown
## Semantic History

This repo uses [Intent](https://github.com/dozybot001/Intent) to record decision context.

- Run `itt inspect` at session start to recover prior context
- Intent = goal (high-level), snap = step taken with rationale
- Run `itt snap "title" -m "why, and what comes next"` before each commit
- The rationale should capture decisions and forward state, not just describe the diff
- Run `itt start` / `itt done` to bracket goals; `itt suspend` / `itt resume` to switch
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
