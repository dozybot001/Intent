# Explicit IntHub pull

Read only when the user explicitly asks to pull this repository's Intent history from IntHub. This permits a private download and validated local restoration, not new semantic records, push, account login, token management, endpoint changes, public grants, or Git remote changes. Automatic maintenance and read-only recovery never imply pull.

1. Follow [execution.md](execution.md), fix cwd to the target Git root, and inspect local history. If the explicitly requested restoration destination has no `.intent/`, initialize it with `itt init`, then inspect again. A preview-only or no-local-change request never authorizes init: report the prerequisite instead. Diagnose graph warnings with doctor and stop; do not bypass a damaged history or recreate its storage.
2. Run `itt hub status`, then `itt auth status` against the effective endpoint. Require `ok: true` and `authenticated: true`; credential availability alone is insufficient. If authentication fails, ask the user to log in themselves, without requesting pasted tokens. Do not link a new workspace merely to pull.
3. Run `itt pull`; use `--workspace ID` only for the user-selected source. A saved pull source takes precedence over the destination's workspace; otherwise a linked checkout selects its own workspace. An unbound checkout can default only when exactly one synced source exists. For `WORKSPACE_REQUIRED`, surface the structured candidate IDs and ask once rather than picking the newest or merging tracks. HTTP errors carry server details under `error.details.response.error`.
4. `--dry-run` downloads and validates without installing; use it for requested preview or necessary diagnosis, not as a mandatory extra round trip. A successful no-op can preserve local changes when upstream is unchanged. Conflicts, invalid snapshots, and concurrent local changes stop pull without overwriting history; there is no force or automatic merge. Never delete local objects to make it succeed.
5. Parse the result and inspect after an applied restoration. Report source workspace, batch/sequence, counts, and changed/no-op status. `pull` preserves this checkout's identity; a new checkout remains unlinked, with provenance only. A later separately authorized push requires linking its own workspace, never adopting the source's ID.

On `PULL_APPLY_FAILED`, stop writes and report `recovery_required` and `committed` accurately: committed data may already be installed despite a cleanup error. One inspect or hub status may trigger the CLI's locked journal recovery and establish current state; it does not turn the failed command into success. Do not edit the journal, roll back by hand, or blindly replay pull. Process interruption also permits one such reconciliation under the execution guardrails.

```text
itt pull [--workspace ID] [--api-base-url URL] [--token TOKEN] [--dry-run]
```

Prefer existing credential-helper authentication; never echo tokens. Pull imports all lifecycle states and append-only Snap content from one complete raw snapshot, not the UI's merged project view. It restores stored history, not missing work from old chats or code.
