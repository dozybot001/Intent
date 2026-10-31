# Semantic Git: design for Intent 8

[中文](../CN/semantic-git.md) | English

Status: phases 1 to 3 shipped in Intent 8.0; phase 4 has not started.

## Goal

`itt` should behave like Git for semantic history. A developer who knows Git should be able to predict how Intent handles parallel work, several machines, worktrees and divergence, because Intent handles them the way Git does.

Today (7.x) this is not true:

- Object IDs are per-copy counters (`snap-003`), so two copies that record in parallel mint the same IDs.
- A project has one linear history. Push and pull only fast-forward; when two copies diverge, `itt status` reports `diverged` and there is no way to merge.
- Every pushed revision stores a full snapshot, and the local repository keeps no revision history at all. Status changes carry no timestamp.
- In a Git worktree, Intent does not find the main checkout's `.intent/`.

## Decisions (2026-10-30)

- New objects get hash IDs. Legacy counter IDs stay valid forever.
- Every write creates a revision. There is no `itt commit`.
- At launch, IntHub shows `main` and its merge history, with no branch graph.
- Intent flow is modelled as relations between Intents, not as branches (see [Intent flow](intent-flow.md)). It ships in 7.2, before this work.

## One deliberate difference: no staging area

Git asks people to stage and commit. Intent's writers are mostly agents in the middle of other work, and its first promise is low disruption. So every write (`intent create`, `snap create`, a status change) creates a revision immediately, like `git commit -a` with a generated message. Everything else follows Git.

## Concept mapping

| Git | Intent 8 |
|---|---|
| blob | an object version: the JSON content of one Intent, Snap or Decision at one point |
| tree | the project state: object ID → object version |
| commit | a **revision**: tree, parent revisions, author/origin, time, a generated summary and the list of changed objects |
| object hash | hash IDs for new objects (`snap-3f9a2c1…`, shown shortened like Git, unique prefixes accepted). Legacy counter IDs stay valid |
| `HEAD`, branches, refs | `.intent/HEAD`, `refs/heads/*`; `itt branch`, `itt switch` |
| `git log` / `show` / `diff` | `itt log` (revisions; `--graph` draws branches), `itt show ID|REV`, `itt diff A..B` (semantic: added Snaps, status changes, new or retired Decisions) |
| `git status` | branch, upstream, ahead/behind counts |
| remotes, `fetch`, `pull`, `push`, `clone` | `itt remote`, `itt fetch` into `refs/remotes/origin/*`, `itt pull` = fetch + merge, `itt push` (rejected when behind, as in Git), `itt clone URL --project NAME` |
| three-way merge | **semantic three-way merge** against the merge base (below) |
| worktrees | the repository is found through `git rev-parse --git-common-dir`, so all worktrees share one semantic repository; each worktree has its own `HEAD` and pushes its own branch. A bare repository or `--separate-git-dir` names no main worktree, so there each worktree keeps its own `.intent/` |
| tags | `itt tag` for milestones (later) |

## Storage (repository format 2)

```text
.intent/
  objects/ab/cdef….json        immutable object versions, addressed by hash
  trees/ab/cdef….json          {id: version} in two levels of buckets, shared between revisions
  revisions/ab/cdef….json      {parents, tree, author, origin, time, summary, changes}
  refs/heads/main
  refs/remotes/origin/main
  HEAD                         "ref: refs/heads/main"
  config.json                  remotes, upstreams, maintenance flags
```

`intents/`, `snaps/` and `decisions/` stay as the readable working copy, like Git's working tree. Each write changes the working copy and then records it as a revision, so an interruption leaves at most one unrecorded change, which the next write picks up. A command refused or killed part way is undone, by itself or by the next one, so a revision never holds half a command.

Objects keep a stable identity minted at creation. Changing an Intent's status writes a new version of the same ID, exactly like editing a file in Git. Relation lists (`snap_ids`, `decision_ids`, `intent_ids`) and the entries of an Intent's `relations` become grow-only sets.

## Semantic merge

