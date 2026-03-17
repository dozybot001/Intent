# Setup Assets

This directory is the single source of truth for end-user installer assets.

It contains:

- the bootstrap script used from the GitHub homepage
- the integration manifest used by `itt integrations list`
- platform-specific helper files used by `itt setup`

The full reusable Intent skill now lives in `../skills/intent-cli/`.
`setup/manifest.json` points Codex and Claude installs at that canonical
repository skill bundle instead of duplicating separate copies under `setup/`.

The bootstrap installer keeps a local repository checkout at `~/.intent/repo`.
It exposes the repo-backed `itt` command at `~/.intent/bin/itt` and reads
installer files from `~/.intent/repo/setup/` plus the shared skill bundle from
`~/.intent/repo/skills/intent-cli/`, so there is no second copied `setup/`
tree under `~/.intent` and no separate end-user CLI package install.

Runtime-generated outputs still live outside the repository checkout:

- receipts under `~/.intent/receipts/`
- manual helper files under `~/.intent/generated/`
