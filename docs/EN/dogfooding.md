# Current-version dogfooding protocol

[中文](../CN/dogfooding.md) | English

This protocol tests whether the current Intent CLI and Skill provide critical continuation context with low disruption. Historical demos and facts rediscovered from code do not count as current-version recovery evidence.

## Case setup

Use the next naturally occurring development continuations; do not manufacture benchmark tasks.

1. At a natural stopping point, explicitly ask the current agent to record with Intent. Allow at most one batched clarification during the entire recording workflow; repository, scope, boundary, and Decision questions must not interrupt separately.
2. Before recovery, freeze ground truth that is hidden from the receiving agent. Record the expected goal and reason, boundary, next step or blocker, Decisions, and whether this case should have been recorded. Do not revise ground truth to match the recovery result.
3. Start a new session or use another agent with no access to the old chat or ground truth.
4. Before reading code, tests, or other notes, allow only `itt inspect`. If the selected Intent reports `has_more: true` and its latest checkpoint is insufficient, allow `itt inspect --intent ID --history 3`.
5. Save the raw inspect JSON and the receiving agent's first recovery statement. Before the first code change, state the goal and reason, current work boundary, next step or blocker, and standing Decisions.
6. Label each recovered fact by source.

| Label | Meaning |
|---|---|
| `I` | Supplied directly by Intent output |
| `R` | Rediscovered later from code, tests, or other artifacts |
| `U` | Re-explained by the user |
| `×` | Missed or understood incorrectly |

## Pass criteria

Low disruption requires no more than one additional user turn, no more than three minutes of user attention, and no repair operation or obvious junk record.

Useful continuation requires the goal and reason, work boundary, next step or blocker, and Decisions to be correct and come from `I`. Decisions may be `N/A` only when ground truth contains no active Decision. The user must not repeat old facts, and the first substantive action must point in the right direction. A serious incorrect action is an automatic failure.

Do not discard a naturally occurring case where recording should have happened but was forgotten. Preserve its raw evidence and count it as a failure; do not backfill the record and rerun it or remove it from the sample.

- At least 4 of the first 5 natural cases must pass both criteria for **initial usability**.
- At least 8 of 10 cases, with no serious error, are required for **credible dogfood evidence**.

## Case log

Keep one row per continuation. Do not convert `R` or `U` facts into `I` after the fact.

| Case | Goal and reason | Boundary | Next / blocker | Decisions | First action | Extra turns | Attention | Result |
|---|---|---|---|---|---|---:|---:|---|
| 1 | `I/R/U/×` | `I/R/U/×` | `I/R/U/×` | `I/R/U/×/N/A` | right / wrong | 0 | 0 min | pending |

For every case set, save ground truth, raw inspect output, and the first recovery statement, and record the CLI version, Skill revision, and date. Restart the count when the continuation contract materially changes.
