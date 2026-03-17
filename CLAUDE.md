# Intent CLI – Development Guidelines

## Project

- Python 3.9+, stdlib only, no external dependencies.
- Dev entry point: `python3 ./itt`
- Tests: `python3 -m unittest discover -s tests -v`

## Intent workflow

This repo uses Intent to record semantic history. Follow this workflow:

1. **Session start** → run `python3 ./itt inspect` to see current state
   - If workspace is `active`, continue the existing intent
   - If workspace is `idle`, decide whether this session needs an intent
2. **Begin substantive work** → `python3 ./itt start "What problem am I solving"`
   - Skip for trivial questions or tiny edits
3. **Before each git commit** → `python3 ./itt snap "What I did" -m "Why"`
   - This is the key trigger point — snap before commit, not after
4. **Work complete** → `python3 ./itt done`

## Rules

- All output is JSON. No `--json` flag needed.
- Do not invent object IDs.
- Use `--candidate` only when genuinely comparing alternatives.
