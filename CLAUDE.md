# Intent CLI – Development Guidelines

## Intent CLI Skill

This repository uses Intent CLI for semantic history recording. Follow the protocol in [skills/intent-cli/SKILL.md](skills/intent-cli/SKILL.md).

### Core loop

```bash
itt inspect                           # read state before work
itt start "Describe the problem"      # open an intent
itt snap "What I did" -m "Why"        # record a checkpoint (adopted by default)
itt done                              # close the intent
```

### Guardrails

- Do not invent object IDs.
- Use `itt snap --candidate` only when comparing alternatives.
- Do not create noisy checkpoints for trivial edits.
- If you skip Intent during substantive work, explain why.
- All output is JSON. No `--json` flag needed.

## Project context

- **Language:** Python 3.9+, stdlib only, no external dependencies.
- **Entry point:** `src/intent_cli/cli.py` → `python3 ./itt` during development.
- **Tests:** `python3 -m unittest discover -s tests -v`
- **Build:** `python3 -m build`
- **CI:** GitHub Actions, matrix tests on Python 3.9/3.11/3.12.
