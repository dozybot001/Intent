# First-time setup and optional IntHub access

Use for requested setup, missing CLI, or missing IntHub authentication. Continue the original task after each verified prerequisite; do not turn normal local recording into account setup or cloud upload.

## Install only after confirmation

Check whether `itt` resolves, then run `itt version` through [execution.md](execution.md). Command-not-found / `EXECUTABLE_NOT_FOUND` is a setup branch, not a reason to abandon the workflow. Check for an existing installation outside PATH before installing a duplicate. An incompatible version needs a scoped upgrade proposal, not repeated unsupported commands.

On first installation, ask whether to enable real-time recording **for the current project**. Combine this with any outstanding installation approval in one short batch: “May I install the Intent CLI (`itt`) for your user account, including needed Python/pipx prerequisites? Also enable real-time recording for this project? This stays local and does not upload anything.” If installation is already approved, ask only the unresolved enable choice; an explicit request to enable recording already answers it. Do not ask on each turn, reinstall, or upgrade. Explain additional system changes separately if they exceed the approved scope. A refusal of installation leaves the project unchanged.

Official source: `https://github.com/dozybot001/Intent`. The platform installers are `scripts/install.sh` (macOS/Linux) and `scripts/install.ps1` (Windows) in that repository. Fetch and inspect the relevant installer before executing it; prefer a verified release/revision matching this Skill when available. Do not execute user-supplied shell text or substitute an unrelated package. Source installation requires Git and Python 3.9+; the installers use uv or pipx when present and otherwise a private virtual environment, so they also work on externally managed Pythons. Do not use sudo, replace the system Python, or change network settings silently.

If Python and pipx already exist, the installer's core operation is:

```text
pipx install "intent-history @ git+https://github.com/dozybot001/Intent.git@v7.5.1"
```

Do not use `--force` to overwrite an existing install without approved repair/upgrade. On restricted hosts, let the user run the official installer. Diagnose network/PATH issues in scope; a newly installed executable may need a fresh shell or its resolved absolute path. Installation uses normal process exit status, not the `itt` JSON contract. Verify `itt version` returns JSON with `ok: true`, then check the required maintenance commands. Record the actual revision/version rather than promising any fetched branch matches an unpublished Skill.

## Enable the requested project and finish verification

Only enable after the user's choice or explicit enable request. Resolve the target root and run `itt maintenance status`. For a new history run `itt init`; for a disabled existing history run `itt maintenance on`. In Claude Code, add `--host claude-code` to all three commands. Do not reinitialize or delete an existing `.intent/`. Reuse an already enabled project. Installation alone does not authorize initialization. If the user declines real-time recording, do not enable it; a separately requested one-off record that needs new history uses `itt init` followed immediately by `itt maintenance off` before recording, because `init` defaults to on. Do not switch off a previously enabled project merely because an installation choice is still unanswered.

After configuration, tell the desktop user: **“Open Settings → Hooks, review and trust this project's UserPromptSubmit and Stop hooks.”** Explain that these provide opening context and closure checks, respectively. The user performs the trust action; do not edit trust hashes or imply configuration grants trust. If the list is empty, first check project-directory trust and use the short exact-root CLI recovery path in [codex-hooks.md](codex-hooks.md), not another installation. CLI users can review the same definitions through `/hooks`. In Claude Code, instead tell the user: **“Trust this folder in Claude Code, then confirm Intent's UserPromptSubmit and Stop hooks in `/hooks`; restart the session if they are missing.”** See [claude-code-hooks.md](claude-code-hooks.md). Then verify a real host turn; distinguish enabled local maintenance, configured/trusted hooks, and actually observed entry/Stop execution. Without working hooks, report the Skill-only soft workflow, not a guaranteed gate.

## Optional IntHub: terminal code → browser approval

Only enter this branch when the user requests IntHub authentication or cloud synchronization. Local recording works offline without an IntHub account or token.

1. Resolve the requested remote endpoint; the official hosted site is [IntHub](https://inthub.tenon.asia). For a custom/self-hosted endpoint, use its own website and credentials, not the official site's token. Check `itt auth status --api-base-url URL`; reuse working global credentials for that endpoint.
2. If authentication is missing or expired, have the user run this in their own interactive terminal:

```text
itt auth login --api-base-url https://inthub.tenon.asia
```

3. It prints a short code and opens `/device` when the machine has a browser. The user signs in there, enters the code and approves it; this works from any device, so it also covers SSH and containers. The CLI collects a 90-day access token, named after the machine and listed under **Settings / 设置**. An older hub has no `/device`: the command then asks for a token from Settings at a hidden prompt.

For another endpoint replace only the URL. Do not use `--token SECRET` in shell argv/history. The Skill argv adapter has no interactive stdin, so it cannot run this; hand the step to the user. Unattended machines set `INTHUB_TOKEN` to a token created in Settings.

4. Verify `itt auth status` against the same endpoint reports `authenticated: true`. The CLI validates before saving to the configured secure Git credential helper. Website login alone is not CLI authentication. Credentials are global per endpoint, reusable across projects; project remotes/history remain project-local. If no secure helper is configured, report the credential-store error and use a supported OS-backed helper with appropriate authorization, not a plaintext file fallback.
5. Authentication does not authorize upload/download. Follow [sync.md](sync.md) or [pull.md](pull.md) only for the user's separately requested action. Do not initialize empty history merely to log in or test a push.

Never store tokens in `.intent/`, source files, logs, receipts, or Snap/Decision text. A disclosed token needs revocation/replacement through the user's website account, not repetition in diagnostics.
