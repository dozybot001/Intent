# IntHub MVP Design Doc

[中文](../CN/inthub-mvp.md) | English

## What this document answers

- What IntHub should do in its first phase
- How it should divide responsibility with the local Intent CLI
- Which capabilities belong in scope first, and which explicitly do not
- What the minimum information architecture and sync model should be when implementation starts

## Relationship to other documents

- For vision and layer boundaries, see [vision](vision.md)
- For phase ordering, see [roadmap](roadmap.md)
- For the local object model and behavior contract, see the [CLI design doc](cli.md)
- For the first sync and interface contract, see the [IntHub Sync Contract (V1)](inthub-sync-contract.md)
- This document defines only the first collaboration-layer MVP for IntHub

## 1. Product positioning

IntHub is not a new semantic layer, and it is not a heavyweight project-management platform.

Its role is:

**a remote collaboration layer built on top of Intent.**

In one sentence:

**Local `itt` writes semantics. IntHub shares semantics.**

So the most important first capability is not "editing objects online." It is:

- letting humans and agents see the same current semantic state
- making handoff, continuation, review, and retrospective work without ad-hoc re-explanation
- giving `intent / snap / decision` remote visibility, searchability, and shareability for the first time

## 2. First-phase design principles

- **local-write first**: the local CLI remains the main write path
- **remote-read first**: IntHub solves shared inspect, display, search, and handoff first
- **reuse the local model**: do not reinvent the object model or add a fourth core object
- **sync current semantics, not everything**: sync structured semantic objects, not full raw chats and every intermediate log
- **low-friction by default**: the collaboration layer must not turn the local workflow into process overhead
- **semantic data stays out of Git**: `.intent/` is local semantic-workspace metadata and should not be committed to Git or treated as GitHub-hosted source of truth

For the first practical delivery shape, add one more principle:

- **local-instance first for adoption**: before the hosted remote shape is mature, the first user-facing IntHub experience should converge on a distributable local instance (IntHub Local) so users can inspect their own project's semantic history in a local browser first

## 3. Current non-goals

Not prioritized for the first IntHub release:

- direct remote editing of `intent / snap / decision`
- complete raw conversation archival
- a general task system, issue system, or PM platform
- real-time comment streams, approval flows, and heavy notification systems
- over-designed conflict handling for concurrent multi-writer editing
- a pure web object system detached from Git and local workspace context

## 4. MVP scope

### 4.0 First distributable form: IntHub Local

To make IntHub usable early, the MVP should not require ordinary users to deploy a remote service first.

A better first step is a **distributable local IntHub instance (IntHub Local)**:

- distributed through **GitHub Release assets**
- starts an IntHub backend instance on the user's machine
- binds by default to `127.0.0.1:7210` only
- serves the Web shell and API together by default
- lets the user run `itt hub login / link / sync` inside their own repo
- then inspect the synced `intent / snap / decision` history in a local browser

Why this is the right first product shape:

- it does not require ordinary users to understand hosting, domains, or cloud deployment first
- it preserves the boundary that PyPI distributes only the CLI
- it keeps the product experience aligned with the future hosted IntHub shape; only the deployment location differs

The boundary should be explicit: `IntHub Local` is a **separate deliverable**, not an implicit part of the CLI PyPI package.

### 4.1 Must-have user-facing capabilities

#### Project overview

Provide a one-screen current-state view containing at least:

- active intents
- active decisions
- recent snaps
- associated repos / workspaces
- last sync status for each workspace

#### Handoff view

This is the remote version of `itt inspect`. It should answer:

- what goals are still in progress
- what happened most recently
- which long-term decisions are still active
- where a new agent should look first

#### Intent detail page

At minimum show:

- title / status / rationale
- source query
- attached decisions
- snap timeline
- latest snap summary
- associated repo / branch / commit context

#### Decision detail page

At minimum show:

- title / rationale / status
- intents still constrained by it
- historically linked intents
- when it became deprecated

#### Search

The first search surface only needs high-signal fields:

- object title
- source query / snap query
- summary
- rationale

No complex syntax is required at first, and full chat search is out of scope.

### 4.2 Core scenarios

The first IntHub release should make at least these scenarios work:

1. A new agent can open the project and continue without the user re-explaining context.
2. A reviewer can quickly understand why work is moving along the current path, not just what code changed.
3. Across repeated sessions on the same repo, the user can see real recent progress instead of scattered chat history.

### 4.3 Official showcase project

