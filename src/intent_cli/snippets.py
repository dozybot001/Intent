"""Agent integration snippets for itt setup."""

CLAUDE_MD = """\
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
"""

CURSOR_MDC = """\
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
"""

AGENTS_MD = """\
## Semantic History

This repo uses [Intent](https://github.com/dozybot001/Intent) to record decision context.

- Run `itt inspect` at session start to recover prior context
- Intent = goal (high-level), snap = step taken with rationale
- Run `itt snap "title" -m "why, and what comes next"` before each commit
- The rationale should capture decisions and forward state, not just describe the diff
- Run `itt start` / `itt done` to bracket goals; `itt suspend` / `itt resume` to switch
- All output is JSON — parse it, don't guess
"""

MARKER = "## Intent workflow"
AGENTS_MARKER = "## Semantic History"
