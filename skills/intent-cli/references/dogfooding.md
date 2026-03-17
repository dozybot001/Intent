# Dogfooding Intent Inside The Intent Repository

Use Intent CLI inside the Intent project for meaningful units of work, not for every tiny edit.

## Practical loop

```bash
python3 ./itt start "Refine release guidance"
python3 ./itt snap "Draft release-baseline update" -m "Clarifies what must be done before tagging"
python3 ./itt done
```

## Heuristics

- One intent per meaningful problem or work slice.
- Use `itt snap` when you have a real step worth recording, not every save.
- Use `-m` when the rationale matters for future reference.
- Use `--candidate` only when genuinely comparing alternatives.

## Read pattern

- `python3 ./itt inspect` before write actions that depend on current state.
- `python3 ./itt list checkpoint` to review history.
