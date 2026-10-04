# Current-version dogfooding protocol

[中文](../CN/dogfooding.md) | English

This protocol tests whether Intent provides critical continuation context with low disruption under either an explicit recording request or a locally enabled automatic-maintenance contract. Historical demos and facts rediscovered from code do not count as current-version recovery evidence.

Automatic maintenance is an agent operating contract after one explicit user authorization, not proof of platform enforcement. The repository does not yet provide an automatic-enable CLI command, turn receipt, or enabled Codex hook integration. An automatic-mode case must therefore preserve the authorization plus the exact Skill or agent-instruction revision that performed it; do not describe that evidence as hook-enforced.

## Case setup

Use the next naturally occurring development continuations; do not manufacture benchmark tasks. Record which authorization path applies before each case set:

- **Explicit recording:** at a natural stopping point, the user asks the current agent to record with Intent. If the first `itt inspect` returns `NOT_INITIALIZED`, this explicit recording request permits `itt init` before inspecting again.
- **Locally enabled automatic maintenance:** the user has explicitly enabled one named repository or task once through the active Skill or other recorded local agent instruction. Each turn begins with `itt inspect`; during the work the agent records only verified important milestones; at turn end it assesses `recorded`, `no-op`, or `failed`, without announcing routine success or no-op to the user. A turn boundary does not require a new Snap, and a query, file, command, commit, or tool call is not an Intent boundary. Enabling an uninitialized repository must separately include permission to initialize it.

Then run the case:

1. Apply the selected recording path. Explicit recording allows at most one batched clarification. Enabled automatic maintenance should normally require zero additional user turns; if repository, semantic boundary, or another material ambiguity makes a question unavoidable, combine it into one batch. Never interrupt every turn for individual Decision candidates.
2. In either path, keep zero writes as a valid result. Split independent objectives into separate Intents, but do not split one objective by query, file, command, or implementation step. Do not promote unconfirmed candidates to Decisions; explicit durable user rules need no repeated confirmation. Do not automatically sign in or sync to IntHub, or suspend or complete an Intent merely because the turn ended.
3. Before recovery, freeze ground truth that is hidden from the receiving agent. Record the expected goal and reason, boundary, next step or blocker, Decisions, whether this case should have been recorded, and whether the expected recording outcome was `recorded`, `no-op`, or `failed`. Do not revise ground truth to match the recovery result.
4. Start a new session or use another agent with no access to the old chat or ground truth.
5. Before reading code, tests, or other notes, allow only `itt inspect`. If the selected Intent reports `has_more: true` and its latest checkpoint is insufficient, allow `itt inspect --intent ID --history 3`.
6. Save the raw inspect JSON and the receiving agent's first recovery statement. For automatic-mode cases, also save the raw turn-opening inspect output and turn-close outcome. Before the first code change, state the goal and reason, current work boundary, next step or blocker, and standing Decisions.
7. Label each recovered fact by source.

| Label | Meaning |
|---|---|
| `I` | Supplied directly by Intent output |
| `R` | Rediscovered later from code, tests, or other artifacts |
| `U` | Re-explained by the user |
| `×` | Missed or understood incorrectly |

## Pass criteria

Recording correctness requires the reported turn-close outcome to match frozen ground truth. `no-op` passes only when omitting the turn leaves no continuation-critical gap; `failed` is preserved as evidence but counts as a failed case.

Low disruption requires no more than one additional user turn, no more than three minutes of user attention, and no repair operation or obvious junk record. Enabled automatic maintenance should normally add zero user turns; repeated confirmation or a new Snap for every query fails the low-disruption criterion even if the records are structurally valid.

Useful continuation requires the goal and reason, work boundary, next step or blocker, and Decisions to be correct and come from `I`. Decisions may be `N/A` only when ground truth contains no active Decision. The user must not repeat old facts, and the first substantive action must point in the right direction. A serious incorrect action is an automatic failure.

Do not discard a naturally occurring case where recording should have happened but was forgotten—including an enabled automatic turn whose hook or agent failed to record it. Preserve its raw evidence and count it as a failure; do not backfill the record and rerun it or remove it from the sample.

- At least 4 of the first 5 natural cases must pass both criteria for **initial usability**.
- At least 8 of 10 cases, with no serious error, are required for **credible dogfood evidence**.

## Case log

Keep one row per continuation. Do not convert `R` or `U` facts into `I` after the fact.

| Case | Mode | Record close | Goal and reason | Boundary | Next / blocker | Decisions | First action | Extra turns | Attention | Result |
|---|---|---|---|---|---|---|---|---:|---:|---|
| 1 | explicit / automatic | recorded / no-op / failed | `I/R/U/×` | `I/R/U/×` | `I/R/U/×` | `I/R/U/×/N/A` | right / wrong | 0 | 0 min | pending |

For every case set, save ground truth, raw inspect output, the first recovery statement, and the applicable authorization evidence. Record the CLI version, Skill revision, hook/config revision when applicable, and date. Restart the count when the continuation contract materially changes.
