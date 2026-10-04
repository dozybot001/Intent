# Codex integration: capability and closure design

Status: **design, not an installed hook or implemented CLI feature**. Checked against local Codex CLI 0.160.0 and the [official hooks documentation](https://learn.chatgpt.com/docs/hooks) on 2026-10-04. Skill installation alone does not enforce this contract.

## Available host mechanisms

Codex supports synchronous `UserPromptSubmit` command hooks that can run inspect and inject bounded `additionalContext`, and `Stop` hooks that can return `{"decision":"block","reason":"..."}` to request continuation. Command hooks execute programs; they are not semantic recorders. Prompt/agent hook handlers are currently parsed but skipped. Cloud orchestration does not provide the same local command-hook execution.

Repository hooks belong in `.codex/hooks.json` or `.codex/config.toml`; user hooks live under `~/.codex/`. Sources merge, so installing both can run duplicate handlers. Non-managed definitions require review/trust of their exact definition hash; edits require renewed trust. Preserve unrelated hooks and notification configuration. Do not install or grant trust during ordinary recording.

## Proposed closed loop

One explicit enablement scopes local maintenance to a Git checkout/task. Hooks check that scope, not infer permission from `.intent/`. Revocation or a turn-level read-only/skip instruction takes precedence. Cross-repository work requires separate enablement.

```text
UserPromptSubmit → bounded inspect → context tied to repository + session + turn
                → normal Agent work + verified milestone writes
                → closure: recorded | no-op | failed
Stop            → check closure identity/evidence → allow or one bounded continuation
```

The following components are required **before installing an enforcing Stop hook**; they do not exist in the current CLI:

1. **Entry context adapter.** Resolve the authorized Git root, use the normal locked inspect, parse JSON/`ok` and warnings, and inject relevant latest checkpoints plus active Decisions within strict time/output budgets. Include root, `session_id`, and `turn_id`. No repeated agent inspect when current-turn context is valid. On failure/timeout, expose unavailable history, disable writes for this turn, and preserve the main task; never run init, repair, or sync from a hook.
2. **Turn closure receipt.** A local metadata facility separate from semantic objects, keyed by canonical repository, session, and original turn. Store outcome, reason, affected object IDs, verification status, and partial failures. Store no raw prompt, transcript, token, or source diff. `recorded` requires successful post-write inspection; `no-op` needs a reason, not a garbage Snap; `failed` acknowledges a real failure rather than disguising it as success.
3. **Stop gate.** Verify receipt identity and referenced local objects. An absent/incomplete receipt may request one continuation solely to finish authorized local closure. Valid no-op passes without objects. Acknowledged failure passes with user-visible disclosure; stopping the main task forever is not recovery. A syntactically valid receipt cannot prove semantic completeness or truth; dogfood must still test those.
4. **Replay and loop guard.** Consume host turn identity; map a Stop-generated continuation to the original obligation because the host resumes through a new user prompt. Do not reset retry budget or entry context on that continuation. Check `stop_hook_active` and durable retry state. One retry maximum; repeated failure is reported and released, never coerced into fabricated history. Concurrent/replayed hooks must not duplicate writes or receipts; workspace locking alone is not turn idempotency.

Test ordinary work, no-op, multiple Intents, read-only opt-out, damaged history, lost responses, concurrent/replayed events, untrusted/disabled hooks, timeouts, Stop continuation, and manual interruption before enabling enforcement. No transcript scraping: Codex's transcript format is not a stable integration API.

## Guarantees and limits

A hook can require a closure check on the normal end-of-turn path, not force a correct semantic Snap. Disabled/untrusted hooks, host failure, cancellation, and crashes can bypass the path. Interrupt hooks cannot guarantee an agent-authored final checkpoint or restart a cancelled turn. Recording verified milestones during work is useful even with a Stop gate.

Do not run an external LLM or duplicate task reasoning in a hook. The Agent selects semantics; the CLI stores/validates objects; the hook handles entry and closure evidence. Measure real latency and noise rather than asserting low overhead from design alone.

## AGENTS fallback (soft contract)

For hosts without usable hooks, the user can explicitly approve this instruction in the target repository/task:

```text
Intent automatic local maintenance is enabled for this repository.
Use the intent-cli Skill: inspect once at turn start; preserve verified semantic
changes during work; assess recorded/no-op/failed closure before responding.
No per-turn object quota, automatic sync, login, or cross-repository writes.
Respect read-only, skip-recording, and disable requests. Report partial failures.
```

This is an opt-in template, not an instruction that enables this repository by being read. It is soft guidance, not proof of hook execution or a durable closure receipt. The current Skill can guide automatic maintenance with it; implementing and installing the receipt adapter is a separate change.
