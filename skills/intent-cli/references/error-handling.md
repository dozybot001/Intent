# Error Handling

All errors return JSON with `"ok": false` and an `error` object containing `code`, `message`, and optional `details` and `suggested_fix`.

## Error codes

### `GIT_STATE_INVALID`

Not inside a Git worktree. Move to a repo or run `git init`.

### `NOT_INITIALIZED`

`.intent/` not found. Run `itt init`.

### `STATE_CONFLICT`

Common causes:
- `itt snap` without an active intent
- `itt start` while another intent is open
- `itt adopt` with multiple candidates and no ID specified

What to do: run `itt inspect`, check `workspace_status` and `candidate_checkpoints`, then follow `suggested_next_action`.

### `OBJECT_NOT_FOUND`

The requested ID does not exist. Run `itt list` to find valid IDs. Never guess.

### `INVALID_INPUT`

Bad command syntax or invalid reference.

## Recovery rule

When state is unclear:

```bash
itt inspect
```

Use the returned `workspace_status`, `candidate_checkpoints`, and `suggested_next_action` to decide the next step.
