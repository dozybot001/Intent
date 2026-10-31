# IntHub pull

Use when the user asks to download and restore Intent history. Pull does not authorize later uploads or changing unrelated repositories.

Inspect the destination and initialize missing `.intent/` when the requested restoration needs it. Read-only previews do not initialize. Confirm the remote endpoint/project with `itt remote`; use `itt remote add origin URL --project NAME` if the destination directory name differs from the remote project. Git origin has no role in shared-history synchronization.

Reuse existing global account authentication; when missing, follow [onboarding.md](onboarding.md) for sign-in, then run `itt pull`. In a folder with no `.intent/`, `itt clone PROJECT` sets Intent up and brings the history and branches in one step; only members can clone. Pull fetches the remote, then merges it into the current branch. `MERGE_CONFLICT` lists each field with both values: settle what the task already decides with `itt resolve ID --ours|--theirs|--status S`, ask the user about the rest, then `itt merge --continue`.

Verify the resulting graph and report the project, revision, object counts, and changed/no-op result. Recover transient failures or interrupted installation using [execution.md](execution.md); inspect current state before replaying an uncertain operation.

```text
itt remote add origin URL --project NAME
itt status [--local]
itt fetch [--project NAME] [--api-base-url URL]
itt pull [--project NAME] [--api-base-url URL] [--dry-run]
itt clone PROJECT [--api-base-url URL]
```
