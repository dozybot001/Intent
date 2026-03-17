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
"${CLI}" snap "Landing page candidate A" --candidate >/dev/null
"${CLI}" snap "Landing page candidate B" --candidate >/dev/null
"${CLI}" adopt cp-002 -m "B is cleaner" >/dev/null
"${CLI}" snap "Final polish" -m "Progressive disclosure approach" >/dev/null
"${CLI}" inspect >/dev/null
"${CLI}" list intent >/dev/null
"${CLI}" list checkpoint >/dev/null
"${CLI}" show cp-001 >/dev/null
"${CLI}" revert -m "Revert final polish" >/dev/null
"${CLI}" done >/dev/null
"${CLI}" version >/dev/null

echo "Smoke test passed"
