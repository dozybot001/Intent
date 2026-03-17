English | [简体中文](CHANGELOG.CN.md)

# Changelog

All notable project changes should be recorded here.

## 0.2.0-rc.1 - 2026-03-17

### Added

- repo-backed install flow rooted in `setup/install.sh`, with a fixed local checkout under `~/.intent/repo`
- bundled agent integration assets under `setup/` for Codex, Claude, and Cursor
- bilingual `distribution.md` and `structure.md` docs to explain the new install and repository layout

### Changed

- the end-user install path now starts from a GitHub command, exposes `~/.intent/bin/itt`, and uses the checked-out repo as the canonical runtime source
- write-side commands now accept selectors such as `--checkpoint @current` and `--adoption @latest`
- `STATE_CONFLICT` recovery now returns candidate checkpoints and a concrete `itt checkpoint select <id>` next step
- Codex and Claude skills now teach the inspect-first loop, selector-based writes, and explicit conflict recovery

### Fixed

- Cursor helper guidance now points to the generated helper path under `~/.intent/generated/cursor`

### Notes

- prerelease tag target: `v0.2.0-rc.1`
- the package version is now `0.2.0rc1`
- this prerelease is intended to validate install flow and agent skill ergonomics before stable `v0.2.0`

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

- the package version is `0.1.0`
- this is the first tagged release for the repository
