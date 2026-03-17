# Setup Assets

This directory is the single source of truth for end-user installation assets.

It contains:

- the bootstrap script used from the GitHub homepage
- the integration manifest used by `itt integrations list`
- agent-specific skill or helper files used by `itt setup`

The bootstrap installer keeps a local repository checkout at `~/.intent/repo`.
It exposes the repo-backed `itt` command at `~/.intent/bin/itt` and reads
`~/.intent/repo/setup/` directly, so there is no second copied `setup/` tree
under `~/.intent` and no separate end-user CLI package install.

Runtime-generated outputs still live outside the repository checkout:

- receipts under `~/.intent/receipts/`
- manual helper files under `~/.intent/generated/`
