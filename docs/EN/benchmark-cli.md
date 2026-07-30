# Intent Benchmark CLI

[中文](../CN/benchmark-cli.md) | English

`itt benchmark` runs reproducible continuation experiments against small,
redistributable fixture repositories. The default protocol freezes one
canonical post-Session-A checkpoint per task, clones that checkpoint for every
condition, and invokes only a clean Session B. This removes condition-specific
Session A behavior from the continuation comparison.

The protocol and its permitted claims are fixed in the public
[continuation benchmark preregistration](../benchmarks/continuation-benchmark-preregistration.md).
Screening runs are engineering evidence only; they are not confirmation.

## Default Continuation Run

Bare `itt benchmark` selects the frozen-checkpoint continuation protocol, but a
real Codex run must explicitly name the preregistered model. The runner enforces
`gpt-5.6-terra` with `low` reasoning for this cohort.

```bash
itt benchmark \
  --stage screening \
  --tasks bug-cli-config-cache-001 \
  --conditions no-history,git-only,flat-facts-matched,intent-full \
  --repeat 1 \
  --model gpt-5.6-terra \
  --reasoning-effort low \
  --timeout 600 \
  --seed 1729
```

The default per-trial timeout is 600 seconds. Output is the standard Intent CLI
JSON envelope; `result.runs` contains raw trial rows, while the durable
`manifest.json` and `report.json` remain the audit source.

### Study and resource options

| Option | Meaning |
|---|---|
| `--stage screening\|confirmation\|exploratory` | Records the study stage. Default: `screening`. Only a preregistered holdout run marked `confirmation` can be assessed as confirmatory. |
| `--confirmation-lock FILE` | Required for `confirmation`; verifies frozen task hashes, conditions, repeats, seed, model, effort, and preregistration hash. |
| `--seed N` | Fixes task aliases, pair order, and Latin-rotated condition order. Default: `1729`. |
| `--max-pairs N` | Hard limit on complete task/repeat blocks. It must end on a complete task wave. |
| `--max-total-input-tokens N` | Soft cumulative threshold checked before the next complete pair. |
| `--max-total-wall-seconds S` | Soft suite wall-time threshold checked before the next complete pair. |
| `--timeout S` | Per-trial runner timeout. Default: `600`. |
| `--repeat N` | Number of complete paired waves. All preregistered repeats count. |
| `--out DIR` | Writes the suite to an explicit directory. Existing output requires `--force` to replace. |

Token and wall thresholds deliberately do not interrupt a pair halfway through,
so the final pair can overshoot either threshold. Use `--max-pairs` together
with the per-trial timeout for a hard call-count and per-call time envelope.
Token counts come from Codex JSONL events and are resource-audit signals, not a
direct billing estimate.

## What Is Frozen

Before any model call, the continuation runner:

1. loads and detaches each task spec from the mutable source tree;
2. materializes and validates one canonical after-Session-A checkpoint;
3. records task and checkpoint hashes;
4. builds the complete paired plan from the fixed seed;
5. validates `flat-facts-matched` and `intent-full` fact and context parity when
   both conditions are present.

Every condition in a pair starts from the same source checkpoint and clean Git
state. Intent's full graph is rendered through the real `inspect --full`
product view in an external temporary fixture; `.intent/` is not added to only
one trial repository.

Only Session B invokes Codex in this protocol. Recording cost and autonomous
Session A capture are different research questions and belong to the legacy
two-session protocol or a separate study.

## Main Fairness Conditions

The default continuation conditions are:

- `no-history` — repository checkpoint and current Session B goal only;
- `git-only` — the canonical Git handoff available for the task;
- `flat-facts-matched` — an ungrouped deterministic rendering of the same
  semantic facts as Intent;
- `intent-full` — the same facts represented as the complete Intent object
  graph, including status, `why`/`reason`, and relationships.

`flat-facts-matched` is the primary fairness baseline for testing object-model
value. A weaker, independently written summary is not a substitute. If
`intent-full` ties this baseline, the result may support semantic handoff value
over code-only history, but it does not establish that Intent's structure is
better than an equally informative flat representation.

Legacy/debug context names such as `chat-summary`, `full-transcript`, and
`flat-facts` may still be available to the generic harness. They are not the
preregistered primary flat baseline.

## Isolation and Label Masking

Each Session B receives a fresh temporary `HOME` and `CODEX_HOME`:

- only `auth.json` and minimal model/provider configuration are copied;
- global `AGENTS.md`, skills, plugins, memories, historical sessions, and
  project trust are not copied;
- Codex starts with `--ephemeral` and `--ignore-rules`;
- Intent CLI internals are not exposed to the task agent by default.

