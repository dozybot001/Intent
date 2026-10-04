# IntHub pull

Use when the user asks to download and restore Intent history. Pull does not authorize later uploads or changing unrelated repositories.

Inspect the destination and initialize missing `.intent/` when the requested restoration needs it. Read-only previews do not initialize. Confirm the remote endpoint/project with `itt remote`; use `itt remote add origin URL --project NAME` if the destination directory name differs from the remote project. Git origin has no role in shared-history synchronization.

Reuse existing global account authentication and run `itt pull`. Empty local history can restore a project; an unchanged local baseline can advance to the remote snapshot. If only local history changed, pull leaves it intact. If both sides changed, it reports `HISTORY_DIVERGED` and preserves both. There is no force or automatic merge.

Verify the resulting graph and report the project, revision, object counts, and changed/no-op result. Recover transient failures or interrupted installation using [execution.md](execution.md); inspect current state before replaying an uncertain operation.

```text
itt remote add origin URL --project NAME
itt status [--local]
itt pull [--project NAME] [--api-base-url URL] [--dry-run]
```
