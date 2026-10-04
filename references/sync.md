# IntHub push

Use when the user asks to upload Intent history now. Recording permission and future plans to upload do not authorize a current push.

Inspect the target semantic repository and resolve graph damage before uploading. An empty history needs no upload.

`itt remote` shows the endpoint and project name. The default project name is the local repository directory name, independent of Git origin. To choose another project or endpoint, use `itt remote add origin URL --project NAME` within the user's scope. Multiple local copies use the same remote/project, not different workspace IDs.

Check `itt auth status` against that endpoint. Existing account authentication is global; do not ask for credentials again when it works. If login is needed, let the user sign in through `itt auth login`, without requesting a pasted token.

Run `itt push`. It links the project when needed, saves a content-addressed revision, and reports `changed: false` when nothing needs uploading. There is no manual commit or staging area. A stale/divergent baseline is rejected; do not overwrite or force it. Recover safe failures using [execution.md](execution.md). A read-only `itt status` can establish whether an interrupted upload was accepted.

```text
itt remote
itt remote add origin URL --project NAME
itt auth status [--api-base-url URL]
itt status [--local]
itt push [--project NAME] [--api-base-url URL] [--dry-run]
```

`status` reports `empty`, `up_to_date`, `ahead`, `behind`, or `diverged`; `--local` needs no network. `push --dry-run` previews without remote writes. `itt hub sync` is a compatibility alias.

Credentials use the existing Git credential helper for secure storage only; semantic history does not use Git. Never include tokens in repository files, output, or logs.