The current preregistered runner additionally uses macOS `sandbox-exec` to
deny reads of sibling trials, evaluator files, the real Codex home, and Intent's
benchmark source. On a platform without this evaluator read-isolation layer,
the preregistered cohort refuses to start rather than silently weakening the
protocol.

Task and treatment names are replaced with opaque aliases while model calls are
running and decoded only after the suite stops. This is **label masking**, not
perfect blinding: an agent may still infer a condition from the representation
it receives. Reports and claims must use that exact boundary.

## Audit Artifacts

A completed suite has this general shape:

```text
.itt-benchmark/
  runs/
    continuation-YYYYMMDD-HHMMSS/
      manifest.json
      report.json
      tasks/
        <frozen-task>.json
      checkpoints/
        task-001/
          checkpoint.json
          repo/
      trials/
        trial-0001/
          run.json
          session-b/
            context.md
            instructions.md
            codex-events.jsonl
            repo/
```

Across `manifest.json`, `report.json`, checkpoint metadata, and per-trial
records, the suite preserves:

- task-spec and checkpoint hashes;
- matched semantic-fact and rendered-context hashes;
- decoded task, condition, pair, repeat, order, and C0–C4 stratum;
- runner, model, reasoning effort, timeout, seed, environment, and source
  fingerprints;
- raw scores, elapsed time, Session B token usage, errors, invalid pairs, and
  resource-stop reason;
- overall paired statistics, statistics by stratum, C2/C3 efficacy statistics,
  and the preregistered threshold assessment.

An infrastructure failure invalidates the complete pair rather than leaving a
single favorable condition in the aggregate. Agent task failures remain task
failures. Frozen task specs and all attempted trial artifacts are retained for
audit.

## Validity Boundaries

- Start with `--stage screening`; do not describe screening output as a
  confirmation result.
- Near-100% success in every condition indicates a ceiling, not an Intent
  advantage.
- Hidden behavioral tests run in an isolated repository copy. Source-string
  checks are supporting diagnostics, not sufficient evidence by themselves.
- C0 code-sufficient controls, C2/C3 efficacy tasks, and C4 safety controls are
  reported separately.
- Do not pool runs that differ in model, reasoning effort, task version, prompt,
  renderer, or protocol.
- A confirmation claim is permitted only when the holdout run and all
  preregistered thresholds pass.

The existing [low-resource smoke report](../benchmarks/2026-07-30-low-resource-smoke.md)
validated an earlier engineering path and exposed a ceiling effect. It is not a
positive effectiveness result and is not pooled with the new protocol.

## Legacy Automated Two-Session Protocol

Use `--protocol live` to run the older automated Session A + Session B flow:

```bash
itt benchmark \
  --protocol live \
  --tasks bug-cli-config-cache-001 \
  --conditions no-history,intent-full \
  --repeat 1 \
  --model gpt-5.6-terra \
  --reasoning-effort low \
  --timeout 600
```

This protocol asks a model to create the Session A checkpoint separately for
each condition. It is useful for end-to-end workflow experiments, but its
results must not be mixed with frozen-checkpoint continuation efficacy.

## Manual Live Debug Commands

The `benchmark live` subcommands remain available for inspecting each handoff
step manually.

```bash
itt benchmark live start \
  --task bug-cli-config-cache-001 \
  --condition intent-full \
  --out /tmp/intent-live/run-001

itt benchmark live begin --run /tmp/intent-live/run-001 --phase a
itt benchmark live checkpoint --run /tmp/intent-live/run-001
itt benchmark live handoff --run /tmp/intent-live/run-001
itt benchmark live begin --run /tmp/intent-live/run-001 --phase b
itt benchmark live score --run /tmp/intent-live/run-001
itt benchmark live report --runs /tmp/intent-live
```

These commands do not automatically launch a model. Give the generated
`instructions.md` to the corresponding clean session between steps.

## Other Debug Commands

```bash
# List task fixtures
itt benchmark list

# Materialize the canonical after-A repository
itt benchmark materialize \
  --task bug-cli-config-cache-001 \
  --stage after_a \
  --out /tmp/intent-bench-task

# Render one fact-matched handoff
itt benchmark context \
  --task bug-cli-config-cache-001 \
  --condition flat-facts-matched \
  --out /tmp/context.md

# Render an Intent ablation
itt benchmark context \
  --task bug-cli-config-cache-001 \
  --condition intent-full \
  --ablation no-decision \
  --out /tmp/context.md

# Score a completed repository
itt benchmark score \
  --task bug-cli-config-cache-001 \
  --repo /tmp/intent-bench-task
```

Available Intent ablations are `no-intent`, `no-snap`, `no-decision`,
`no-why`, `no-status`, and `no-relations`.
