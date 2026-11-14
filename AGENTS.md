# Intent: notes for coding agents

Intent CLI (`itt`, package `intent-history`) is semantic Git for agent-driven work. IntHub is the hosted service that stores and shows Intent history. Both live in this repository.

## Layout

- `src/intent_cli/`: the CLI. `hub/` talks to IntHub.
- `apps/inthub_api/`: the IntHub server. `apps/inthub_web/`: its web app (plain JS, no build step).
- `SKILL.md`, `SKILL_CN.md`, `references/`, `agents/`, `scripts/itt_argv.py`: the agent Skill shipped with each release.
- `deploy/inthub/`: production release scripts and Caddy and Compose files.
- `docs/EN/`, `docs/CN/`: public docs, kept in both languages. `docs/releases/vX.Y.Z.md`: release notes, one file per version.
- `tests/`: pytest. `tests/web/`: web tests, run with `node tests/web/run.cjs`.
- `dist/`, `build/`: build output, ignored by Git.

## Working here

- Work on `main`. `origin` pushes to Gitee and GitHub at once.
- While developing, run the tests a change affects: `python scripts/changed_tests.py`. Run the full suite once, at release: `python -m pytest -q -n auto --dist loadfile` and `node tests/web/run.cjs`. The PostgreSQL tests need `INTHUB_TEST_POSTGRES_URL` and otherwise only run inside `deploy/inthub/release.sh`.
- Keep source files near 400 lines and split by responsibility.
- The CLI supports Python 3.9 to 3.14 and prints JSON. Within a major version the `.intent/` format and the JSON output stay compatible.
- User-facing text exists in English and Chinese. Change both.
- IntHub's web app uses color only for status, icon plus text for every option, and no browser-styled controls.
- One request per release. A release bumps `scripts/install.sh` and `scripts/install.ps1`, adds `docs/releases/vX.Y.Z.md`, tags `vX.Y.Z`, then runs `bash deploy/inthub/release.sh`. Publishing the GitHub release publishes to PyPI.
- This project records its own history with Intent. Use the `intent-cli` Skill, and do not `itt push`, `pull` or `auth login` unless asked.
