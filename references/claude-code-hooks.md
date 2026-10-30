# Project-local Claude Code maintenance

Claude Code support is an explicit, opt-in host choice. It reuses the closure model in [codex-hooks.md](codex-hooks.md): the same project flag, entry snapshot, turn token, `itt maintenance close recorded|no-op|failed` receipt, and one closure-only Stop retry. Codex remains the default host and its behavior is unchanged. Implementation: [maintenance_hooks.py](../src/intent_cli/maintenance_hooks.py); coverage: [test_maintenance.py](../tests/test_maintenance.py).

## Setup and scope

- New history: `itt init --host claude-code`. Existing history: `itt maintenance on --host claude-code` once. `itt maintenance status` follows the host configured in this root; `--host claude-code` names it explicitly.
- Intent merges two command handlers (`UserPromptSubmit`, `Stop`) into this root's `.claude/settings.local.json`, Claude Code's personal project settings file. The handlers embed this machine's Python and the absolute root, so they do not belong in the shared, usually committed `.claude/settings.json`. Other settings and hooks are preserved, a previous Intent handler is replaced rather than duplicated, and a newly created file is excluded through this clone's `.git/info/exclude`.
- `itt maintenance off` disables this root and removes only Intent's handlers from that file, deleting the file only when nothing else remains. Codex hook files are not touched.
- Nothing is written to `~/.claude/settings.json`, managed policy, permissions, another project, or a plugin. Installing the Skill or plugin never enables a project.

## Host contract used

Checked on 2026-10-29 against the official [hooks reference](https://code.claude.com/docs/en/hooks) and the hook input schema of Claude Code 2.1.309:

- Input JSON on stdin carries `session_id`, `transcript_path`, `cwd`, `permission_mode`, `hook_event_name`, and `prompt_id`, plus `prompt` (`UserPromptSubmit`) or `stop_hook_active` (`Stop`). There is no turn ID. `prompt_id` correlates one prompt with every later event until the next prompt, so it is the turn identity: a replayed entry reuses its turn, and Stop checks the matching turn. Without a usable `prompt_id` (older releases, or an entry that never ran), entry issues its own identity and Stop checks the session's latest Intent turn. The transcript is never read and the prompt is never stored.
- Entry returns `hookSpecificOutput.additionalContext`. Claude Code caps injected hook text at 10,000 characters and replaces anything longer with a file reference and a short preview, so the context is bounded at 9,500 bytes and clipping stays explicit.
- A missing receipt returns `{"decision": "block", "reason": ...}` once. Claude continues the same turn with that reason; the next Stop carries `stop_hook_active: true`, and a still-missing receipt releases with an incomplete-closure `systemMessage`.
- Handlers use shell form: `sh -c` on macOS/Linux and Git Bash on Windows. Exec form (`args`) has no documented minimum version, so it is not relied on; Windows without Git Bash, where Claude Code falls back to PowerShell, is unsupported.

## Complete first-time setup (configuration is not proof of execution)

1. Start `claude` from this exact root (the setup's `review_cwd`) and accept the workspace trust dialog. An interactive session runs no settings-file hooks before that; `-p` and SDK runs treat the folder as trusted.
2. Run `/hooks`, a read-only view, and confirm both Intent handlers from `.claude/settings.local.json`. Edits are normally picked up automatically; restart the session if they are missing. `disableAllHooks` or the managed `allowManagedHooksOnly` policy prevents execution; status reports `blocked_by` only for the file it manages.
3. Verify one real, read-only turn: injected context with a token, a successful `no-op` receipt, then `itt maintenance status --host claude-code` showing `entry_seen` and `stop_checked_receipt`. `claude --debug` logs each hook run. Observations are per host and do not attest the current session.

In the default permission mode Claude Code asks before running `itt` commands. Approve the closure command once and let Claude Code remember it, or add your own permission rule; Intent never edits permissions. Keep the handoff short: what is configured, the one user action still needed, and whether real execution has been observed.

## What is and is not guaranteed

The guarantees and limits in [codex-hooks.md](codex-hooks.md#what-is-and-is-not-guaranteed) apply. Claude Code specifics:

- Interrupting a turn skips Stop, so that turn's receipt is never checked. Subagents stop through `SubagentStop`, outside the gate; only the main agent closes the turn.
- Plan mode cannot run the closure command, so a plan-mode Stop is released without a receipt. A turn that leaves plan mode before finishing is gated normally.
- `UserPromptSubmit` also fires for scheduled tasks, background subagent reports, and cross-session messages. Each becomes its own turn with fresh context and needs its own receipt; a mid-turn one can cost the single retry.
- Context compaction can drop the injected token mid-turn. The Stop retry reason restates it, so recovery costs the one retry.
- The plugin ships only the Skill, never hooks: plugin hooks would run in every project where the plugin is enabled.

## Plugin and Skill distribution

The repository is a Claude Code plugin marketplace whose single plugin is the repository root. With no `skills/` directory or `skills` key, its root [SKILL.md](../SKILL.md) loads as the plugin's one skill, with these references unchanged, so `npx skills` and plugin users read the same instructions:

```text
/plugin marketplace add dozybot001/Intent
/plugin install intent-cli@intent
```

`npx skills add dozybot001/Intent` keeps discovering the same root Skill. Either route installs instructions only; enabling a project still needs the explicit `--host claude-code` command above.
