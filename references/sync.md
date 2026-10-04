# Explicit IntHub sync

Read only after the user explicitly asks to push this repository's Intent data to IntHub. Sync permits validating authentication, necessary first repository binding, and one complete snapshot push. It does not permit semantic-object writes, login/logout, token management, endpoint changes, Git remote changes, or public showcase grants. Automatic maintenance never grants sync permission.

1. Follow [execution.md](execution.md), fix cwd to the target Git root, and run `itt inspect`. `NOT_INITIALIZED` in sync-only mode means there is no snapshot to push: stop without init. Diagnose warnings with doctor and stop before network writes. Respect active Decisions; resolve a conflict with a durable local-only rule before external actions, rather than silently overriding it.
2. Run `itt hub status` to discover the effective endpoint, local binding, credential availability, and `link_pending`/`sync_pending`. Pending local state does not prove server acceptance. Do not read `.intent/hub.json` directly or inspect implementation code for account state.
3. Capture `result.api_base_url`; run `itt auth status --api-base-url URL`. Require `ok: true` and `result.authenticated: true`. A locally available credential is not proof of valid authentication. If unauthenticated, stop and ask the user to run `itt auth login --api-base-url URL` themselves; never initiate login automatically or ask for a pasted token. Tenon OIDC identifies the IntHub account independently of Git provider.
4. If not linked or `link_pending` is true, run `itt hub link --api-base-url URL`; add `--project-name NAME` only if supplied by the user. Pending links reuse persisted workspace IDs to reconcile lost responses. The explicit sync request authorizes this required binding after authentication succeeds. GitHub and Gitee origins are supported; never switch or modify `origin`.
5. Run `itt push`, omitting endpoint/token arguments when binding and credential helper select them. Pending pushes reuse sync batch IDs for unchanged payloads; the CLI has bounded in-process transport retries. `--dry-run` is only for requested preview or necessary payload diagnosis, not a replacement for real push.
6. Parse the response; report the accepted batch, project/workspace binding, and `last_synced_at`. On terminal failure, stop mutations; allow one `itt hub status` reconciliation to report binding and pending state. Never infer this repository's success from another or retry against a different provider/endpoint. If recording and sync were both requested, finish and verify local recording first.

`itt push` sends a full object snapshot, not an incremental diff. `itt hub sync` remains a compatibility alias; prefer `itt push`.

Endpoint precedence: explicit `--api-base-url`, repository binding, user config, official service `https://inthub.tenon.asia`. Credential precedence: explicit `--token`, `INTHUB_TOKEN`, Git credential helper. Prefer the helper; never echo or persist tokens in repository files or logs.

```text
itt hub status [--api-base-url URL]
itt auth status [--api-base-url URL] [--token TOKEN]
itt hub link [--project-name NAME] [--api-base-url URL] [--token TOKEN]
itt push [--api-base-url URL] [--token TOKEN] [--dry-run]
```
