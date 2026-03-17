# Intent CLI Error Handling

## `GIT_STATE_INVALID`

Meaning:

- the current directory is not inside a Git worktree

What to do:

- move to the correct repository, or
- run `git init` if the user wants to start a new Git repo first

## `NOT_INITIALIZED`

Meaning:

- the repository is a Git worktree, but `.intent/` has not been initialized

What to do:

- run `itt init` if the user wants Intent enabled here

## `STATE_CONFLICT`

Common causes:

- `itt snap` without an active intent
- `itt adopt` without a clear current checkpoint
- starting a run while another run is already active

What to do:

- inspect `itt inspect --json`
- check `candidate_checkpoints`, `active_run`, and `workspace_status_reason`
- if needed, select the intended checkpoint explicitly before adopting

## `OBJECT_NOT_FOUND`

Meaning:

- the requested object ID does not exist in the current workspace

What to do:

- re-read with `list/show`
- use selectors like `@active`, `@current`, or `@latest` when available
- never guess the missing ID

## `INVALID_INPUT`

Meaning:

- the command syntax or linked Git reference is invalid

What to do:

- check the flags again
- verify any explicit Git ref before retrying

## Recovery rule

When the state is unclear, fall back to:

```bash
itt inspect --json
```

Use the returned `workspace_status_reason`, `warnings`, `candidate_checkpoints`, and `suggested_next_actions` to decide the next safe step.
