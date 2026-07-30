# Continuation Benchmark Preregistration

Status: **preregistered design; no confirmatory model results have been collected under this protocol**

Protocol version: `1.0`

Registered: `2026-07-30`

This document fixes the questions, comparison conditions, outcomes, stopping
rules, and permitted claims for the next Intent continuation benchmark before
confirmatory runs begin. Its purpose is to make a negative or null result as
auditable as a positive one.

All model-assisted trials in this protocol use exactly:

- model: `gpt-5.6-terra`
- reasoning effort: `low`

Results produced with another model or reasoning effort belong to a separate
cohort and must not be pooled with this study.

## 1. Research questions

The benchmark separates three claims that are often conflated:

1. **Semantic handoff value:** Does carrying code-external goals, findings,
   and decisions improve continuation over repository state or Git history
   alone?
2. **Object-model value:** Given the same semantic facts and a comparable
   context budget, do explicit `intent`, `snap`, and `decision` boundaries
   improve continuation over a flat factual summary?
3. **Compression value:** Can Intent approach a full transcript's continuation
   quality with materially less context?

The primary confirmatory contrast is `intent-full` versus
`flat-facts-matched`. `intent-full` versus `git-only` is a prespecified
secondary contrast. A later full-transcript comparison is a separate
non-inferiority study and is not required for the first confirmation run.

Intent is not expected to help every software task. The expected advantage
region is defined before tasks are selected.

## 2. Advantage-region strata

| Stratum | Definition | Preregistered expectation |
|---|---|---|
| **C0 — code-sufficient control** | No required fact exists outside visible code, tests, repository state, and the current Session B request. | All competent conditions should complete the task. Intent may be slower or use more context; an Intent quality advantage is not expected. |
| **C1 — sparse semantic handoff** | One current goal, one to three code-external facts, no stale state, no competing intent, and no scope conflict. | Semantic history should beat `no-history` or `git-only` when the external fact matters. A fact-matched flat summary should normally tie Intent. |
| **C2 — relational semantic handoff** | At least two intents; at least one inactive, suspended, or completed object; at least two decisions or findings; and at least one relation or scope distinction needed for the correct continuation. | Intent should beat code-only baselines. A structural advantage over flat facts is plausible but not assumed. |
| **C3 — longitudinal, high-density handoff** | At least three intents, at least two status transitions, a deprecated/replaced decision or corrected direction, eight or more relevant facts, comparable distractor history, and at least two code-plausible continuation paths. | This is the principal expected advantage region for Intent over a fact-matched flat representation. |
| **C4 — safety and falsification control** | The current request supersedes history, a record is stale or wrong, or following a historical decision would violate current instructions. | Intent must defer to current authority and avoid stale-history lock-in. A failure is a product safety result, not an inconvenient outlier. |

C0 and C4 results are reported separately and are never pooled into an
advantage estimate. C1 is a calibration stratum. Confirmatory efficacy claims
are limited to the preregistered C2/C3 population.

## 3. Task construction and eligibility

Each task must be a synthetic or redistributable fixture repository, normally
containing 5–20 meaningful files. It must not be derived by selecting a known
favorable episode from Intent's own history.

Before any model run, a task must have:

- one frozen Session A checkpoint;
- a neutral Session B goal that does not reveal the hidden decision or answer;
- hidden behavioral tests;
- explicit semantic obligations and critical forbidden behaviors;
- one reference-correct solution;
- for C2/C3, at least two plausible implementation directions that can look
  reasonable from code or visible tests, while at least one violates the
  semantic oracle;
- an assigned stratum and a written justification;
- a task-spec hash and checkpoint Git tree hash.

Source-string checks may be retained as diagnostics, but cannot by themselves
establish success. Hidden tests execute in an isolated copy and must assess
behavior. A task that lets every baseline reach a ceiling is reported as
non-discriminating; it is not retroactively rewritten and counted as evidence.

## 4. Canonical fact ledger

Every C1–C4 task is frozen with one condition-independent atomic fact ledger.
Before any model call, the task's semantic objects are normalized into this
ledger; both matched renderers are then rebuilt exclusively from it. The
product graph is round-tripped through `itt inspect --full` and must reproduce
the same ledger exactly. A fact has the following model-visible shape:

