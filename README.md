English | [简体中文](README.CN.md)

# Intent

> Git records code changes. Intent records what you did and why.

Intent is a semantic history layer built on top of Git for agent-driven development. It tracks:

- what problem is being worked on
- what steps were taken
- what was the rationale behind key choices

Intent does not replace Git. It adds the layer Git was never designed to carry.

## Understand It in 30 Seconds

In agent-driven development, code is produced quickly, but the reasoning behind it is often scattered across conversations, issues, and drafts.

Git answers "how did the code change?" but not "what was the intent, and why was this path chosen?"

Intent fills that gap by promoting higher-level semantics into first-class objects that agents can read and act on.

## Core Loop

```
start → snap → done
```

- `start`: begin work on a problem
- `snap`: record a step with optional rationale
- `done`: close the intent when work is complete

## Object Model

Intent has two object types:

| Object | States | Purpose |
| --- | --- | --- |
| Intent | `open` → `done` | the problem or goal being worked on |
| Checkpoint | `adopted`, `candidate`, `reverted` | a recorded step — the unit of semantic history |

By default, `snap` creates an adopted checkpoint. Use `--candidate` when genuinely comparing alternatives.

## Minimal Example

```bash
itt init
itt start "Reduce onboarding confusion"
itt snap "Simplify landing page" -m "Progressive disclosure approach"
git add . && git commit -m "refine onboarding layout"
itt done
```

All commands output JSON. Intent is designed for agent consumption.

## Why Not Just Use Issues, ADRs, or Commit Messages

| Approach | Good At | Limitation |
| --- | --- | --- |
| commit messages | explaining individual code changes | does not answer "what is the current goal?" or "what steps led here?" |
| issues / PRs | holding discussion and context | context fragments; no stable object boundary for agents |
| ADRs / docs | preserving long-term decisions | too heavy for high-frequency step recording |
| Intent | tracking semantic steps and rationale | currently focused on the local CLI loop |

## Install

For contributors:

```bash
git clone https://github.com/dozybot001/Intent.git
cd Intent
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
```

For end users:

```bash
curl -fsSL https://raw.githubusercontent.com/dozybot001/Intent/main/setup/install.sh | bash
```

The bootstrap keeps a local checkout at `~/.intent/repo`, exposes `itt` at `~/.intent/bin/itt`, and runs `itt setup` for the detected agent.

## Commands

| Command | Purpose |
| --- | --- |
| `itt init` | Initialize Intent in a Git repository |
| `itt start <title>` | Create and activate an intent |
| `itt snap <title> [-m rationale]` | Record a checkpoint (adopted by default) |
| `itt snap <title> --candidate` | Record as candidate for comparison |
| `itt adopt [checkpoint_id]` | Adopt a candidate checkpoint |
| `itt revert` | Revert the latest adopted checkpoint |
| `itt done [intent_id]` | Close the active intent |
| `itt inspect` | Machine-readable workspace snapshot (JSON) |
| `itt list <intent\|checkpoint>` | List objects |
| `itt show <id>` | Show a single object by ID |
| `itt setup [agent]` | Install agent integration |
| `itt doctor` | Verify agent setup health |

## Agent Protocol

Intent is designed primarily for agents. An agent should:

- run `itt inspect` before substantive work to understand current state
- start an intent when beginning meaningful work
- use `itt snap` to record steps with rationale
- run `itt done` when work is complete
- skip recording for trivial questions or tiny edits

## Validation

```bash
./scripts/check.sh
```

Or run steps separately:

```bash
python3 -m unittest discover -s tests -v
./scripts/smoke.sh
./scripts/demo_agent.sh
```

## What Intent Is Not

- not a replacement for Git
- not a replacement for issues, PRs, or documentation systems
- not a "record everything" archive

Intent only tracks semantic steps worth recording, along with their rationale.

## Repository Layout

```text
Intent/
|-- README.md
|-- README.CN.md
|-- skills/
|   `-- intent-cli/
|-- setup/
|-- src/
|   `-- intent_cli/
|-- docs/
|-- scripts/
|-- tests/
`-- .intent/
```

## Documentation

- [Changelog](CHANGELOG.md)
- [Documentation index](docs/EN/README.md)
- [Glossary](docs/EN/glossary.md)
- [Vision and problem definition](docs/EN/vision.md)
- [CLI spec](docs/EN/cli.md)
- [Distribution and integration design](docs/EN/distribution.md)
- [First agent feedback transcript](docs/EN/feedback.md)
- [Demo](docs/EN/demo.md)
- [Release baseline](docs/EN/release.md)
- [Strategy](docs/EN/strategy.md)
- [Roadmap](docs/EN/roadmap.md)
- [Documentation i18n guide](docs/EN/i18n.md)
