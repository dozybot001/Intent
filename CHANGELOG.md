English | [简体中文](CHANGELOG.CN.md)

# Changelog

All notable project changes should be recorded here.

## 0.3.0 - 2026-03-17

### Changed

- **major simplification**: reduced the object model from 5 types (intent, checkpoint, adoption, run, decision) to 2 types (intent, checkpoint)
- core loop changed from `init → start → snap → adopt → log` to `init → start → snap → done`
- intent states simplified from 4 (active, paused, completed, archived) to 2 (open, done)
- workspace states simplified from 6 to 3 (idle, active, conflict)
- all output is now JSON-only; no human-readable text mode, no `--json` flag needed
- `snap` now creates an adopted checkpoint by default; use `--candidate` for comparison workflow
- `adopt` now adopts a candidate checkpoint (no longer creates a separate adoption object)
- `revert` now directly changes checkpoint status (no separate revert record)
- `done` replaces the old `complete`/`abandon` commands for closing intents
- schema version bumped from "0.1" to "0.2"
- `.intent/` directory now contains only `intents/` and `checkpoints/` (removed `adoptions/`, `runs/`, `decisions/`)
- `state.json` simplified to 4 fields: `schema_version`, `active_intent_id`, `workspace_status`, `updated_at`
- `inspect` output flattened with `suggested_next_action` (singular, not array)

### Removed

- `status` command (use `inspect` instead)
- `log` command
- `decide` / `decision create` command
- `run start` / `run end` commands
- `checkpoint select` command
- Surface CLI vs Canonical CLI distinction
- `--json`, `--id-only`, `--no-interactive`, `--if-not-adopted` flags
- `adoption`, `run`, `decision` object types
- `mode`, `active_run_id`, `current_checkpoint_id`, `last_adoption_id` from state.json
- `config.json` `git.strict_adoption` field
- `render.py` module (no human-readable output)
- selectors (`@current`, `@latest`, `@active`)

### Added

- `done` command for closing intents
- `--candidate` flag on `snap` for comparison workflow
- `show` command with type inference from ID prefix
- repo-backed install flow rooted in `setup/install.sh`
- bundled agent integration assets under `setup/` for Codex, Claude, and Cursor

### Notes

- this is a breaking change from v0.1.0
- old `.intent/` data with schema "0.1" may need manual migration

## 0.1.0 - 2026-03-17

### Added

- initial local `.intent/` object layer
- primary surface flow: `init`, `start`, `snap`, `adopt`, `revert`, `status`, `inspect`, `log`
- canonical and read-side commands for `intent`, `checkpoint`, `adoption`, `run`, and `decision`
- structured machine-readable responses for `status --json`, `inspect --json`, and write commands
- `run start/end/list/show` and `decision create/list/show`
- human demo, agent demo, smoke script, and unified `scripts/check.sh`
- baseline GitHub Actions CI and package build verification

### Notes

- the package version is `0.1.0`
- this is the first tagged release for the repository
