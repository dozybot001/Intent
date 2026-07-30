# Intent Benchmark CLI

[中文](../CN/benchmark-cli.md) | English

`itt benchmark` contains a generic, reproducible benchmark harness for testing
Intent's workflow cost and resume value from the same CLI agents already use.

The benchmark is intentionally independent from Intent's own development
history. Each task is a small fixture repository with:

- base files
- Session A changes and notes
- Session B continuation goal
- Intent-style context objects
- a hidden oracle for scoring the completed Session B repository

## One-Command Run

The default path creates clean task repositories under `.itt-benchmark/runs/<run-id>/`, starts Codex Session A, builds the handoff layer, starts a fresh Codex Session B, then reports success rate, total elapsed time, B-phase time, and handoff character volume.

```bash
itt benchmark
```

Common overrides:

```bash
itt benchmark \
  --out /tmp/intent-live \
  --conditions no-history,git-only,chat-summary,intent-full,full-transcript \
  --tasks bug-cli-config-cache-001 \
  --repeat 1 \
  --model gpt-5.6-terra \
  --reasoning-effort low
```

Output remains standard Intent CLI JSON. `result.table` is the compact comparison table, while `result.runs` keeps per-trial details. The default runner is `codex`, so the machine must be able to run `codex exec`. Reasoning effort defaults to `low`; comparisons should pin both model and effort across all conditions.

Each run also writes the durable data source into the benchmark directory:

```text
.itt-benchmark/
  runs/
    run-YYYYMMDD-HHMMSS-ffffff/
      manifest.json
      report.json
      tasks/
        bug-cli-config-cache-001.json
      trials/
        bug-cli-config-cache-001__intent-full__r01/
          run.json
          session-a/
          session-b/
```

- `manifest.json` records runner, model, reasoning effort, tasks, conditions, repeat, Intent CLI version, and paths.
- `report.json` is the primary result artifact for later analysis and comparison.
- `tasks/` stores the exact task spec snapshot used in this run.
- `trials/*/run.json` stores per two-session trial events, scores, timing, and errors.

## Clean Codex Sessions

The automated runner does not use the full current user `~/.codex` directory directly. Each phase creates an isolated temporary `HOME` / `CODEX_HOME`:

- It copies only `auth.json` and minimal model/provider config.
- It does not copy `AGENTS.md`, skills, plugins, historical sessions, memory, or project trust config.
- It launches Codex with `--ephemeral` and `--ignore-rules`.
- `manifest.json` records `runner_isolation` as `clean-home`.

This keeps the benchmark closer to a fresh agent session and avoids contamination from machine-global agent instructions.

## Resource and Validity Boundaries

- Start with one task, two conditions, `repeat=1`, and `--reasoning-effort low`. Scale only after checkpoint, runner, and scoring paths are valid.
- The current fixtures are an engineering pilot. Too few tasks or near-100% success in every condition cannot support a claim that Intent beats Git or a flat summary.
- Final scoring runs hidden behavioral tests in an isolated repository copy and combines them with explicit policy constraints. Source-string checks are only supporting signals.
- Session A receives an exact checkpoint. If the agent implements the Session B fix early, record a checkpoint failure rather than treating the trial as product-effect evidence.
- Persist model, reasoning effort, task snapshots, and repeat count in the manifest. Do not pool results from different resource settings.
- The automated Codex runner records input, cached-input, output, and reasoning tokens from JSONL events. Use them for resource auditing, not as a direct billing estimate.

See the first [low-resource engineering smoke report](../benchmarks/2026-07-30-low-resource-smoke.md). Both conditions succeeded, exposing a ceiling effect rather than providing positive evidence for Intent.

## Debug Commands

List tasks:

```bash
itt benchmark list
```

Materialize the repository after Session A:

```bash
itt benchmark materialize \
  --task bug-cli-config-cache-001 \
  --stage after_a \
  --out /tmp/intent-bench-task
```

Build a context packet for Session B:

```bash
itt benchmark context \
  --task bug-cli-config-cache-001 \
  --condition intent-full \
  --out /tmp/context.md
```

Build an ablated Intent context:

```bash
itt benchmark context \
  --task bug-cli-config-cache-001 \
  --condition intent-full \
  --ablation no-decision \
  --out /tmp/context.md
```

Score a completed repository:

```bash
itt benchmark score \
  --task bug-cli-config-cache-001 \
  --repo /tmp/intent-bench-task
```

## Live Two-Session Benchmark

The live benchmark tests the real workflow: Session A reaches a checkpoint, then a fresh Session B resumes from the selected handoff condition.

Create a run:

```bash
itt benchmark live start \
  --task bug-cli-config-cache-001 \
  --condition intent-full \
  --out /tmp/intent-live/run-001
```

Start Session A timing:

```bash
itt benchmark live begin --run /tmp/intent-live/run-001 --phase a
```

Give `/tmp/intent-live/run-001/session-a/instructions.md` to a fresh Session A. After Session A reaches the checkpoint and stops:

```bash
itt benchmark live checkpoint --run /tmp/intent-live/run-001
itt benchmark live handoff --run /tmp/intent-live/run-001
```

Start Session B timing:

```bash
itt benchmark live begin --run /tmp/intent-live/run-001 --phase b
```

Give `/tmp/intent-live/run-001/session-b/instructions.md` to a fresh Session B. After Session B finishes:

```bash
itt benchmark live score --run /tmp/intent-live/run-001
```

Aggregate multiple runs:

```bash
itt benchmark live report --runs /tmp/intent-live
```

The live report includes success rate and elapsed time. When success rates are all near 100%, compare total time, B time, and handoff time.

## Context Conditions

- `no-history`
- `git-only`
- `chat-summary`
- `full-transcript`
- `intent-full`

## Ablations

Ablations apply only to `intent-full`:

- `no-intent`
- `no-snap`
- `no-decision`
- `no-why`
- `no-status`
- `no-relations`
