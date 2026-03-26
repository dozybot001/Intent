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

This project uses Intent to manage its own development. If you have `itt` installed:

```bash
itt init          # if your fork doesn't have .intent/ yet
itt inspect       # see current state
```

Create an intent before starting meaningful work, and create a snap when you reach a meaningful checkpoint.

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
pages/                Static site & showcase data (GitHub Pages)
docs/                 Documentation and references
tests/                Test suite
```

## Code Style

- Keep it simple. Don't over-engineer.
- No external dependencies for the CLI.
- Add tests for new commands and behavior changes.
