# Intent Evaluation Design

[中文](../CN/evaluation.md) | English

Intent's core claim cannot be proven by reasoning alone. It needs a reproducible and falsifiable evaluation framework that answers two questions:

- Whether `itt` adds little enough workflow overhead
- Whether `intent / snap / decision` helps the next session resume work, and whether those object boundaries are necessary

## 1. Core Hypotheses

### H1: Low Interference

Using Intent should not significantly increase the burden on the user or agent.

Observable signals:

- Extra command count
- Recording time
- Extra token / character count
- User confirmation count
- Whether recorded object count grows out of control

### H2: High Resume Value

After a new session, agent switch, or context loss, `itt inspect` should reduce re-explanation and repeated investigation.

Observable signals:

- Time to first correct next action
- Context clarification count
- Repeated file reads, repeated investigation, or repeated trial-and-error
- Long-lived decision violations
- Whether the final patch continues the original goal

### H3: Necessary and Sufficient Object Design

`intent / snap / decision` should be a low-redundancy minimal object set.

- Sufficiency: full Intent context should approach full transcript resume quality at much lower cost
- Necessity: removing an object or key field should cause explainable degradation

## 2. Generic Task Suite

Evaluation tasks should not be selected from Intent's own history or from favorable project-specific examples. They should be redesigned as generic, reproducible, small development scenarios in independent fixture repositories.

Each task includes:

- A small code repository
- Initial code state
- Session A goal
- Code state after Session A
- Optional long-lived constraints
- Session B continuation goal
- Hidden oracle: correct behavior, forbidden behavior, scoring criteria

Tasks should cover common agent development work, not only cases where Intent is expected to shine.

### Task Types

| Type | What it tests | Example |
| --- | --- | --- |
| Bug continuation | Whether recent investigation and next steps transfer | Session A finds the true cause but does not finish the fix; Session B continues |
| Feature continuation | Whether goal and milestones are clear | Session A completes the API layer; Session B continues UI or tests |
| Refactor continuation | Whether architectural intent carries forward | Session A extracts an interface; Session B migrates remaining call sites |
| Decision inheritance | Whether long-lived constraints are honored | Constraint: do not add dependencies, or preserve public API compatibility |
| Decision conflict | Whether conflicts are detected | Session B request conflicts with an active decision |
| Negative handoff | Whether low-signal semantics avoid polluting resume | Session A only includes mechanical edits or failed attempts |
| Multi-intent ambiguity | Whether multiple goal states can be distinguished | One active intent, one suspended intent; Session B should continue only the relevant one |
| Correction recovery | Whether wrong direction or reversal can be recovered | Session A rejects an earlier approach; Session B should not continue the discarded path |

## 3. Task Generation Rules

To avoid designing tasks specifically for Intent, each task should satisfy these constraints:

- Small, but not toy-sized: usually 5-20 files
- Requires changes across at least 2 files
- Session A leaves non-obvious context such as investigation findings, tradeoffs, rejected options, or long-lived constraints
- Session B cannot infer the whole answer from the diff alone
- The oracle can distinguish correct work from superficially complete but wrong-direction work
- Each task type has multiple equivalent instances to reduce overfitting

Generic task domains can include:

- CLI tools
- REST APIs
- Small frontend components
- Data processing scripts
- Configuration / deployment scripts
- Documentation and agent skill synchronization

## 4. Context Conditions

The same task should run under multiple context conditions.

| Condition | What Session B can see | Purpose |
| --- | --- | --- |
| No history | Repository only | Lower bound |
| Git only | Code + commit / diff / commit message | Git baseline |
| Chat summary | Plain human-written or agent-written summary | Unstructured semantic baseline |
| Full transcript | Full or high-quality compressed conversation | High-cost upper bound |
| Intent full | `intent + snap + decision` | Tested approach |

## 5. Ablation Conditions

To test object design rather than merely "summary beats no summary", remove objects or fields.

| Ablation | Expected degradation |
| --- | --- |
| No intent | Goal boundary is unclear; agent may continue the wrong task |
| No snap | Recent progress and investigation findings are lost; repeated work increases |
| No decision | Long-lived constraints are easier to violate |
| No why | Agent knows what happened, but not why; continuation quality drops |
| No status | Agent may continue done / deprecated objects |
| No relation links | Search and attribution cost increases |

If an ablation does not consistently degrade results, the corresponding object or field has not been proven necessary and should be redesigned or removed.

## 6. Metrics

### Workflow Cost

- `record_command_count`
- `record_elapsed_seconds`
- `record_token_estimate`
- `user_confirmation_count`
- `objects_created`

### Resume Quality

- `time_to_first_correct_action`
- `clarification_count`
- `repeated_investigation_count`
- `decision_violation_count`
- `wrong_direction_edits`
- `task_success`
- `patch_quality_score`

### Blind Review

Reviewers see only Session B behavior and output, not the context condition.

Scoring dimensions:

- Did the agent understand the goal?
- Did it understand recent progress?
- Did it honor long-lived constraints?
- Did it avoid repeated investigation?
- Did it produce a correct patch?

## 7. Success Criteria

Intent does not need to beat the information volume of a full transcript. It should approach transcript-level resume quality with much lower cost.

Reasonable success criteria:

- `Intent full` resume quality is significantly higher than `Git only` and `Chat summary`
- `Intent full` recording and reading cost is significantly lower than `Full transcript`
- Removing `intent`, `snap`, or `decision` causes explainable degradation in corresponding task types
- Repeated investigation, decision violations, and goal misunderstanding that appear under `No history` or `Git only` are materially reduced under `Intent full`

## 8. Minimal Viable Evaluation

The first version does not need a large-scale experiment. It should be small but rigorous:

- 8 task types
- 3 instances per type
- 5 context conditions
- 6 ablation conditions
- At least 3 repetitions per condition

This is enough to produce initial reproducible data and expose weak points in the object design.

The first runnable harness is exposed through [`itt benchmark`](benchmark-cli.md), so different agents can generate context, continue tasks, and score completed repositories against the same tasks.

## 9. Falsification First

The purpose of evaluation is not to prove Intent is always right. It is to discover where it fails.

Pay special attention to:

- Whether a plain summary is already enough
- Whether decisions accumulate into noise
- Whether snaps become mechanical logs
- Whether `why` often becomes vague filler
- Whether object relations actually lower resume cost
- Whether user-triggered retrospective recording is more reliable than automatic recording

If data confirms these problems, Intent should adjust the object model or recording workflow instead of defending the original design.
