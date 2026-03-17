# Dogfooding Intent Inside The Intent Repository

Use Intent CLI inside the Intent project for meaningful units of work, not for every tiny edit.

## Practical loop

```bash
python3 itt start "Refine release guidance"
python3 itt run start
python3 itt snap "Draft release-baseline update"
python3 itt adopt -m "Adopt release-baseline structure"
python3 itt decide "Keep release-note template in the release skill" --because "One source of truth is easier to maintain"
python3 itt run end
python3 itt log
```

## Heuristics

- create one intent per meaningful problem or work slice
- create checkpoints when you have real candidate states, not every save
- adopt when you are explicitly choosing a candidate
- record a decision only when the tradeoff should survive beyond the immediate edit
- end the run when that agent pass is complete

## Read pattern

- use `python3 itt status --json` for a quick workspace check
- use `python3 itt inspect --json` before write actions that depend on current semantic state
- use `python3 itt log` to review semantic history for the repository itself
