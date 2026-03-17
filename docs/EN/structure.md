English | [简体中文](../CN/structure.md)

# Repository Structure

Purpose: explain the current repository layout, the role of each top-level path, and which directories are source-of-truth versus local or generated state.

## What This Document Answers

- what the current project tree looks like after the install-path cleanup
- which directories belong to CLI source code, install assets, docs, tests, and local Intent state
- which paths are meant for contributors versus end users

## What This Document Does Not Answer

- the full CLI contract or JSON schema
- the detailed install journey across agents
- release policy or roadmap prioritization

## Canonical Source Tree

This tree focuses on the source-of-truth paths and omits generated artifacts such as `build/`, `dist/`, `.venv/`, and `src/intent_cli.egg-info/`.

```text
Intent/
|-- AGENTS.md
|-- CHANGELOG.CN.md
|-- CHANGELOG.md
|-- LICENSE
|-- README.CN.md
|-- README.md
|-- docs/
|   |-- README.md
|   |-- CN/
|   |   |-- README.md
|   |   |-- cli.md
|   |   |-- demo.md
|   |   |-- distribution.md
|   |   |-- glossary.md
|   |   |-- i18n.md
|   |   |-- release.md
|   |   |-- roadmap.md
|   |   |-- structure.md
|   |   `-- vision.md
|   `-- EN/
|       |-- README.md
|       |-- cli.md
|       |-- demo.md
|       |-- distribution.md
|       |-- glossary.md
|       |-- i18n.md
|       |-- release.md
|       |-- roadmap.md
|       |-- structure.md
|       `-- vision.md
|-- itt
|-- pyproject.toml
|-- scripts/
|   |-- check.sh
|   |-- demo_agent.sh
|   |-- demo_log.sh
|   `-- smoke.sh
|-- setup/
|   |-- README.md
|   |-- install.sh
|   |-- manifest.json
|   |-- claude/
|   |   `-- SKILL.md
|   |-- codex/
|   |   `-- SKILL.md
|   `-- cursor/
|       |-- README.md
|       `-- intent.mdc
|-- src/
|   `-- intent_cli/
|       |-- __init__.py
|       |-- __main__.py
|       |-- cli.py
|       |-- constants.py
|       |-- core.py
|       |-- distribution.py
|       |-- errors.py
|       |-- git.py
|       |-- helpers.py
|       |-- render.py
|       `-- store.py
|-- tests/
|   `-- test_cli.py
`-- .intent/
    |-- config.json
    |-- state.json
    |-- adoptions/
    |-- checkpoints/
    |-- decisions/
    |-- intents/
    `-- runs/
```

## Top-Level Paths

- `README.md` and `README.CN.md`: GitHub entry points for contributors and end users.
- `CHANGELOG.md` and `CHANGELOG.CN.md`: release-facing change summaries.
- `AGENTS.md`: repository-specific guidance for coding agents working in this repo.
- `pyproject.toml`: Python packaging metadata and the `itt` console entrypoint declaration for contributor installs.
- `itt`: the repository-local launcher used in development and also copied into the fixed checkout model.
- `src/intent_cli/`: the actual CLI implementation.
- `setup/`: end-user install assets and agent-specific setup resources.
- `docs/`: the bilingual long-form documentation set.
- `scripts/`: validation and demo scripts used during development.
- `tests/`: automated test coverage for the CLI and install flow.
- `.intent/`: local semantic history for dogfooding Intent inside the Intent repository.

## CLI Source Layout

- `cli.py`: command parser and command dispatch.
- `core.py`: workspace state machine and object lifecycle logic.
- `distribution.py`: install-path and agent-setup behavior built around the fixed checkout model.
- `store.py`: local object persistence under `.intent/`.
- `git.py`: Git state inspection and linkage helpers.
- `render.py`: human-readable output rendering.
- `helpers.py`, `constants.py`, `errors.py`: shared utility, exit code, and error-model support.
- `__main__.py` and `__init__.py`: module entrypoints and package metadata glue.

## Setup Layout

`setup/` is the single source of truth for end-user installation assets.

- `install.sh`: the user-facing install script shown on the GitHub homepage.
- `manifest.json`: machine-readable integration metadata consumed by `itt integrations list`, `itt setup`, and `itt doctor`.
- `codex/` and `claude/`: file-based skill assets that can be installed automatically.
- `cursor/`: helper assets for the current manual-follow-up Cursor path.
- `README.md`: a concise explanation of how the fixed checkout model uses this directory.

## Documentation Layout

- `docs/EN/` and `docs/CN/`: mirrored English and Simplified Chinese documentation trees.
- `docs/*/README.md`: per-language documentation index.
- `cli.md`: command semantics and CLI contract.
- `distribution.md`: install path and agent integration journey.
- `structure.md`: this repository layout reference.
- `vision.md`, `roadmap.md`, `release.md`, `demo.md`, `glossary.md`, `i18n.md`: project framing, planning, release, and terminology support.

## Local And Generated State

Some paths exist in local checkouts but are not part of the maintained source tree:

- `.intent/`: intentional local workspace data for this repository itself.
- `build/`, `dist/`: generated packaging output.
- `src/intent_cli.egg-info/`: packaging metadata generated during local builds or editable installs.
- `.venv/`: contributor-local virtual environment when present.
- `.DS_Store`: macOS filesystem metadata, not project structure.

The current end-user install journey should not depend on these generated paths. The maintained runtime source of truth remains the fixed checkout plus `setup/`.
