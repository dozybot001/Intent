# IntHub push

Use when the user asks to upload Intent history now. Recording permission and future plans to upload do not authorize a current push.

Inspect the target semantic repository and resolve graph damage before uploading. An empty history needs no upload.

`itt remote` shows the endpoint and project name. The default project name is the local repository directory name, independent of Git origin. To choose another project or endpoint, use `itt remote add origin URL --project NAME` within the user's scope. Multiple local copies use the same remote/project, not different workspace IDs.

Check `itt auth status` against that endpoint. Existing account authentication is global; do not ask for credentials again when it works. If login is needed, follow [onboarding.md](onboarding.md): user-owned interactive `itt auth login` → code approved in the browser → status verification. Never request a token in chat or pass it through the non-interactive argv adapter.

Run `itt push`. It links the project when needed, sends the current branch to the same branch on the remote, and reports `changed: false` when nothing needs uploading. There is no manual commit or staging area. If the remote moved, the push is refused: run `itt pull`, settle any conflict, then push again. There is no force mode. Recover safe failures using [execution.md](execution.md). A read-only `itt status` can establish whether an interrupted upload was accepted.

```text
itt remote
itt remote add origin URL --project NAME
itt auth status [--api-base-url URL]
itt status [--local]
itt push [--project NAME] [--api-base-url URL] [--dry-run] [--delete BRANCH]
```

`status` reports `empty`, `up_to_date`, `ahead`, `behind`, or `diverged`; `--local` needs no network. `push --dry-run` previews without remote writes. `itt hub sync` is a compatibility alias.

Credentials use the Git credential helper when one is configured, otherwise a private file beside the Intent config; semantic history does not use Git. Never include tokens in repository files, output, or logs.
