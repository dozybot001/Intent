English | [简体中文](../CN/release.md)

# Release Baseline

This document defines the minimum release-ready checklist for the current CLI stage.

## Goal

Before creating a GitHub release, confirm that the repository is:

- installable
- testable
- demoable
- documented

## Minimum Checklist

- version is correct in [pyproject.toml](../../pyproject.toml)
- [CHANGELOG.md](../../CHANGELOG.md) is updated for the release target
- [README.md](../../README.md) and [README.CN.md](../../README.CN.md) still match the current CLI
- [docs/EN/cli.md](cli.md) and [docs/CN/cli.md](../CN/cli.md) match the implementation
- [scripts/check.sh](../../scripts/check.sh) passes locally
- GitHub Actions CI is green
- the package still builds as sdist and wheel
- the built wheel can be installed into a clean environment and the `itt` entry point still runs

## Local Commands

```bash
./scripts/check.sh
python3 itt version
python3 -m build
```

## Release Notes Scope

For the current stage, release notes should cover:

- the 2-object model (intent, checkpoint)
- the `start → snap → done` core loop
- JSON-only output
- machine-readable agent entry point (`inspect`)
- agent integration setup

## Out of Scope

Do not block the current release on:

- remote sync
- platform UI
- advanced filtering
- collaboration-layer features beyond the local CLI