The first IntHub release should include at least one official showcase project that demonstrates what this collaboration layer looks like in real work.

The preferred first sample should be **Intent's own semantic history**, because:

- it is real continuously produced data, not synthetic demo fixtures
- it naturally covers the core value IntHub wants to prove: cross-agent handoff, feedback consumption, decision constraints, and error correction
- project maintainers understand the context best, so the showcase can be kept accurate over time

This showcase should not be treated as a one-off static story page. It should be a continuously updated live showcase. The product should expose two entry modes:

- **showcase / case-study entry**: helps a first-time viewer quickly understand how the system is used in practice
- **raw object entry**: lets the viewer drill into the actual intent / snap / decision views rather than stopping at the curated narrative

In other words, case-study storytelling may exist, but it must not replace the raw object views. Both should coexist.

## 5. Minimum information architecture

The first release should introduce only the collaboration-layer containers it actually needs:

| Layer | Role |
| --- | --- |
| `project` | top-level collaboration scope |
| `repo` | one Git repository |
| `workspace` | one local checkout / agent working copy |
| `sync batch` | one synchronization record from local to IntHub |

Below those layers, the remote system should still carry the same three semantic object types:

- intent
- snap
- decision

Do not introduce a new general-purpose core object in the MVP.

## 6. Sync model

The recommended first model is:

**batch append-only + object snapshot view**

Meaning:

- each sync creates a new `sync batch`
- each batch includes current workspace Git and schema context
- each batch uploads current object snapshots rather than having the server reinterpret semantics
- the server presents the latest object state as a derived view

Why this is the right first step:

- easier to ship than full event sourcing
- preserves synchronization boundaries better than a plain final-state upsert
- stays aligned with the local append-only and mostly immutable object model

Each sync batch should include at least:

- `project`
- `repo`
- `workspace`
- `schema_version`
- `branch`
- `head_commit`
- `dirty`
- `synced_at`
- the currently visible intent / snap / decision snapshots

## 7. ID and origin design

Local object IDs such as `intent-001` are meaningful only within one workspace. They must not be treated as global remote primary keys.

The MVP should therefore distinguish two identifiers:

- **local display ID**: for example `intent-001`, preserved for humans and the local CLI
- **remote global ID**: assigned by IntHub for storage, indexing, and API references

Remote objects should also preserve origin metadata:

- origin workspace
- local object id
- object type
- created_at

That gives us both:

- continuity with the local readable model
- no cross-repo or cross-workspace ID collisions remotely

## 8. Git context requirements

IntHub does not replace Git, but the first release must display semantic objects alongside Git context.

Each sync should at minimum carry:

- repo
- branch
- HEAD commit
- dirty state

Without this, IntHub degrades into a remote note wall rather than a collaboration layer.

The boundary should stay explicit:

- Git / GitHub provide repo identity, permissions, and code context
- IntHub provides semantic-object sync, storage, indexing, and display
- `.intent/` should not be committed to the repository or consumed as part of GitHub content

This keeps semantic history from being pulled back into branch, merge, rebase, and PR noise.

## 9. First API / sync entrypoint suggestions

The first API surface does not need to be broad, but it should at least support:

- submitting a sync batch
- fetching project overview
- fetching intent detail
- fetching decision detail
- searching objects

The CLI side does not need many new commands at first, but it should reserve one clear entrypoint, such as:

```bash
itt hub sync
```

Its job should stay narrow:

- read local `.intent/`
- enrich with Git context
- push to IntHub

Do not overload the CLI with remote editing, comments, or approvals in the first phase.

## 10. Suggested implementation order

### Phase A: Sync contract

- define the sync batch payload
- define the minimum remote schema for project / repo / workspace / object
- make idempotent sync work first

### Phase B: Read-only web overview

- project home
- handoff / inspect view
- intent / decision detail pages

### Phase C: Search and retrospective

- search over title / query / summary / rationale
- recent activity / timeline view

### Phase D: Decide later whether to expand write capability

Only after the previous phases are validated in real use should we consider:

- richer review surfaces
- remote write paths
- more complex collaboration flows

## 11. How to judge whether the IntHub MVP works

The test is not how many pages exist. It is whether these questions become materially easier:

- Can a new agent take over current work more easily
- Can the user understand why work is proceeding this way more easily
- Do review and handoff depend less on chat-memory reconstruction
- Does the added complexity produce real collaboration value

If not, then IntHub is still just a web mirror of local objects, not yet a real collaboration layer.
