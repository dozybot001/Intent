# Safe local execution

Read before the first `itt` command in an authorized workflow. Continuous maintenance is the normal mode in locally enabled projects; explicit one-off recording, recovery, push, and pull remain scoped workflows.

1. Resolve the target semantic repository (the directory containing `.intent/`) and use it as each command's cwd. Git is optional. Make semantic changes through the CLI.
2. Pass semantics as argv data, not shell code. Prefer an argv-capable process API. In Codex's shell-text runner, resolve `scripts/itt_argv.py` relative to this Skill and run `python3 <trusted-absolute-runner-path> <encoded-argv>` with repository `workdir`. Encode `JSON.stringify(argv)` using `encodeURIComponent(...).replace(/[!'()*]/g, c => '%' + c.charCodeAt(0).toString(16).toUpperCase())`. Only that encoded token is data-derived. Do not invent a Base64 adapter or depend on unavailable `Buffer`, `btoa`, or `TextEncoder` globals.
3. Await each dependent command's completion; a running session is not a failure. Do not parse partial output as the result or overlap writes to the same history.
4. Parse terminal stdout as JSON; `ok: true` confirms success. If `NOT_INITIALIZED`, initialize only when the requested setup, recording, or restoration needs it, then inspect. Read-only recovery and sync-only requests do not create history.
5. Capture created IDs from `result.id` and existing IDs from inspect. Pass explicit IDs to transitions rather than relying on implicit object selection.
6. Diagnose errors and continue when recovery is safe within the requested task. Fix invocation errors that occurred before execution. For a busy repository, check the owner and wait; do not remove its lock. Read-only requests may be retried after transient failures. If a write's completion is unknown, inspect current state first: verify local object IDs or compare remote status. Shared-history push reconciles accepted content without creating a second revision. Never blindly replay object creation. Pause only affected operations when state remains uncertain, data conflicts, or recovery needs additional authority.
7. Diagnose graph warnings with `itt doctor`. Preserve existing objects and resume writes only after graph integrity is verified. Evaluate `suggested_fix` against the actual cause and task scope rather than executing it blindly.
8. After semantic mutations, verify affected IDs, lifecycle, and latest checkpoints. The current-turn `maintenance close recorded` receipt validates the graph and changed IDs; reuse that verification instead of a redundant full inspect when sufficient. Inspect omits done/cancelled Intents: verify the completion checkpoint before the transition, then confirm its response's ID/status. Report unresolved graph damage or uncertain writes as partial recording; a hooked turn can close `failed` with its injected token and a brief reason.

`itt init` defaults to project-local continuous maintenance. Legacy histories need `itt maintenance on`; `off` affects only the resolved root. Hook installation never grants host trust. `maintenance close` uses the ordinary JSON contract and safe argv adapter. `maintenance hook` is the host-only stdin/native-output protocol: do not invoke it manually, invent a turn token, or expect its output to contain `ok`.

Local writes use `itt intent create WHAT [--why WHY]`, `itt snap create WHAT --intent ID [--why WHY]`, and `itt decision create WHAT [--why WHY]`. Lifecycle commands are `itt intent activate/suspend/done ID`, `itt intent cancel ID [--reason TEXT]`, and `itt decision deprecate ID [--reason TEXT]`; the slash notation means choose one subcommand. Pass these as argv arrays, not interpolated shell strings.

Never automatically log in/out, start a hub, expose tokens, alter remotes, push, or pull. Network writes require the separate sync workflow; downloads require the separate pull workflow. Intent failure neither authorizes unrelated repair nor blocks otherwise authorized main work.

Typical mutation response:

```json
{"ok":true,"action":"...","result":{"id":"..."},"warnings":[]}
```

Typical error response:

```json
{"ok":false,"error":{"code":"...","message":"...","suggested_fix":"..."}}
```
