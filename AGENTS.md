# AGENTS.md instructions for /Users/dozy/Intent

## Skills

A skill is a set of local instructions stored in a `SKILL.md` file. Use the project skill below when the task is about understanding, operating, or teaching Intent CLI in this repository.

### Available skills

- intent-cli: Use when you need to understand, operate, or teach the Intent CLI workflow in a Git repository. This skill is the preferred guide for reading workspace state, following the core `init -> start -> snap -> adopt -> log` loop, using `run` and `decision`, and dogfooding Intent CLI inside the Intent project. (file: /Users/dozy/.codex/skills/intent-cli/SKILL.md)

### How to use skills

- Discovery: If the user names a skill or the task clearly matches a listed skill, use it for that turn.
- Loading: Open the skill `SKILL.md` first. Only read bundled references when they are needed.
- Scope: Keep the conversation anchored to the repository state. Do not use the skill to invent Intent objects or IDs that are not present in the workspace.
- Dogfooding: When working inside the Intent repository itself, use the skill's dogfooding guidance before creating local Intent objects.
- Required protocol: For substantive project work in this repository, treat Intent as an active working layer rather than a passive log. Before doing substantial implementation, design, or multi-step documentation work, first read `python3 itt inspect --json`, decide whether to continue an existing intent or create a new one, and then record meaningful `run`, `checkpoint`, `adoption`, and `decision` events as the work progresses.
- Required explanation on omission: If a substantive work pass does not create or update any Intent record, explicitly say why the omission is correct for this pass.
- Restraint: Do not force Intent objects for trivial read-only answers or tiny clarifications. Continue an existing active intent when it already matches the user's request; only start a new one when the work meaningfully shifts.
