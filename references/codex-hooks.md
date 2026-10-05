# Project-local Codex maintenance

Implemented in [maintenance.py](../src/intent_cli/maintenance.py), [maintenance_hooks.py](../src/intent_cli/maintenance_hooks.py), and [commands/maintenance.py](../src/intent_cli/commands/maintenance.py); adapter coverage lives in [test_maintenance.py](../tests/test_maintenance.py). No external model or server is needed.

## Setup and scope

- A new `itt init` enables continuous maintenance and installs two project-local command hooks. An existing history uses `itt maintenance on` once; absence of the flag means disabled, not inferred authorization.
- `itt maintenance off` revokes only this semantic root, including an in-flight turn. `itt maintenance status` reports local state without initializing anything. Independently initialized nested roots do not inherit their parent's flag.
- No global Codex configuration or trust state is edited. Existing unrelated hooks are preserved. A newly generated machine-specific `.codex/hooks.json` is locally Git-excluded; pre-existing configurations remain user-owned.
- `.intent/maintenance.json` holds the project flag and bounded local receipts/context. It is separate from semantic objects and excluded from IntHub snapshots. Pull preserves destination metadata. No raw prompts, transcripts, or source diffs are stored.

Codex requires human review/trust of non-managed definitions through `/hooks`; exact-definition changes need renewed review. Configuration does not attest actual execution. Project/user/plugin hooks merge, so do not install a duplicate global handler. See the [official hooks documentation](https://learn.chatgpt.com/docs/hooks).

### Complete first-time setup (not just file generation)

`init`, `maintenance on`, and `maintenance status` return `hooks.setup`, including an argv-safe CLI entry point for the exact root. Use that root, not a parent or another project:

1. For desktop setup, tell the user to open **Settings → Hooks** and review/trust this project's `UserPromptSubmit` and `Stop` definitions from `ROOT/.codex/hooks.json`. CLI users use `/hooks`; neither path requires reinstalling.
2. If the list is empty, first verify the exact project root, hook file, and directory trust. Project-local hooks are skipped when the project `.codex/` layer is untrusted; an empty list alone does not establish that cause. When directory trust is missing, use the short handoff below. Directory trust and hook-definition trust are separate; do not edit trust hashes, bypass review, or install duplicate global hooks.
3. Verify a real, read-only host turn: injected context/token, a successful `no-op` receipt, and the Stop observation. Manual adapter calls and CLI-only success do not prove desktop execution. A missing-receipt retry test is for adapter validation, not a required onboarding step for every user.

Keep the handoff brief: what is configured, the one user action still needed, and whether real execution has been observed. If trust is pending, say “configured; awaiting your trust; automatic execution not yet verified,” then continue unrelated authorized work. Do not repeatedly request permission to continue setup, or describe unrelated products as deployed based on this setup.

### Copy-ready trust handoff (only when needed)

Check whether `codex` is available before telling the user to run it; do not assume desktop installation provides a CLI on PATH. Check an existing installation/PATH first. If absent, offer the [official Codex CLI installation guide](https://learn.chatgpt.com/docs/codex/cli); with npm available the official package is `npm install -g @openai/codex`. Installing Codex CLI is separate from installing `itt`: obtain approval before Agent installation, or let the user run the instructions. Do not silently install npm/system prerequisites, use sudo, or capture sign-in credentials; any CLI sign-in is completed privately by the user.

Template for the Agent to fill, not for the user to edit:

```text
codex --cd <ABSOLUTE_PROJECT_PATH>
```

Replace the placeholder with the verified root and quote it safely for the user's shell. Send only the filled command, for example:

```sh
codex --cd /Users/deyang/PassBy
```

Then say: “Click **Trust** (or the equivalent trust-directory confirmation), enter `/hooks`, review and trust **all Intent hooks for this project**—currently `UserPromptSubmit` and `Stop`—then reopen the desktop session.” This does not mean trusting unrelated hooks from other projects, plugins, or global sources. Already trusted definitions need no repeat confirmation. If CLI installation is declined, retain configured state and report the unverified host limitation without blocking unrelated work.

When setup is requested, proceed through discovery and verification rather than stopping at `configured: true`. Report the verified host and any remaining host-specific gap accurately. Keep test-only turns out of semantic Snaps and dogfood scores.

`maintenance status` exposes bounded local `observations`: `entry_seen` and `stop_checked_receipt`. The latter is written by the Stop adapter only after checking a valid receipt, not merely by `maintenance close`. These observations are not current-session attestation; an earlier CLI test does not prove the desktop is running hooks.

## Normal flow

```text
UserPromptSubmit → project flag → one locked graph snapshot + bounded context/token
                → Agent work + meaningful verified semantic writes
                → close recorded | no-op | failed
Stop            → verify receipt → allow, or one bounded closure-only continuation
```

The entry adapter caches one graph/context per original turn; replay does not re-read or reset its baseline. Context is capped at 12 KB and explicitly marks truncation, directing the Agent to inspect missing selected facts. Root, session, and original turn identify a hashed receipt token; it is not an authentication credential.

- `recorded`: healthy graph and verified changed objects; optional explicit IDs must actually have changed. After recovery from an unavailable entry graph, only newly created objects with verifiable timestamps can be attributed automatically.
- `no-op`: healthy graph and a brief reason. No synthetic Snap is required. This records the Agent's assessment; it cannot prove that no meaningful fact was omitted.
- `failed`: brief acknowledgement, valid even when history is damaged. Stop releases with a warning instead of inventing successful verification.

Receipts are idempotent. Stop verifies referenced object fingerprints again. An absent or invalid receipt consumes its durable one-retry budget before returning a block. The exact issued continuation maps the host's new turn back to the original obligation, never creating a fresh retry budget. Repeated failures or `stop_hook_active` release with an incomplete-closure warning.

Local metadata is bounded to 32 turn entries and 4 MiB, not an unlimited audit archive. Simultaneous/replayed events are serialized by the workspace lock. Hooks never initialize history, select semantics, run suggested repairs, authenticate, or synchronize.

## What is and is not guaranteed

With trusted, enabled hooks on the normal host path, closure is checked and either verified, acknowledged as failed, or reported incomplete after one retry. Hook execution itself must be confirmed in the host; adapter tests and “configured” status are not that proof.

Semantic quality, completeness, and correct Intent/Snap boundaries still depend on the Agent and real dogfood. Untrusted/unsupported/disabled hooks, lock/time/output failures, missing host identity, cancellation, crashes, and force-stop can bypass closure. The adapter fails open with a warning rather than hanging the main task or falsely claiming success. Preserve verified milestones before risky phases to reduce lost context.

For hosts without usable hooks, the same project flag and Skill provide a soft read → preserve → assess contract. Without an injected token, do not invent a receipt or scrape host transcripts.
