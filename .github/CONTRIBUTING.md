# Contributing to Intent

Thanks for your interest in contributing to Intent.

## Getting Started

```bash
git clone https://github.com/dozybot001/Intent.git
cd Intent
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[server,release]"   # IntHub server dependencies + pytest
```

Run tests before opening a PR (Node.js is needed for the web UI logic tests):

```bash
python -m pytest -q                # the full suite
python scripts/changed_tests.py    # only the tests your uncommitted changes affect
```

Pass a commit, such as `python scripts/changed_tests.py HEAD~2`, to include what changed since then.

PostgreSQL integration tests are skipped unless `INTHUB_TEST_POSTGRES_URL` points at a disposable database, for example one started with `docker run --rm -e POSTGRES_PASSWORD=test -p 5432:5432 postgres`.

To work on the agent skill locally, install it from your checkout with `npx skills add ./ -g -a claude-code -a codex`.

## Development Workflow

This repo dogfoods Intent, and maintainers record milestones with `itt`.
You don't need to use Intent to contribute.
If you want to try it, `itt inspect` shows the current state.
`.intent/` is not in Git, so run `itt init` first in a fresh clone.

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
src/intent_cli/       CLI (`itt`), standard library only
apps/inthub_api/      IntHub server: API, auth, history storage
apps/inthub_web/      IntHub web app (static, no build step)
apps/inthub_local/    `itt hub start` launcher for a local IntHub
SKILL.md, references/ Agent skill and its on-demand references
scripts/              Installers and the skill's argv adapter
deploy/inthub/        Production release tooling (maintainers)
docs/                 User documentation (EN and CN)
tests/                Test suite (pytest + Node logic tests)
```

## Code Style

- Keep it simple. Don't over-engineer.
- No external dependencies for the CLI.
- Add tests for new commands and behavior changes.
