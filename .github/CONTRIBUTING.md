# Contributing to Intent

Thanks for your interest in contributing to Intent.

## Getting Started

```bash
git clone https://github.com/dozybot001/Intent.git
cd Intent
pip install -e .
npx skills add dozybot001/Intent -g --all
```

Run tests before opening a PR:

```bash
python -m pytest -q
```

## Development Workflow

This project dogfoods Intent. Local writes require either explicit one-off recording permission or explicit automatic-maintenance enablement; contributing alone grants neither. When the user asks to record through Intent, begin with `itt inspect`; if that first inspect returns `NOT_INITIALIZED`, the explicit recording request permits `itt init` and a second inspect. Recovery remains read-only unless the user asks to continue the recovered work.

```bash
itt inspect       # see current state
itt init          # only after authorized recording returns NOT_INITIALIZED
itt inspect       # repeat after the authorized initialization
```

Reuse a semantically matching active Intent, or reactivate a relevant suspended Intent, before creating a new one. Zero writes is valid when there is no new high-signal semantic information. Before suspending open work, make its latest Snap a self-contained continuation checkpoint.

The automatic-maintenance contract is a one-time local opt-in for one named repository or task through the active Skill or another recorded agent instruction: each turn starts with inspect, records only verified important milestones during the work, and closes as `recorded`, `no-op`, or `failed`. Per-turn closure does not mean per-turn Snap creation, and records must not be split by query, file, command, or tool call. This repository does not ship an automatic-enable or turn-receipt CLI command, and Codex hooks for this flow are not implemented or enabled. Do not claim hook-enforced evidence or silently infer enablement. Enablement must separately authorize initialization of an uninitialized repository and must not imply IntHub login or sync, automatic Decisions, or query-end `suspend` / `done` transitions.

## Reporting Bugs

Open a [GitHub issue](https://github.com/dozybot001/Intent/issues/new?template=bug_report.md) with:

- What you expected to happen
- What actually happened
- The `itt` command and its JSON output
- Your Python version and OS

## Submitting Changes

1. Fork the repo and create a branch
2. Make your changes and add tests when behavior changes
3. Run `python -m pytest -q` and confirm all tests pass
4. Open a pull request with a clear description

## Project Structure

```text
src/intent_cli/       CLI source (published via pip install .)
apps/                 IntHub Local (API + Web UI)
SKILL.md              Agent skill specification
docs/                 Documentation and references
tests/                Test suite
```

## Code Style

- Keep it simple. Don't over-engineer.
- No external dependencies for the CLI.
- Add tests for new commands and behavior changes.
