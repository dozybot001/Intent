English | [简体中文](CHANGELOG.CN.md)

# Changelog

All notable project changes should be recorded here.

## 0.1.0 - 2026-03-17

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
- release baseline docs now include a stable release-notes template

### Notes

- the package version is currently `0.1.0`
- this is the first tagged release for the repository