```json
{
  "id": "F07",
  "object_type": "decision",
  "object_id": "decision-003",
  "field": "status",
  "value": "active",
  "model_visible": true
}
```

Task-author notes about repository-visible facts, semantic obligations, and
fairness live in a separate `construction_facts` section. They are never
rendered to the model and are not allowed to substitute for machine-checked
atomic parity.

The ledger must distinguish:

- relevant and distractor facts;
- current, suspended, done, active, and deprecated states;
- goal, milestone, finding, decision, correction, and relation facts;
- global versus intent-scoped constraints;
- facts available in Git from facts available only in semantic history.

The frozen atomic ledger, its hash, and opaque `F###` IDs rendered into each
condition are saved with the run. Coverage is calculated from actual rendered
and round-tripped IDs rather than asserted by the task author. A semantic
condition is invalid if it silently adds an answer, omits a ledger fact, or
turns an evaluator-only annotation into model-visible text.

## 5. Comparison conditions

### `no-history`

Session B receives only the frozen repository and the common Session B request.

### `git-only`

Session B receives the same repository and request plus the frozen canonical
Git-style commit message and base-to-checkpoint diff defined by the synthetic
task. The trial repository itself stays identical across conditions; this
packet is versioned and hashed, but is not claimed to be a naturally occurring
production Git history. No semantic ledger prose is added.

### `flat-facts-matched`

Session B receives a deterministic, ungrouped prose rendering of exactly the
same model-visible atomic facts as `intent-full`, including statuses, why
facts, corrections, and scope relations. It is not an intentionally weak
summary and is not generated independently by another model.

### `intent-full`

Session B receives those same atomic facts represented through explicit Intent
objects, statuses, and relations. The treatment must be produced by a
documented product surface or a versioned renderer. If the benchmark uses a
richer experimental graph view than the released `itt inspect` command, the
report must call it an experimental `intent-graph` treatment and must not
attribute the result to the released inspect experience.

### `full-transcript` (optional later study)

Session B receives a frozen canonical Session A transcript, not a
condition-aware, post hoc “transcript-style” summary. This is a high-cost upper
bound.

For the primary object-model contrast:

- Intent and flat facts have 100% ledger-fact parity;
- neither renderer may add implementation advice absent from the ledger;
- their serialized handoff character counts must be within 10% of one another
  before any model call;
- if the length bound cannot be met without losing fact parity, the renderer
  must be revised before trials, not after results are observed.

An unconstrained human- or agent-written chat summary may be evaluated as an
ecological secondary baseline, but it is not the fact-matched primary control.

## 6. Frozen Session A and label-masked Session B

Continuation efficacy is measured with one canonical Session A checkpoint per
task. The checkpoint repository, Git state, and fact ledger are frozen once,
then cloned across conditions. Session A is not rerun for each condition.

Only Session B invokes a model in the efficacy study. Recording burden is a
separate end-to-end study because condition-specific Session A work would
confound handoff quality with checkpoint quality and recording effort.

Every Session B trial has:

- the same current request and instruction template;
- a fresh isolated `HOME` and `CODEX_HOME`;
- the same model, `low` reasoning effort, timeout, tools, and runner version;
- evaluator read isolation that denies sibling trials, benchmark source,
  hidden tests, and evaluator metadata while allowing the active trial;
- a neutral context filename and heading that do not reveal the condition;
- condition order randomized within task/repeat blocks from a committed seed.

The current Session B request always outranks historical context. Task and
treatment names are replaced with opaque aliases until all calls finish.
This is label masking, not perfect blinding: representation shape can still
make a treatment inferable, and reports must state that limitation.

## 7. Outcomes

### Primary outcome: strict semantic success

`strict_semantic_success` is binary and equals `true` only when all of the
following hold:

1. all hidden functional tests pass;
2. every required active semantic obligation is satisfied;
3. no critical forbidden behavior occurs;
4. no deprecated decision is incorrectly applied;
5. no unrelated intent or protected scope is modified contrary to the oracle;
6. the current Session B request is not overridden by stale history.

There is no weighted primary composite. Partial credit cannot turn a strict
failure into a success.

### Secondary outcomes

