# Intent CLI – Development Guidelines

## Project

- Python 3.9+, stdlib only, no external dependencies.
- Dev entry point: `python3 ./itt`
- Tests: `python3 -m unittest discover -s tests -v`

## Intent workflow

This repo uses Intent to record semantic history. Follow this workflow:

1. **Session start** → run `python3 ./itt inspect` to see current state
   - If workspace is `active`, read the intent and latest snap, then continue
   - If `suspended_intents` is non-empty, consider `python3 ./itt resume`
   - If workspace is `idle`, decide whether this session needs an intent
2. **Begin substantive work** → `python3 ./itt start "What goal am I pursuing"`
   - An intent is a goal, not a task — keep it high-level
   - Skip for trivial questions or tiny edits
3. **Before each git commit** → `python3 ./itt snap "What I did" -m "Why, and what comes next"`
   - The rationale should capture what the next session needs to know
   - Include progress state, pending work, and decision context
   - This is the key trigger point — snap before commit, not after
4. **Switching context** → `python3 ./itt suspend` then `python3 ./itt start` or `python3 ./itt resume`
5. **Goal complete** → `python3 ./itt done`