Because Snaps are append-only and new IDs never collide, most merges are a union. For each object changed on both sides since the merge base:

- grow-only relation sets: union, our entries first and theirs after. Position carries no meaning: the latest Snap is chosen by `created_at`, and the hub compares these lists as sets;
- `status`: identical on both sides, or changed on only one side, merges cleanly; two different new statuses (for example `done` and `cancelled`) are a conflict;
- `reason` and the write-once descriptive fields: a conflict only if both sides set them differently;
- Intent `relations`: entries are united and a withdrawal wins. A merge that leaves an Intent with two parents or a cycle is a conflict.

Conflicts are structured, not text markers: `itt merge` stops, `itt status` lists conflicted objects with both values, `itt resolve ID --status done` (or `--ours`/`--theirs`) settles each one, then `itt merge --continue` or `itt merge --abort`. Agents get the same information as JSON. After a merge, open Intents with the same normalized WHAT are listed as possible duplicates. Combining them is always an explicit `--into`.

## Branches are not intent flow

The natural picture of a branch view is intents flowing, branching and converging. A Git-style branch cannot show that. A branch records *where* changes were recorded (a machine, a worktree, an agent session), not *how goals relate*. With automatic revisions:

| Situation | Revision branches show | The intent flow is |
|---|---|---|
| One agent in one worktree finds sub-goal B while working on A | one straight line | B branches from A |
| Two worktrees work on unrelated goals A and C, then merge | a branch and a merge | two independent goals |
| A laptop and a desktop both record Snaps on A, then merge | a branch and a merge | one goal, recorded in two places |
| Approaches X and Y are tried for A, and Y wins | nothing, if both were recorded on one branch | A forks into X and Y; X ends in Y |
| Two copies each create "Add Apple Pay", then merge | a merge | one goal recorded twice, to be combined |

Git has the same gap. Its commit graph shows parallel work, and teams express feature structure through conventions such as one branch per feature. Intent cannot rely on such a convention, because agents do not keep it.

So intent flow is recorded as relations between Intents (see [Intent flow](intent-flow.md)). Snaps already belong to one Intent, and Decisions can name the Intent they came from. The history layer adds what relations cannot: when each change happened and where it was recorded. Revision branches appear only as provenance and in `itt log --graph`, the way `git log --graph` serves Git users.

## Remote protocol 3 and IntHub

`itt push` uploads what the remote lacks, then moves one ref. As on a Git remote, the ref moves only from where the pusher saw it, only forward, and only once everything it reaches has arrived. `itt fetch` downloads what the local tips lack, in pages. IntHub stores the revision DAG as content-addressed blobs with branch refs per project, and its history page shows `main` with its merges. `main` is also kept as a snapshot per push, which the web views and protocol 2 read.

A project's protocol 2 pushes become revisions the first time the graph is used, each keeping its old ID in `legacy`, so a copy from before the graph can find a merge base from the last push it saw. Older clients can keep reading and pushing `main` during the migration window, and their pushes join the graph.

## Migration from 7.x

`itt` 8 converts a 7.x repository losslessly on an explicit `itt migrate`, and refuses to write before it. Current objects become the first revision, legacy IDs are kept, and the IntHub remote is relinked to the same project. Downgrading after migration is not supported, so the command makes a backup first.

## Phases

Phases 1 to 3 shipped in Intent 8.0, and phase 4 in 8.1.

1. Repository format 2: objects, revisions, refs, automatic revisions, hash IDs for new objects, `itt log`, `show`, `diff` and `itt migrate`.
2. Branches and worktrees: `itt branch`, `itt switch` and Git-worktree discovery.
3. Semantic merge with structured conflicts and duplicate-goal hints.
4. Remote protocol 3: `fetch`, `pull` = fetch + merge, `push`, `clone`. IntHub stores the revision DAG and shows `main` with its merge history.

Each phase ships with migration and compatibility tests and with Skill and hook guidance for what it adds. Phases 1 to 3 are local-only and can be released before the server changes. Intent relations ship separately in 7.2, and the migration carries them over.
