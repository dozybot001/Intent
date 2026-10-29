# Intent flow: relations between Intents

[中文](../CN/intent-flow.md) | English

Status: design (2026-10-30), not implemented yet. Target: Intent 7.2.

## Principles

- Flow happens only between Intents. Every Snap already belongs to exactly one Intent, which is the relation between work and meaning, so Snaps get no further relations.
- A relation answers one of two questions: where a goal comes from, and what constrains it. Anything else counts as unrelated and is not recorded.
- Relation states are not stored. They are derived from the statuses of the two Intents, so they cannot disagree with the objects and cannot conflict in a merge.
- Like everything else, relations are append-only. They can be added and withdrawn, but a written record is never edited or deleted.
- This does not depend on semantic Git. It can ship before 8.0, and the format-2 migration keeps it as it is.

## Five relations

| Type | Flag (B relative to A) | Meaning | Flow view |
|---|---|---|---|
| **part of** `part_of` | `--part-of A` | B is a part of A: A is not complete until B is done or dropped | branches off A and rejoins A when it ends |
| **derived from** `derived_from` | `--derived-from A` | B arose while working on A, but A does not need B | branches off A and does not rejoin |
| **succeeds** `succeeds` | `--succeeds A` | B takes over A's aim: the next stage, a changed approach, or a merged duplicate | A's lane flows into B |
| **depends on** `depends_on` | `--depends-on A` | B cannot proceed until A is done | thin arrow from A to B |
| **conflicts with** `conflicts_with` | `--conflicts-with A` | A and B cannot both be achieved as stated: competing approaches or opposing goals | dashed line, both ways |

Why these five: the first three say where B comes from: inside A (part of), beside A because of A (derived from), or in A's place (succeeds). The last two say what constrains B: it must wait for A (depends on), or it cannot coexist with A (conflicts with). Together they draw branching, flow and convergence:

- **Branching:** part of, derived from, and one Intent succeeded by several.
- **Flow:** succeeds.
- **Convergence:** parts rejoining their parent, and several Intents succeeded by one, for example merged duplicates or goals combined into one.

"Succeeds" means carrying the aim forward, like a successor in a role. It is not subclassing: a narrower sub-goal is a part or is derived.

There is deliberately no weak "related" or "see also" relation. It has no criterion, agents would overuse it, and the graph would turn into noise.

## Relation states

| Type | States (derived from the two statuses) |
|---|---|
| part of | in progress → done / dropped; a hint when A has ended while B is still open |
| derived from | none; it only records the origin |
| succeeds | handover pending (A still active or suspended) → handed over (A ended) |
| depends on | blocked (A not done) → satisfied (A done) / broken (A cancelled; needs attention) |
| conflicts with | unresolved (both open) → resolved (at least one ended) |

States that need attention (blocked, broken, unresolved, handover pending) appear in `itt inspect`, in the opening context and in IntHub's continuation brief.

## Rules

- Between two Intents there is at most one active relation at a time.
- An Intent has at most one parent: either part of or derived from, pointing at one Intent.
- part of, succeeds and depends on never form cycles. No Intent relates to itself, and the target must exist.
- An Intent that has ended cannot gain new parts.

## Commands

```bash
itt intent create "Add Apple Pay" --why "…" --part-of intent-003
itt intent relate intent-007 --depends-on intent-004          # add later, at any time
itt intent unrelate intent-007 intent-004                      # withdraw the active relation between them
itt intent cancel intent-005 --into intent-008 --reason "duplicate"  # end it; intent-008 succeeds it
itt decision create "Payments go through PaymentIntents only" --why "…" --from intent-003
```

`--into` on `done` or `cancel` ends the Intent and records on the target that it succeeds this one. `itt show ID` lists relations in both directions, with their states.

## Storage

Intents gain an optional `relations` field, written on the Intent that declares the relation (B):

```json
"relations": [
  {"type": "part_of", "intent": "intent-003", "created_at": "2026-11-02T08:15:00+00:00"},
  {"type": "depends_on", "intent": "intent-004", "created_at": "…", "removed_at": "…"}
]
```

Withdrawing only adds `removed_at`. An Intent without relations has no such field, so existing objects and checksums do not change.

## Decision sources

Today a Decision applies globally. At creation it links to every active Intent, and every Intent created or resumed later links to it too. What it does not record is the Intent it came from.

Decisions gain an optional `source_intent_id`, written at creation with `--from ID` and never changed. Without it a Decision is sourceless, which means project-level. It still applies globally, as now.

The source is not inferred. A project-wide rule written while some goal is active does not necessarily come from that goal, and a wrong source misleads more than a missing one. The Skill tells agents to pass `--from` when a Decision really comes from the current goal.

## Flow view

IntHub gains a Flow page:

- Each Intent is a node, ordered left to right by creation time. Parts and derived Intents sit below their parent. A successor continues on the same lane, to the right of the Intent it succeeds.
- Line styles follow the table above. Node colour only shows status, and always comes with text.
- Decisions are diamonds on their source Intent. Sourceless Decisions sit in a Project band at the top, and deprecated ones are hollow.
- Snaps are not nodes. A node shows its Snap count, and clicking it opens the existing detail sheet.
- Ended Intents can be hidden, or the view can focus on one Intent's neighbourhood.

Acceptance: one fixture history per relation type, then real projects. The view is done when a reader can tell from the graph alone, without opening Snaps, how the goals branched, continued and converged.

## Compatibility

- Older `itt` versions ignore the new fields when reading. If an existing Intent later gains a relation, though, 7.1 and earlier reject the pull in their fast-forward check and need to upgrade to 7.2. 7.2 also lets that check tolerate fields added in the future, so this does not happen again.
- The 8.0 migration keeps these fields as they are. In a semantic merge, relation records are united and a withdrawal wins. A merge that leaves an Intent with two parents or a cycle becomes a structured conflict for the user to resolve.
