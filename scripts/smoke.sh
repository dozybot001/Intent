#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="${ROOT}/itt"
TMPDIR="$(mktemp -d)"

cleanup() {
  rm -rf "${TMPDIR}"
}

trap cleanup EXIT

cd "${TMPDIR}"

git init >/dev/null
git config user.email intent@example.com
git config user.name Intent

printf 'seed\n' > README.md
git add README.md
git commit -m "seed" >/dev/null

"${CLI}" init >/dev/null
"${CLI}" start "Reduce onboarding confusion" >/dev/null
"${CLI}" run start --title "Smoke run" >/dev/null
"${CLI}" run list --json >/dev/null
"${CLI}" run show @active --json >/dev/null
"${CLI}" snap "Landing page candidate B" >/dev/null
"${CLI}" status >/dev/null
"${CLI}" status --json >/dev/null
"${CLI}" intent list --json >/dev/null
"${CLI}" checkpoint list --json >/dev/null
"${CLI}" config show --json >/dev/null
"${CLI}" adopt -m "Adopt progressive disclosure layout" >/dev/null
"${CLI}" decide "Prefer progressive disclosure" --because "Lower cognitive load for first-time users." >/dev/null
"${CLI}" inspect --json >/dev/null
"${CLI}" adoption list --json >/dev/null
"${CLI}" decision list --json >/dev/null
"${CLI}" decision show @latest --json >/dev/null
"${CLI}" log >/dev/null
"${CLI}" revert -m "Revert progressive disclosure layout" >/dev/null
"${CLI}" run end --json >/dev/null
"${CLI}" run show run-001 --json >/dev/null
"${CLI}" adoption show adopt-002 --json >/dev/null

echo "Smoke test passed"