- semantic-obligation recall: satisfied required obligations / total required;
- critical semantic violation count;
- wrong-intent or out-of-scope edit count;
- hidden behavioral test pass count;
- Session B elapsed time;
- time or event index to first correct write, when reliably observable;
- unique and repeated repository reads before the first correct write;
- files changed and patch size;
- Session B input, cached-input, non-cached-input, output, and reasoning-output
  tokens, reported separately rather than combined with Session A;
- handoff characters and provider-reported Session B input usage. The latter
  includes tool interaction and is not misreported as an isolated tokenizer
  count for the initial context file.

Timing and token metrics cannot replace the primary outcome after results are
known. Efficiency is interpreted only among trials with comparable quality.

## 8. Low-resource sequential design

No model is used for fixture construction, static validation, renderer parity
checks, task hashing, or reference-solution scoring.

### Stage 1 — development screening

This stage is explicitly non-confirmatory.

- six development C2/C3 tasks;
- `intent-full` and `flat-facts-matched`, one Session B run each: 12 calls;
- two C0 controls with `intent-full` and `no-history`, one run each: 4 calls;
- two C4 safety controls with `intent-full` and `flat-facts-matched`, one run
  each: 4 calls;
- maximum: 20 low-effort Session B calls.

Screening stops without confirmation if any of these occurs:

- fewer than three `Intent success / flat failure` pairs among the six C2/C3
  tasks;
- more than one `flat success / Intent failure` pair;
- flat facts succeed on all six C2/C3 tasks, indicating a ceiling;
- a C0 fixture is not solvable in both assigned conditions;
- Intent causes a history-driven critical violation on any C4 task;
- fact parity, checkpoint identity, label masking, or evaluator read isolation fails.

Screening results are used to debug the fixture family and harness only. They
must never be pooled into, substituted for, or presented as confirmation
results.

### Stage 2 — frozen holdout confirmation

Before any holdout output is inspected, freeze eight previously unused C2/C3
tasks, their ledgers, oracles, renderers, trial order, and hashes.
The CLI confirmation stage requires a lock JSON containing the exact task
hashes, conditions, repeats, seed, model, effort, and preregistration hash; a
user-supplied `--stage confirmation` label without this verified lock is
rejected.

The first confirmation pass runs:

- eight tasks;
- `git-only`, `flat-facts-matched`, and `intent-full`;
- one Session B run per task/condition;
- 24 low-effort Session B calls.

This pass can stop for futility, but cannot declare early success. Continue to
a second Intent/flat repeat only if the first pass has at least two
`Intent success / flat failure` pairs, no `flat success / Intent failure` pair,
and a positive Intent–Git strict-success difference. The second repeat adds 16
calls. The maximum primary confirmation budget is therefore 40 Session B
calls.

Infrastructure failure is handled by the rules in Section 11. Additional
repeats, models, or reasoning levels are separate studies.

## 9. Confirmatory thresholds and statistics

The primary contrast is paired within task/repeat block:

`intent-full` versus `flat-facts-matched` on C2/C3 strict semantic success.

Evidence for an object-model advantage requires all of the following:

- Intent strict semantic success is at least 75%;
- the absolute Intent-minus-flat success-rate difference is at least 10
  percentage points;
- a one-sided exact McNemar test on discordant pairs rejects the null that
  Intent is no more likely to succeed than flat facts at `alpha = 0.05`;
- there is no history-caused critical C4 violation in the frozen safety suite;
- all parity, label-masking, read-isolation, and reproducibility checks pass.

For illustration, six Intent-only successes and zero flat-only successes give
a one-sided exact discordant-pair probability of `1 / 64`, but the actual test
uses all observed discordant pairs rather than requiring that exact pattern.

The prespecified secondary semantic-history contrast is Intent versus Git. A
practical advantage requires an absolute strict-success difference of at least
20 percentage points. The paired raw table, exact McNemar result, and
uncertainty interval are reported even if the threshold is not met.

Reports include raw success counts, paired discordance tables, absolute effect
sizes, and 95% confidence intervals. The exact primary test uses the first
frozen repeat only, one paired outcome per task. A preregistered second repeat
is reported as an all-repeats sensitivity analysis and is not treated as an
independent task in the primary p-value. Secondary outcome tests are labeled
exploratory; no secondary metric can rescue a failed primary contrast.

The Stage 1 screen has no confirmatory p-value. Stage 2 has no early-success
look, so its final primary test is performed once after the preregistered stop
or second repeat.

## 10. Permitted and forbidden interpretations

