# AGENTS.md instructions for this repository

## Skills

A skill is a set of local instructions stored in a `SKILL.md` file. Use the project skill below when the task is about understanding or operating Intent CLI in this repository.

### Available skills

- intent-cli: Use when you need to operate the Intent CLI semantic history layer in a Git repository. This skill covers the core `init → start → snap → done` loop, workspace inspection, and dogfooding Intent inside the Intent project. (file: `skills/intent-cli/SKILL.md`)

### How to use skills

- Discovery: If the user names a skill or the task clearly matches a listed skill, use it for that turn.
- Loading: Open the skill `SKILL.md` first. Only read bundled references when they are needed.
- Scope: Keep the conversation anchored to the repository state. Do not invent Intent objects or IDs that are not present in the workspace.
- Dogfooding: When working inside the Intent repository itself, use the skill's dogfooding guidance.
- Required protocol: For substantive project work in this repository, treat Intent as an active working layer. Before doing substantial implementation or design work, first run `itt inspect`, decide whether to continue an existing intent or create a new one, and record meaningful checkpoints as the work progresses.
- Required explanation on omission: If a substantive work pass does not create or update any Intent record, explicitly say why the omission is correct for this pass.
- Restraint: Do not force Intent objects for trivial read-only answers or tiny clarifications. Continue an existing active intent when it already matches the user's request; only start a new one when the work meaningfully shifts.
