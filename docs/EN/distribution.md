English | [简体中文](../CN/distribution.md)

# Distribution and Integration Design

Purpose: define how Intent CLI and agent-platform integrations should be distributed so the default user journey feels like one install flow instead of multiple manual steps.

## What This Document Answers

- how to separate the internal CLI layer from platform-specific integrations without exposing that split to end users
- what the primary install journey should look like
- how registries such as skill catalogs fit into distribution
- what release artifacts should exist for CLI and integrations

## What This Document Does Not Answer

- exact installer implementation details
- per-platform API quirks or UI behavior
- the canonical CLI contract or JSON schema

## Boundary with Other Documents

- the project rationale and the long-term relationship among Intent CLI, skills, and IntHub are defined in [Vision and problem definition](vision.md)
- the stable CLI behavior and machine contract are defined in [Unified CLI spec](cli.md)
- release-readiness checks for the current CLI stage are defined in [Release baseline](release.md)
- sequencing and prioritization after `v0.1.0` are defined in [Roadmap](roadmap.md)

## 1. Product Framing

There are two different audiences here:

- Intent CLI developers and maintainers
- Intent users who want their agent environment to understand and operate `itt`

Internally, Intent can still keep separate layers:

- a local CLI runtime
- shared integration guidance
- platform-specific adapters or skills

But the default public experience should not require users to understand that packaging split before first use.

## 2. Primary User Journey

The GitHub project homepage should expose two different command paths for two different audiences:

- a contributor command such as `git clone ...` for developers, maintainers, and contributors
- a user command for people who just want Intent installed and connected to their existing agent setup

For example, the homepage may show:

```bash
git clone https://github.com/dozybot001/Intent.git
```

and:

```bash
curl -fsSL https://raw.githubusercontent.com/dozybot001/Intent/main/setup/install.sh | bash
```

The key rule is not "never fetch files from GitHub." The key rule is that end users should not have to manually clone the repository, enter the repo, and understand its internal layout just to get started. The bootstrap may fetch whatever assets it needs behind the scenes.

The target user journey should be:

1. the user sees the user command on the GitHub homepage
2. the user runs it directly in a local terminal
3. the installer creates or refreshes a stable local repository checkout such as `~/.intent/repo`
4. the installer exposes the `itt` command from that checkout, for example through `~/.intent/bin/itt`, and adds that directory to PATH when it can
5. the installer auto-detects supported agent platforms already present on the machine
6. if a supported platform is detected, the matching skill or adapter is installed into the directory that platform actually reads, or is registered through that platform's supported mechanism
7. if no supported agent platform is detected, the installer should still make that repo-backed `itt` usable and then clearly explain that the user can run `itt setup <agent>` later
8. after a successful detected-platform install, the matching agent should immediately have a usable Intent skill instead of merely leaving a bundle inside an Intent-owned directory for the user to handle manually

`itt setup --agent auto` still matters as part of the CLI command surface, but it should complement the homepage user command rather than replace it.

One more constraint is important here: `itt` should not come from a second separately installed standalone CLI copy. It should come directly from the fixed local checkout.

## 3. Internal Layering

The current path model should stay concrete and small:

- fixed local checkout: `~/.intent/repo`
- command launcher: `~/.intent/bin/itt`
- installer assets: `~/.intent/repo/setup/`
- canonical skill bundle: `~/.intent/repo/skills/intent-cli/`
- runtime receipts and generated helpers: `~/.intent/receipts/` and `~/.intent/generated/`

Anything outside those paths should be treated as contributor tooling, not part of the end-user install story.

## 4. Hard Boundaries

To keep future implementation work aligned, these boundaries should stay explicit:

- no second copied `setup/` tree under `~/.intent`
- no second standalone CLI install for end users
- no alternate runtime source of installer assets or canonical skill content beyond the fixed local checkout
- contributor flows such as `pip install -e .` may continue to exist, but they should stay framed as contributor-only paths

The GitHub homepage and docs should keep pointing to the bootstrap flow first.

## 5. Command Model

The user-facing command surface should stay small:

```bash
itt setup --agent auto
itt setup codex
itt setup claude
itt setup cursor
itt doctor
itt integrations list
```

These commands should hide platform-specific filesystem paths, adapter layouts, and registration details.

## 6. Repository Layout

The repository source of truth can stay small, but it should still distinguish
between the canonical reusable skill bundle and the installer-specific assets:

```text
skills/
  intent-cli/
    SKILL.md
    agents/
    references/

setup/
  install.sh
  manifest.json
  cursor/
```

`skills/intent-cli/` is the canonical shipped Intent skill bundle. It should be
versioned in GitHub, visible to contributors, and used as the source for
platforms that can install a file-based global skill directory.

`setup/` keeps only the bootstrap entry point, integration manifest, and
platform-specific helper assets. Codex and Claude should install from the
shared repo skill bundle instead of maintaining duplicated skill copies under
`setup/`.

The fixed checkout still contains the `itt` entrypoint and CLI code itself. The
user should experience one local repo, not one repo plus a separate user-facing
CLI install.

## 7. Release Artifacts

At the current stage, release outputs only need to preserve the same user journey:

1. a stable repository snapshot or release archive that contains `itt`, `src/`, `skills/`, and `setup/`
2. a stable bootstrap script
3. a machine-readable integration manifest
4. the platform setup assets inside `setup/`

No extra distribution channel should become the primary story before this fixed-checkout model is stable.

## 8. Platform Setup Behavior

`itt setup <agent>` should follow the same high-level contract on every platform:

- check that the fixed local checkout and repo-backed `itt` are available
- install, link, or register the correct skill or adapter into the place that platform actually reads
- write any needed local configuration
- run a lightweight verification step

If a platform does not expose a stable global file-based install location, `itt setup <agent>` should honestly fall back to generating a helper asset and telling the user what manual step remains.

The platform-specific details can vary, but the user-facing semantics should stay aligned.

## 9. Design Principles

- do not require users to manually clone the Intent repository just to enable integrations, even if the bootstrap clones it into a fixed location behind the scenes
- the GitHub homepage should clearly distinguish the contributor command from the direct user command
- do not make a third-party registry the only supported install path
- do not couple the CLI release story to a single agent vendor
- do not force users to learn the difference between skills, adapters, and local binaries before they can start

## 10. Current Conclusion

Intent should keep its internal layers separate, but the public-facing journey should converge on a clearer shape:

- the GitHub homepage shows a clone command for contributors
- the GitHub homepage shows a direct user command for end users
- the user command clones a fixed local repo and exposes the repo-backed `itt` command from that checkout
- the user command wires up the matching agent skill in the same flow when possible
- if no supported agent is present yet, that repo-backed `itt` still becomes usable immediately and the follow-up `itt setup <agent>` path is made explicit

The current repository-backed bootstrap can fetch or copy that fixed local repo as needed, but the user story should still feel like "run one command, get the repo-backed `itt`, and wire the agent when possible."
