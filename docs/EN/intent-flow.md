# Intent flow: relations between Intents

[中文](../CN/intent-flow.md) | English

Relations record how your goals connect: where a goal comes from and what constrains it. You write them with `itt`, and the Flow page in IntHub draws them.

Relations exist only between Intents. A Snap already belongs to one Intent, so it takes no relation of its own.

## Five relations

Each relation is recorded on one Intent (B) and points at another (A).

| Type | Flag on B | Meaning | On the Flow page |
|---|---|---|---|
| **part of** `part_of` | `--part-of A` | B is a part of A: A is not complete until B is done or dropped | A line off A's trunk with a filled dot at B; ended parts rejoin A's row |
| **derived from** `derived_from` | `--derived-from A` | B arose while working on A, but A does not need B | A lighter line off A's trunk with a hollow dot at B; it does not rejoin |
| **succeeds** `succeeds` | `--succeeds A` | B takes over A's aim: the next stage, a changed approach, or a merged duplicate | A thick arrow from A to B, usually along one row |
| **depends on** `depends_on` | `--depends-on A` | B cannot proceed until A is done | A thin arrow from A to B: amber while blocked, green once satisfied, red if broken |
| **conflicts with** `conflicts_with` | `--conflicts-with A` | A and B cannot both be achieved as stated: competing approaches or opposing goals | A dashed line marked "vs": amber until one side ends, then faded |

The first three say where B comes from: inside A (part of), beside A because of A (derived from), or in A's place (succeeds). The last two say what constrains B: it must wait for A (depends on), or it cannot coexist with A (conflicts with). Anything else counts as unrelated and is not recorded.

Together they draw branching, flow and convergence:

- **Branching:** part of, derived from, and one Intent succeeded by several.
- **Flow:** succeeds.
- **Convergence:** parts rejoining their parent, and several Intents succeeded by one, for example merged duplicates.

"Succeeds" means carrying the aim forward, like a successor in a role. It has nothing to do with subclassing: a narrower sub-goal is a part or is derived.

There is deliberately no weak "related" or "see also" relation. It would have no clear test, agents would overuse it, and the graph would turn into noise.

## Writing relations

```bash
itt intent create "Add Apple Pay" --why "…" --part-of intent-003
itt intent relate intent-007 --depends-on intent-004          # add one later, at any time
itt intent unrelate intent-007 intent-004                      # withdraw the active relation between them
itt intent cancel intent-005 --into intent-008 --reason "duplicate"  # end it; intent-008 succeeds it
itt show intent-007                                            # relations in both directions, with states
```

`itt intent create` takes one parent (`--part-of` or `--derived-from`) plus any number of `--succeeds`, `--depends-on` and `--conflicts-with`. `itt intent relate` records one relation at a time.

`--into` works on `done` and `cancel`. It ends the Intent and records that the target succeeds it. If the two Intents conflicted, that conflict is withdrawn, because ending one in favour of the other resolves it.

The rules:

- Two Intents share at most one active relation at a time.
- An Intent has at most one parent: one part of or derived from relation, pointing at one Intent.
- Parent relations, succeeds and depends on never form cycles.
- An Intent cannot relate to itself, and the target must exist.
- An Intent that has ended cannot gain new parts.
- Relations are append-only. Withdrawing one marks it as withdrawn and keeps the record.

## How state is derived

A relation's state is never stored. `itt` and IntHub work it out from the statuses of the two Intents, so it always matches them.

| Type | States |
|---|---|
| part of | in progress → done / dropped; parent ended if A ends while B is still open |
| derived from | none; it only records the origin |
| succeeds | handover pending while A is open → handed over once A has ended |
| depends on | blocked while A is not done → satisfied once A is done; broken if A is cancelled |
| conflicts with | unresolved while both are open → resolved once either has ended |

States that need attention (parent ended, handover pending, blocked, broken, unresolved) appear in `itt inspect`, in the opening context an agent receives, and in IntHub's continuation brief.

`itt` reports these states and does not enforce them. You can end A while a part is still open, or keep working on a blocked B. The state tells you and the next agent what needs handling.

## The Flow page

Flow is a tab in every IntHub project. It draws `main` on IntHub, so a new relation appears once it reaches `main` there.

- Related Intents sit in groups. Groups with open work come first, and they fill the page rightwards, then down. Each Intent is a card with its creation date in the corner.
- Parts and derived Intents sit one column right of their parent and share one trunk. A successor continues the same row. An Intent that depends on or conflicts with another, and has no parent or predecessor, sits to its right.
- Ended parts come back to one point on the parent's row. One ended part with no successor after its parent draws neither that point nor a line back.
- Line styles follow the table above. Amber means the relation needs attention. The legend lists only the marks in use.
- Card colour only shows status, and always comes with text.
- Decisions are diamonds under their source Intent. Project-level Decisions sit in a Project band at the top, and deprecated ones are hollow.
- Snaps are not drawn. A card shows its Snap count, and clicking it opens the detail sheet.
- Intents with no relations are listed below the graph.
- **Hide ended** removes Intents that have ended. **Focus on…** shows one Intent and its direct relations.

## Decision sources

A Decision applies to the whole project. When you create it, it links to every active Intent, and every Intent created or reactivated later links to it too.

To record which Intent a Decision came from, add `--from` when you create it:

```bash
itt decision create "Payments go through PaymentIntents only" --why "…" --from intent-003
```

The source is written once and never changes. It only records the origin, so the Decision still applies to the whole project. Without `--from`, the Decision is project-level.

The source is never inferred. A project-wide rule written while some goal is active does not necessarily come from that goal, and a wrong source misleads more than a missing one. Add `--from` only when the Decision really comes from that Intent.

## Compatibility

Relations are optional, and an Intent without any stores nothing extra. If your project uses them, everyone who pulls needs `itt` 7.2 or later: older versions reject a pull once an Intent they already hold gains a relation.
