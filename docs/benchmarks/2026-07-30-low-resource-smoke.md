# Low-resource benchmark smoke test — 2026-07-30

Status: **engineering validation only; not an effectiveness benchmark**.

This run checked whether the automated two-session path can stop at the intended Session A checkpoint, build two different handoffs, resume in a clean Session B, and score behavior with hidden tests.

## Configuration

| Field | Value |
|---|---|
| Base revision | `c7467d0` plus the benchmark-validity changes documented here |
| Runner | Codex CLI, clean `HOME` / `CODEX_HOME` per phase |
| Model | `gpt-5.6-terra` |
| Reasoning effort | `low` |
| Python | 3.14.3 |
| Task | `decision-stdlib-csv-001` |
| Conditions | `no-history`, `intent-full` |
| Repeats | 1 per condition |

The run was intentionally kept small to limit resource use. Both conditions used the same model and reasoning effort.

## Result

| Condition | Checkpoint | Final hidden score | Session B time | Total time | Handoff characters |
|---|---:|---:|---:|---:|---:|
| `no-history` | 3 / 3 | 5 / 5 | 32.96 s | 61.43 s | 249 |
| `intent-full` | 3 / 3 | 5 / 5 | 50.17 s | 99.47 s | 1,048 |

The final score combined policy checks with an isolated hidden pytest run. Both conditions completed the task correctly.

Codex event usage summed across Session A and B:

| Condition | Input tokens | Cached input tokens | Output tokens | Reasoning output tokens |
|---|---:|---:|---:|---:|
| `no-history` | 140,591 | 119,296 | 1,256 | 86 |
| `intent-full` | 217,502 | 178,688 | 2,605 | 523 |

Input token counters include cached input and should not be treated as a billing estimate. They are retained to make resource use visible and to prevent a nominally small smoke test from silently expanding.

## What this does and does not show

The run validates the repaired harness path:

- Session A stopped at the exact checkpoint instead of implementing the final fix.
- Session B received condition-specific context in a clean agent environment.
- Model and reasoning effort were explicit and persisted in the manifest.
- Per-phase Codex token usage can now be extracted from JSONL events and included in reports.
- A source-string decoy could not pass the new hidden behavioral test.

It does **not** show an Intent advantage. This task has a clear failing regression test and an obvious standard-library solution, so `no-history` already reaches 100% success. In this single run, Intent was longer and slower. With one task and one repeat, timing differences are noisy and must not be generalized.

The correct conclusion is that this fixture has a ceiling effect. Until harder tasks, paired repeats, and stronger statistics exist, the project must not claim that Intent improves continuation success, reduces tokens, or outperforms Git and flat summaries.

## Pre-run defect found

An earlier smoke attempt never reached Session B because both Session A agents implemented the final fix. The old prompt named a broad Phase A goal but did not state the exact checkpoint. The harness now requires `session_a.checkpoint_goal`, and all current tasks explicitly name the expected failing regression test and the files that must remain untouched.

## Next valid experiment

Before scaling model calls:

1. Build at least six synthetic tasks with non-obvious cross-session context and neutral Session B goals.
2. Freeze one canonical Session A repository state per task so conditions compare the same checkpoint.
3. Use hidden behavioral tests plus policy checks, not source strings alone.
4. Run paired, randomized conditions with at least three low-effort repeats.
5. Report raw counts, median/IQR, and uncertainty; treat a flat summary matching Intent as a valid falsification of object-model superiority.
