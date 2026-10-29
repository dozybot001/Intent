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
python -m pytest -q
```

PostgreSQL integration tests are skipped unless `INTHUB_TEST_POSTGRES_URL` points at a disposable database, for example one started with `docker run --rm -e POSTGRES_PASSWORD=test -p 5432:5432 postgres`.

To work on the agent skill locally, install it from your checkout with `npx skills add ./ -g --all`.

## Development Workflow

This project dogfoods Intent. Local writes require either explicit one-off recording permission or explicit automatic-maintenance enablement; contributing alone grants neither. When the user asks to record through Intent, begin with `itt inspect`; if that first inspect returns `NOT_INITIALIZED`, the explicit recording request permits `itt init` and a second inspect. Recovery remains read-only unless the user asks to continue the recovered work.

```bash
itt inspect       # see current state
itt init          # only after authorized recording returns NOT_INITIALIZED
itt inspect       # repeat after the authorized initialization
```

Reuse a semantically matching active Intent, or reactivate a relevant suspended Intent, before creating a new one. Zero writes is valid when there is no new high-signal semantic information. Before suspending open work, make its latest Snap a self-contained continuation checkpoint.

Continuous maintenance is a project-local opt-in (`itt init` for new histories, `itt maintenance on` for existing ones): each turn starts with inspect, records only verified important milestones, and closes as `recorded`, `no-op`, or `failed` through `itt maintenance close`. Per-turn closure does not mean per-turn Snap creation, and records must not be split by query, file, command, or tool call. Project-local Codex hooks supply the opening context and Stop check once the user trusts them; configuration alone is not evidence that a host executed them (see [references/codex-hooks.md](../references/codex-hooks.md)). Enablement never implies IntHub login or sync, automatic Decisions, or query-end `suspend` / `done` transitions.

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
