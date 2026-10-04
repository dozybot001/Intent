# Safe local execution

Read before the first `itt` command in an authorized workflow. Applies to automatic maintenance, one-off recording, recovery, push, and pull.

1. Resolve the target semantic repository (the directory containing `.intent/`) and use it as each command's cwd. Git is optional. Make semantic changes through the CLI.
2. Pass semantics as argv data, not shell code. Prefer an argv-capable process API. In Codex's shell-text runner, resolve `scripts/itt_argv.py` relative to this Skill and run `python3 <trusted-absolute-runner-path> <encoded-argv>` with repository `workdir`. Encode `JSON.stringify(argv)` using `encodeURIComponent(...).replace(/[!'()*]/g, c => '%' + c.charCodeAt(0).toString(16).toUpperCase())`. Only that encoded token is data-derived. Do not invent a Base64 adapter or depend on unavailable `Buffer`, `btoa`, or `TextEncoder` globals.
3. Await each dependent command's completion; a running session is not a failure. Do not parse partial output as the result or overlap writes to the same history.
4. Parse terminal stdout as JSON; `ok: true` confirms success. If `NOT_INITIALIZED`, initialize only when the requested setup, recording, or restoration needs it, then inspect. Read-only recovery and sync-only requests do not create history.
5. Capture created IDs from `result.id` and existing IDs from inspect. Pass explicit IDs to transitions rather than relying on implicit object selection.
6. Diagnose errors and continue when recovery is safe within the requested task. Fix invocation errors that occurred before execution. For a busy repository, check the owner and wait; do not remove its lock. Read-only requests may be retried after transient failures. If a write's completion is unknown, inspect current state first: verify local object IDs or compare remote status. Shared-history push reconciles accepted content without creating a second revision. Never blindly replay object creation. Pause only affected operations when state remains uncertain, data conflicts, or recovery needs additional authority.
7. Diagnose graph warnings with `itt doctor`. Preserve existing objects and resume writes only after graph integrity is verified. Evaluate `suggested_fix` against the actual cause and task scope rather than executing it blindly.
8. After semantic mutations, inspect and verify affected IDs, lifecycle, and latest checkpoints. Inspect omits done/cancelled Intents: verify the completion checkpoint before the transition, then confirm its response's ID/status. Report unresolved graph damage or uncertain writes as partial recording.

Never automatically log in/out, start a hub, expose tokens, alter remotes, push, or pull. Network writes require the separate sync workflow; downloads require the separate pull workflow. Intent failure neither authorizes unrelated repair nor blocks otherwise authorized main work.

Typical mutation response:

```json
{"ok":true,"action":"...","result":{"id":"..."},"warnings":[]}
```

Typical error response:

```json
{"ok":false,"error":{"code":"...","message":"...","suggested_fix":"..."}}
```