- **Intent beats Git but ties flat facts:** evidence supports the value of
  semantic handoff over code-only history. It does not support superiority of
  the Intent object model over an equally informative summary.
- **Intent ties fact-matched flat facts:** the strongest permitted statement is
  that semantic handoff carries continuation value, if it also beats code-only
  baselines. The result cannot be described as an Intent structural advantage.
- **Intent beats flat facts only in C3:** the claim is restricted to dense,
  longitudinal, relational histories. It is not generalized to simple tasks.
- **C0 shows no gain and higher cost:** this is an expected boundary result,
  not evidence against the C2/C3 hypothesis.
- **No-history or Git reaches a ceiling in C2/C3:** the fixture failed to expose
  code-external semantic dependence. It remains in the report as
  non-discriminating.
- **Flat facts beat Intent:** the object representation may add friction or
  obscure information; this is a product-design result.
- **C4 failure:** stale semantic history overrode current authority. This is a
  safety failure and must be disclosed independently of aggregate efficacy.
- **Full transcript wins at much higher cost:** Intent may still have a
  compression tradeoff, but non-inferiority must be tested separately before
  making that claim.

No result from this protocol establishes market adoption, human workflow
benefit, long-term record quality, or reduced Session A recording burden.

## 11. Anti-cherry-picking and invalid-run rules

- Development and holdout task IDs are fixed before holdout outputs are read.
- Task specs, ledgers, hidden oracles, context renderers, source revision,
  prompts, and randomization seed are hashed in the manifest.
- Every attempted trial is retained and reported, including model failures and
  unfavorable outputs.
- An agent error, wrong patch, timeout caused by agent behavior, or failure to
  finish within the fixed budget counts as a task failure.
- A documented provider, authentication, or harness infrastructure failure may
  be retried only by rerunning the entire task/repeat condition block. The
  original failed artifacts remain public and the retry reason is recorded.
- If a fixture or oracle bug is found after trials begin, the task version is
  invalidated for every condition. It cannot be repaired only for the losing
  condition. A new version requires all paired conditions to rerun.
- Model, effort, timeout, prompt, tools, context budget, and score definitions
  cannot change within the cohort.
- No best-of-N selection is allowed. All preregistered repeats count.
- Screening tasks and results cannot enter the confirmation aggregate.
- C0, C1, C2/C3, and C4 are reported by stratum; favorable strata cannot be
  silently pooled while unfavorable strata are omitted.
- Private production data, secrets, and proprietary source code are excluded
  from fixtures and public artifacts.

## 12. Public report schema

The public report and machine-readable manifest must include at least:

### Study identity

- protocol version and preregistration commit;
- benchmark and Intent source revisions;
- harness, runner, Codex CLI, Python, and operating-system versions;
- model and reasoning effort;
- study stage: screening or confirmation.

### Task identity

- task ID, version, stratum, and stratum justification;
- task-spec, oracle, atomic-ledger, checkpoint-tree, Git HEAD/tree, status, and
  object-set hashes;
- relevant and distractor fact counts;
- required code-external fact count and Git-observability annotation;
- hidden-test command and test identifiers, without publishing secrets during
  a still-running study.

### Trial identity

- anonymous condition ID used by Session B and decoded condition in the final
  report;
- task, repeat, randomized order, and randomization seed;
- common prompt hash, rendered-context hash, fact IDs, fact-coverage result,
  context characters and the preflight character-parity result;
- clean-environment/isolation status;
- timestamps, elapsed time, terminal status, and any infrastructure error;
- retry or exclusion status with a predefined reason.

### Resource and behavior data

- Session B input, cached-input, non-cached-input, output, and reasoning-output
  tokens;
- tool calls, reads, writes, changed files, and patch size when observable;
- time/event index to first correct write when measurable;
- raw agent event-log and patch artifact paths plus checksums.

### Scoring and analysis

- every strict-success component;
- hidden-test pass/fail results;
- required obligations satisfied and critical violations;
- raw per-trial outcome, not only averages;
- paired discordance tables;
- success rates, absolute differences, confidence intervals, and exact test
  results;
- screening gates, confirmation stopping decision, and whether every claim
  threshold was met;
- all deviations from this preregistration.

The report must end with the strongest claim actually licensed by Section 10,
including an explicit null or negative conclusion when required.
