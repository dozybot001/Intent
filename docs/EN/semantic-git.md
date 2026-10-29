# Semantic Git: design proposal for Intent 8

[中文](../CN/semantic-git.md) | English

Status: proposal (2026-10-30). Target: Intent 8.0.

## Goal

`itt` should behave like Git for semantic history. A developer who knows Git should be able to predict how Intent handles parallel work, several machines, worktrees and divergence, because Intent handles them the way Git does.

Today (7.x) this is not true:

- Object IDs are per-copy counters (`snap-003`), so two copies that record in parallel mint the same IDs.
- A project has one linear history. Push and pull only fast-forward; when two copies diverge, `itt status` reports `diverged` and there is no way to merge.
- Every pushed revision stores a full snapshot, and the local repository keeps no revision history at all.
- In a Git worktree, Intent does not find the main checkout's `.intent/`.

## One deliberate difference: no staging area

Git asks people to stage and commit. Intent's writers are mostly agents in the middle of other work, and its first promise is low disruption. So every write (`intent create`, `snap create`, a status change) creates a revision immediately, like `git commit -a` with a generated message. Everything else follows Git.

## Concept mapping

| Git | Intent 8 |
|---|---|
| blob | an object version: the JSON content of one Intent, Snap or Decision at one point |
| tree | the project state: object ID → object version |
| commit | a **revision**: tree, parent revisions, author/origin, time, a generated summary and the list of changed objects |
| object hash | content-addressed IDs for new objects (`snap-3f9a2c1…`, shown shortened like Git, unique prefixes accepted). Legacy counter IDs stay valid forever |
| `HEAD`, branches, refs | `.intent/HEAD`, `refs/heads/*`; `itt branch`, `itt switch` |
| `git log` / `show` / `diff` | `itt log` (revisions), `itt show ID|REV`, `itt diff A..B` (semantic: added Snaps, status changes, new or retired Decisions) |
| `git status` | branch, upstream, ahead/behind counts |
| remotes, `fetch`, `pull`, `push`, `clone` | `itt remote`, `itt fetch` into `refs/remotes/origin/*`, `itt pull` = fetch + merge, `itt push` (rejected when behind, as in Git), `itt clone URL --project NAME` |
| three-way merge | **semantic three-way merge** against the merge base (below) |
| worktrees | the repository is found through `git rev-parse --git-common-dir`, so all worktrees share one semantic repository; each worktree has its own `HEAD` |
| tags | `itt tag` for milestones (later) |

## Storage (repository format 2)

```text
.intent/
  objects/ab/cdef….json        immutable object versions, addressed by hash
  revisions/ab/cdef….json      {parents, tree, author, origin, time, summary, changes}
  refs/heads/main
  refs/remotes/origin/main
  HEAD                         "ref: refs/heads/main"
  config.json                  remotes, upstreams, maintenance flags
```

Objects keep a stable identity minted at creation. Changing an Intent's status writes a new version of the same ID, exactly like editing a file in Git. Relation lists (`snap_ids`, `decision_ids`, `intent_ids`) become grow-only sets.

## Semantic merge

Because Snaps are append-only and new IDs never collide, most merges are a union. For each object changed on both sides since the merge base:

- grow-only relation sets: union, ordered by `created_at`;
- `status`: identical on both sides, or changed on only one side, merges cleanly; two different new statuses (for example `done` and `cancelled`) are a conflict;
- `reason` and the write-once descriptive fields: a conflict only if both sides changed them differently.

Conflicts are structured, not text markers: `itt merge` stops, `itt status` lists conflicted objects with both values, `itt resolve ID --status done` (or `--ours`/`--theirs`) settles each one, then `itt merge --continue` or `itt merge --abort`. Agents get the same information as JSON.

## Remote protocol 3 and IntHub

Push and fetch negotiate missing revisions and object versions, the way Git negotiates packs. IntHub stores the revision DAG and deduplicated objects, which also removes today's full snapshot per push. Branch refs are per project; the web app shows `main` first and gains a branch and history view. IntHub accepts the 7.x protocol during a migration window.

## Migration from 7.x

`itt` 8 converts a 7.x repository losslessly on an explicit `itt migrate` (and refuses to write before it): current objects become the first revision, legacy IDs are kept, and the IntHub remote is relinked to the same project. Downgrading after migration is not supported, so the command makes a backup first.

## Phases

1. Repository format 2: objects, revisions, refs, automatic revisions, `itt log`, `show`, `diff`, migration, hash IDs for new objects.
2. Branches and worktrees: `itt branch`, `itt switch`, Git-worktree discovery.
3. Semantic merge with structured conflicts.
4. Remote protocol 3: `fetch`, `pull` = fetch + merge, `push`, `clone`; IntHub revision DAG and branch views.
5. Agent workflows: Skill and hook guidance for branches and conflicts.

Each phase ships with migration and compatibility tests; phases 1 to 3 are local-only and can be released before the server changes.

## Questions for the owner

1. Hash IDs for new objects (recommended), or keep counters with a per-copy prefix?
2. Automatic revision per write (recommended), or an explicit `itt commit`?
3. At launch, should IntHub show branches, or only `main` with merge history?
