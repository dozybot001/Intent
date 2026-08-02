# Current-version dogfooding protocol

[中文](../CN/dogfooding.md) | English

This protocol tests whether the current Intent CLI and Skill provide critical continuation context with low disruption. Historical demos and facts rediscovered from code do not count as current-version recovery evidence.

## Case setup

Use the next naturally occurring development continuations; do not manufacture benchmark tasks.

1. At a natural stopping point, explicitly ask the current agent to record with Intent.
2. Start a new session or use another agent with no access to the old chat.
3. Before reading code, tests, or other notes, allow only `itt inspect`. If the selected Intent reports `has_more: true` and its latest checkpoint is insufficient, allow `itt inspect --intent ID --history 3`.
4. Before the first code change, state the goal and reason, current work boundary, next step or blocker, and standing Decisions.
5. Label each recovered fact by source.

| Label | Meaning |
|---|---|
| `I` | Supplied directly by Intent output |
| `R` | Rediscovered later from code, tests, or other artifacts |
| `U` | Re-explained by the user |
| `×` | Missed or understood incorrectly |

## Pass criteria

Low disruption requires no more than one additional user turn, no more than three minutes of user attention, and no repair operation or obvious junk record.

Useful continuation requires the goal, work boundary, and constraints to come from `I`; the user must not repeat old facts; and the first substantive action must point in the right direction. A serious incorrect action is an automatic failure.

- At least 4 of the first 5 natural cases must pass both criteria for **initial usability**.
- At least 8 of 10 cases, with no serious error, are required for **credible dogfood evidence**.

## Case log

Keep one row per continuation. Do not convert `R` or `U` facts into `I` after the fact.

| Case | Goal | Boundary | Next / blocker | Decisions | First action | Extra turns | Attention | Result |
|---|---|---|---|---|---|---:|---:|---|
| 1 | `I/R/U/×` | `I/R/U/×` | `I/R/U/×` | `I/R/U/×` | right / wrong | 0 | 0 min | pending |

Record the CLI version, Skill revision, and date with every case set. Restart the count when the continuation contract materially changes.
