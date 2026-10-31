# Intent

[中文](https://github.com/dozybot001/Intent/blob/main/README_CN.md) | English

[![tests](https://github.com/dozybot001/Intent/actions/workflows/test.yml/badge.svg)](https://github.com/dozybot001/Intent/actions/workflows/test.yml)
[![PyPI](https://img.shields.io/pypi/v/intent-history)](https://pypi.org/project/intent-history/)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![status: beta](https://img.shields.io/badge/status-beta-orange)
![license: MIT](https://img.shields.io/badge/license-MIT-green)

**Your coding agent forgets where you left off. Intent keeps the goal, the latest verified checkpoint and the standing decisions in your project, so the next session continues the work instead of rediscovering it.**

Git records how code changed. Intent records why, what is verified, and what comes next.

![Monday's session records a checkpoint. On Tuesday a new session is told to resume through Intent and picks up the goal, the verified state, the rule and the next step.](https://raw.githubusercontent.com/dozybot001/Intent/main/docs/assets/resume-demo.gif)

**See it on a real project:** [browse Intent's own history on IntHub](https://inthub.tenon.asia/showcase). It holds the goals, checkpoints and decisions behind this repository, and it needs no sign-in.

## The idea

You now shape code through agents. The code lands in Git, but the reasoning stays in a chat that ends with the session, so the next agent starts blind and you explain everything again.

Intent adds a small layer of semantic history next to your code, built around one deliberate imbalance:

- **Recording stays light.** The agent saves a checkpoint only when something meaningful is verified. A quiet turn writes nothing.
- **Resuming is complete.** One command gives the next session the goal, what is verified, the boundary, the next step and the rules that still apply.

The history is plain JSON in `.intent/`, so any agent can read it, and so can you. Nothing leaves your machine unless you choose to share it.

## Quick start

```bash
# 1. Install the CLI (macOS / Linux). Re-run any time to upgrade.
curl -fsSL https://raw.githubusercontent.com/dozybot001/Intent/main/scripts/install.sh | bash

# 2. Add the agent skill (needs Node.js; -a cursor and others also work)
npx skills add dozybot001/Intent -g -a claude-code -a codex -y

# 3. Turn it on in a project (Git is optional)
cd your-project
itt init
```

Trust the project hooks once: in Claude Code, trust the folder and confirm both hooks in `/hooks`; in Codex, open `/hooks`. Then work as usual. To pick up later, in any session, say:

> Resume this project through Intent.

Windows (PowerShell): `irm https://raw.githubusercontent.com/dozybot001/Intent/main/scripts/install.ps1 | iex`.
With pipx or uv: `pipx install intent-history` or `uv tool install intent-history`. Requires Python 3.9+.

The names, in one line: Intent is the project, `itt` is the command, `intent-history` is the package, and IntHub is the optional web app.

## Try it by hand

```bash
itt init
itt intent create "Add Apple Pay to the web checkout" --why "Apple Pay users convert 2x on mobile Safari"
itt snap create "Payment sheet confirms PaymentIntents in test mode" \
  --next "Handle shipping-method changes server-side" --blocker none
itt decision create "Payments go through the PaymentIntent API only" --why "One SCA path"
itt inspect
```

```text
Active
  intent-3f9a2c1  Add Apple Pay to the web checkout
                  Next         Handle shipping-method changes server-side
                  Blocker      none
                  Verified     Payment sheet confirms PaymentIntents in test mode
                  snap-8e41d07 · 2026-10-30 00:25 · 1 snap

Decisions
  decision-c27b5fa  Payments go through the PaymentIntent API only
```

This is what a new session reads. In a terminal `itt` prints text; agents and scripts get JSON.

## Why not just AGENTS.md or agent memory?

| You may already use | It holds | Intent adds |
|---|---|---|
| `AGENTS.md`, `CLAUDE.md`, Cursor rules | How to work in this repository | Where the work stands: current goal, verified state, next step, blocker |
| Built-in agent memory | Per-tool, opaque notes | Plain JSON in your project that any agent (and you) can read |
| Issues, PRs, ADRs | Team plans and reviews | Checkpoints captured during the work, plus decisions that attach to new goals automatically |
| Git history | What changed in the code | The reasoning, and the boundary of what is actually done |

## What it records

Three kinds of objects, all append-only:

| Object | Captures |
|---|---|
| **Intent** | One goal and why it matters |
| **Snap** | A verified checkpoint: what is verified, the boundary, the next step, any blocker |
| **Decision** | A durable rule that binds future goals, such as "payments go through PaymentIntents only" |

Intents can be related: part of, derived from, succeeds, depends on, conflicts with. IntHub's Flow page draws how goals branch, continue and converge ([Intent flow](https://github.com/dozybot001/Intent/blob/main/docs/EN/intent-flow.md)).

## History that works like Git

If you know Git, you already know how Intent behaves. Every write is a revision, so there is nothing to commit.

```bash
itt log --graph               # revisions, branches and merges
itt diff HEAD~3               # what changed, in goals and checkpoints rather than lines
itt switch -c experiment      # branch the history, as you would in Git
itt merge experiment          # merge back; only a real disagreement stops it
```

Agents in separate Git worktrees share one history, each on its own branch, and new IDs cannot collide. A merge combines their checkpoints by itself and stops only when two sides set the same field differently, for example one marked a goal done and the other cancelled it. See the [design](https://github.com/dozybot001/Intent/blob/main/docs/EN/semantic-git.md).

## Works with

| Host | Support |
|---|---|
| **Claude Code** | Skill (or plugin: `/plugin marketplace add dozybot001/Intent`, then `/plugin install intent-cli@intent`) plus project hooks: `itt init --host claude-code`. See [setup and limits](https://github.com/dozybot001/Intent/blob/main/references/claude-code-hooks.md). |
| **Codex** | Skill plus project hooks: `itt init --host codex`. See [setup and limits](https://github.com/dozybot001/Intent/blob/main/references/codex-hooks.md). |
| **Cursor and other agents** | Skill instructions only, best effort |

Hooks open each turn with the current state and check at the end that the turn was closed. They are written to project-local files and never enable other projects. `itt maintenance off` turns recording off for one project.

## What stays on your machine

- `.intent/` holds plain JSON. `itt init` excludes it from Git in this clone only, because it may contain internal reasoning. Commit it deliberately if your team wants it in Git.
- Each hooked turn adds a compact opening context with a hard size cap, and one `itt maintenance close` call.
- `itt` touches the network only when you run `push`, `pull`, `fetch`, `clone` or `auth`, or `status` with a remote set.

## Share with IntHub (optional)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/dozybot001/Intent/main/docs/assets/inthub-flow-dark.png">
  <img alt="IntHub's Flow page: goals as cards, with their parts, derivations and decisions" src="https://raw.githubusercontent.com/dozybot001/Intent/main/docs/assets/inthub-flow-light.png">
</picture>

- **Locally:** `itt hub start`, then `itt remote add origin http://127.0.0.1:7210 --project NAME` and `itt push`. Another folder joins with `itt clone NAME --api-base-url http://127.0.0.1:7210`.
- **Hosted:** [inthub.tenon.asia](https://inthub.tenon.asia), operated by 榫卯 Tenon AI. Run `itt auth login`, approve the code in the browser, then `itt push`. Each account and team can keep 100 projects and 1 GB of history. Projects are private by default, can be shared with a team (`--project TEAM/NAME`), and can be made public in their settings. See [teams and sharing](https://github.com/dozybot001/Intent/blob/main/docs/EN/inthub-collaboration.md) and the [privacy notice](https://inthub.tenon.asia/privacy).
- **Restore elsewhere:** `itt clone NAME` in the project folder. Only members can clone.

`itt push` sends the current branch and `itt pull` fetches and merges, as in Git. If two copies record in parallel, `itt status` reports `diverged`, and `itt pull` merges them, stopping only where both set the same field differently.

## Status

Intent is **beta** (8.x). Coming from Intent 7? Run `itt migrate` once in each project: it keeps every ID and backs up first. Within a major version the `.intent/` format and the JSON output stay compatible; breaking changes come with a new major version and a migration. Recording and continuation flows are covered by tests on Python 3.9 to 3.14. Whether Intent measurably reduces re-explaining in real work is still being tested with natural continuation cases.

## FAQ

**Does it replace Git, issues or docs?** No. It records the reasoning and the state of work that those tools don't.

**What if the agent records noise?** Zero writes is a valid outcome. The skill records only verified milestones, never per command or per file. Objects are append-only, so corrections are new Snaps.

**Is `pip install intent-cli` this project?** No, that PyPI name belongs to an unrelated tool. Intent is `intent-history`.

**Windows?** The CLI and installer support Windows. Claude Code hooks need Git Bash.

**How do I remove it?** In each project run `itt maintenance off --remove-hooks`, and `rm -rf .intent` if you also want its history gone. Then run `rm -rf ~/.local/share/intent ~/.local/bin/itt` and `npx skills remove intent-cli -g`. An IntHub token stays valid until it expires; revoke it under Settings.

## Docs

- [Vision](https://github.com/dozybot001/Intent/blob/main/docs/EN/vision.md): why semantic history matters
- [Continuation case](https://github.com/dozybot001/Intent/blob/main/docs/EN/continuation-case.md): from interruption to resumption, step by step
- [CLI reference](https://github.com/dozybot001/Intent/blob/main/docs/EN/cli.md): commands, objects and the JSON contract
- [Intent flow](https://github.com/dozybot001/Intent/blob/main/docs/EN/intent-flow.md): relations between Intents and the Flow page
- [Teams and sharing](https://github.com/dozybot001/Intent/blob/main/docs/EN/inthub-collaboration.md): accounts, visibility and roles on IntHub
- [Semantic Git](https://github.com/dozybot001/Intent/blob/main/docs/EN/semantic-git.md): how revisions, branches and merges work

[Contributing](https://github.com/dozybot001/Intent/blob/main/.github/CONTRIBUTING.md) · [Code of conduct](https://github.com/dozybot001/Intent/blob/main/.github/CODE_OF_CONDUCT.md) · [Security](https://github.com/dozybot001/Intent/blob/main/.github/SECURITY.md) · MIT License
