# Intent — semantic history

This repo uses Intent (`.intent/`) to track what you're doing and why.
If `itt` is not found, use `python3 -m intent_cli` instead.

## Workflow

1. **Session start** → run `itt inspect` to check workspace state
   - **active** → read the intent and latest snap rationale, continue where it left off
   - **suspended intents** → consider `itt resume [id]`
   - **idle** → `itt start "<goal>"` if this session involves substantive work
2. **Begin substantive work** → `itt start "What goal am I pursuing"`
   - An intent is a goal, not a task — keep it high-level
   - Skip for trivial questions or tiny edits
3. **Before each git commit** → `itt snap "What I did" -m "Why, and what comes next"`
   - Snap before commit, not after — this is the key trigger point
4. **Switching context** → `itt suspend`, then `itt start` or `itt resume`
5. **Goal complete** → `itt done`

## Object semantics

- **Intent** = a goal, not a task. One intent may span multiple snaps and commits.
  Title answers: "What problem am I solving?"
  Example: "Migrate auth to JWT", not "Add JWT token generation".
- **Snap** = a step taken toward the intent. Title answers: "What did I do?"
- **Rationale** (`-m`) = the most valuable field. It must give the next session
  everything it needs to continue without re-explaining. Include:
  - What's done, what's in progress, what's remaining
  - Decisions made and why
  - Strategic context (constraints, deadlines, dependencies)

All `itt` output is JSON — parse it, don't guess.
