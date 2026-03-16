English | [简体中文](CHANGELOG.CN.md)

# Changelog

All notable project changes should be recorded here.

This project does not have a public release yet. The entries below describe the current release baseline under preparation.

## 0.1.0 - Unreleased

### Added

- initial local `.intent/` object layer
- primary surface flow: `init`, `start`, `snap`, `adopt`, `revert`, `status`, `inspect`, `log`
- canonical and read-side commands for `intent`, `checkpoint`, `adoption`, `run`, and `decision`
- structured machine-readable responses for `status --json`, `inspect --json`, and write commands
- `run start/end/list/show` and `decision create/list/show`
- human demo, agent demo, smoke script, and unified `scripts/check.sh`
- baseline GitHub Actions CI and package build verification

### Changed

- documentation was reorganized into bilingual EN/CN trees under `docs/`
- README now includes local install and validation entry points
- core CLI modules were split into smaller files for constants, errors, git helpers, helpers, and rendering

### Notes

- the package version is currently `0.1.0`
- this changelog entry is the release baseline, not a tagged release announcement
