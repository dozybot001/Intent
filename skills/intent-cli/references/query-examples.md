# When To Record

Use these examples to decide when Intent recording is warranted.

## Quick matrix

| Task shape | New intent? | Checkpoint? | Notes |
| --- | --- | --- | --- |
| brief read-only question | no | no | explain omission if substantive |
| bug fix with code/tests | yes (unless active intent matches) | yes | preserve the problem as the intent title |
| refactor or architecture | yes | yes, with rationale | record structural choices in `-m` |
| docs or UX pass | maybe | yes if meaningful rewrite | skip for typo fixes |
| explicit tradeoff | yes | yes, with rationale | clearest case for `-m "why"` |
| follow-up within same work | no, continue active intent | if new step appears | avoid fragmenting one problem |
| vague request | not yet | no | clarify scope first |

## Pattern

For each request, decide:
1. Is this substantive enough for Intent records?
2. Continue active intent or start new?
3. What is the shortest useful intent title?

## Intent title heuristics

Prefer: short, problem-oriented, stable after the query is forgotten.

Good: `Extract persistence from core`, `Choose docs structure`
Bad: `Fix things`, `Continue work`, `User asked me to improve stuff`

## When to use rationale (`-m`)

Use `-m` when:
- You chose between meaningful alternatives
- The reason matters for future reference
- An architectural or design principle was established

Skip `-m` when:
- The checkpoint title is self-explanatory
- The change is mechanical
