# Query To Semantic Record Examples

Use these examples to derive high-signal `intent` and `decision` records from real user requests.

## Quick Recording Matrix

| Task shape | New intent? | Run? | Checkpoint? | Decision? | Notes |
| --- | --- | --- | --- | --- | --- |
| brief read-only question | no | no | no | no | explain omission if this was a substantive pass |
| bug fix with code or tests | usually yes, unless active intent already matches | yes | usually yes | only if a durable tradeoff appears | preserve the problem as the intent, not the exact wording |
| refactor or architectural cleanup | usually yes, unless continuing current work | yes | yes | often yes | good place to record structural decisions |
| docs or UX wording pass | usually yes for a meaningful rewrite | yes | yes | maybe | only create a decision if a lasting principle is chosen |
| explicit tradeoff or option selection | yes | yes | yes | yes | this is the clearest case for a decision |
| release-process or policy change | usually yes | yes | yes | often yes | record durable release rules, not every checklist step |
| follow-up request within the same work slice | usually no, continue active intent | yes | if a new candidate appears | maybe | avoid fragmenting one problem across many intents |
| vague request with unclear scope | not yet | maybe after clarification | no | no | first restate the assumed work slice before recording |

## Pattern

For each new request, decide four things:

1. is this substantive enough to deserve Intent records at all
2. should the current active intent be continued or should a new one be created
3. what is the shortest useful intent title
4. whether the user request implies a durable `decision`, or only implementation work

The goal is not to mirror the whole query. The goal is to preserve the semantic unit of work.

## Example 1: Bug Fix

User query:

> The CLI crashes when `itt run end` is called with no active run. Please fix it and add tests.

Suggested intent:

- `Handle run end without an active run`

Why:

- the request is substantive
- it describes one concrete correctness problem
- the title preserves the work unit without copying the full sentence

Likely records:

- create or continue an intent
- start a run
- create a checkpoint after the fix and tests are in place
- adopt once that candidate is chosen
- no decision unless a durable tradeoff appears

## Example 2: Refactor

User query:

> The persistence logic in `core.py` is getting too heavy. Split storage concerns out so the domain logic is easier to maintain.

Suggested intent:

- `Extract persistence from core`

Possible decision:

- `Keep persistence in a dedicated store layer`

Why the decision is worth recording:

- it is an architectural choice likely to survive beyond the immediate patch
- future contributors may need to understand why storage was separated from domain logic

## Example 3: UX Copy Tuning

User query:

> The README still sounds too self-referential. Make it feel more like a normal open-source project homepage.

Suggested intent:

- `Neutralize README tone`

Likely records:

- intent, run, checkpoint, adoption
- no decision unless the rewrite locks in a durable documentation principle

Good decision only if needed:

- `Keep public docs descriptive rather than self-evaluative`

## Example 4: Competing Approaches

User query:

> I’m not sure whether docs should be split by language or by topic. Please evaluate both and choose one.

Suggested intent:

- `Choose documentation structure`

Likely decision:

- `Organize docs by language`

Why:

- the user is explicitly asking for a tradeoff resolution
- the chosen structure will influence later work and should be easy to inspect

Possible sequence:

```bash
itt start "Choose documentation structure"
itt run start
itt snap "Language-based docs structure proposal"
itt adopt -m "Adopt language-based docs structure"
itt decide "Organize docs by language" --because "Language choice is the first branch readers need; topic grouping can stay inside each language tree."
itt run end
```

## Example 5: Packaging / Release Work

User query:

> Make this repo feel more release-ready: add a changelog, release baseline, and check script.

Suggested intent:

- `Prepare release baseline`

Likely decision:

- only if a durable release-process rule is introduced, such as where templates live or what must run before tagging

## Example 6: Continue Existing Work

Current active intent:

- `Improve agent-facing CLI contract`

New user query:

> Also make `inspect --json` include clearer next-step hints for agents.

Suggested action:

- continue the existing intent rather than starting a new one

Why:

- the request is clearly part of the same work slice
- opening a second intent would fragment semantic history

## Example 7: Skip Intent Recording

User query:

> What does `itt inspect --json` return at the top level?

Suggested action:

- no new intent
- explain that this is a brief read-only explanation and does not need semantic records

Good omission explanation:

- `This pass is a short read-only explanation, so I’m not creating a new Intent record.`

## Example 8: Ambiguous Request

User query:

> Clean this up and make it better.

Suggested action:

- do not guess too aggressively
- first inspect current context and restate the assumed work slice

Good intent after clarification:

- `Clarify CLI help output`
- `Simplify persistence boundaries`
- `Tighten bilingual doc wording`

Bad intent:

- `Make it better`

## Heuristics For Intent Titles

Prefer titles that are:

- short
- problem- or outcome-oriented
- stable after the exact wording of the user query is forgotten

Prefer:

- `Extract persistence from core`
- `Clarify release workflow`
- `Choose documentation structure`

Avoid:

- `User asked me to maybe improve some stuff`
- `Fix things`
- `Continue work`

## Heuristics For Decisions

Create a decision when:

- the user asks to choose between meaningful options
- you adopt a rule that future work should follow
- the rationale is likely to matter later even if the code changes again

Do not create a decision when:

- you are just describing what a command does
