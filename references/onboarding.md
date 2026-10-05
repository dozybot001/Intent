# First-time setup and optional IntHub access

Use for requested setup, missing CLI, or missing IntHub authentication. Continue the original task after each verified prerequisite; do not turn normal local recording into account setup or cloud upload.

## Install only after confirmation

Check whether `itt` resolves, then run `itt version` through [execution.md](execution.md). Command-not-found / `EXECUTABLE_NOT_FOUND` is a setup branch, not a reason to abandon the workflow. Check for an existing installation outside PATH before installing a duplicate. An incompatible version needs a scoped upgrade proposal, not repeated unsupported commands.

If installation has not already been explicitly approved, ask once: “This project needs the Intent CLI (`itt`). May I install it for your user account from the official Intent repository, including Python/pipx prerequisites if needed? This does not log in to IntHub or upload anything.” Explain additional system changes separately if they exceed that scope. A refusal leaves the project unchanged; offer instructions without attempting a workaround installation.

Official source: `https://github.com/dozybot001/Intent`. The platform installers are `scripts/install.sh` (macOS/Linux) and `scripts/install.ps1` (Windows) in that repository. Fetch and inspect the relevant installer before executing it; prefer a verified release/revision matching this Skill when available. Do not execute user-supplied shell text or substitute an unrelated package. Source installation requires Git and Python 3.9+; the installers handle pipx. Do not use sudo, replace the system Python, or change network settings silently.

If Python and pipx already exist, the installer's core operation is:

```text
pipx install "intent-cli @ git+https://github.com/dozybot001/Intent.git@v7.0.0"
```

Do not use `--force` to overwrite an existing install without approved repair/upgrade. On restricted hosts, let the user run the official installer. Diagnose network/PATH issues in scope; a newly installed executable may need a fresh shell or its resolved absolute path. Installation uses normal process exit status, not the `itt` JSON contract. Verify `itt version` returns JSON with `ok: true`, then check the required maintenance commands. Record the actual revision/version rather than promising any fetched branch matches an unpublished Skill.

## Enable the requested project and finish verification

Resolve the target root and run `itt maintenance status`. For a new history run `itt init`; for a disabled existing history run `itt maintenance on`. Do not reinitialize or delete an existing `.intent/`. Reuse an already enabled project.

After configuration, tell the desktop user: **“Open Settings → Hooks, review and trust this project's UserPromptSubmit and Stop hooks.”** Explain that these provide opening context and closure checks, respectively. The user performs the trust action; do not edit trust hashes or imply configuration grants trust. If the list is empty, follow `hooks.setup` and [codex-hooks.md](codex-hooks.md) to resolve project discovery instead of leaving the user stuck. CLI users can review the same definitions through `/hooks`. Then verify a real host turn; distinguish enabled local maintenance, configured/trusted hooks, and actually observed entry/Stop execution. Without working hooks, report the Skill-only soft workflow, not a guaranteed gate.

## Optional IntHub: website → access token → private CLI login

Only enter this branch when the user requests IntHub authentication or cloud synchronization. Local recording works offline without an IntHub account or token.

1. Resolve the requested remote endpoint; the official hosted site is [IntHub](https://inthub.tenon.asia). For a custom/self-hosted endpoint, use its own website and credentials, not the official site's token. Check `itt auth status --api-base-url URL`; reuse working global credentials for that endpoint.
2. If authentication is missing/expired, direct the user to that website, sign in to their account, and open the account menu's **Access token / 访问令牌** action. The current UI creates a new CLI access token and displays the secret once. The user copies and keeps it privately; do not read the secret through browser inspection, screenshots, clipboard tools, or ask them to paste it into chat.
3. Have the user run this in their own interactive terminal and paste the token at the hidden prompt:

```text
itt auth login --api-base-url https://inthub.tenon.asia
```

For another endpoint replace only the URL. Do not use `--token SECRET` in shell argv/history. The Skill argv adapter intentionally has no interactive stdin, so it cannot accept this prompt; do not capture the token in an agent-controlled terminal either. If no private input surface exists, hand off this one login step, then resume after the user confirms completion.

4. Verify `itt auth status` against the same endpoint reports `authenticated: true`. The CLI validates before saving to the configured secure Git credential helper. Website login alone is not CLI authentication. Credentials are global per endpoint, reusable across projects; project remotes/history remain project-local. If no secure helper is configured, report the credential-store error and use a supported OS-backed helper with appropriate authorization, not a plaintext file fallback.
5. Authentication does not authorize upload/download. Follow [sync.md](sync.md) or [pull.md](pull.md) only for the user's separately requested action. Do not initialize empty history merely to log in or test a push.

Never store tokens in `.intent/`, source files, logs, receipts, or Snap/Decision text. A disclosed token needs revocation/replacement through the user's website account, not repetition in diagnostics.
