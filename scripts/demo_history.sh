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

printf '\n== Setup ==\n'
"${CLI}" init
"${CLI}" start "Reduce onboarding confusion"

printf '\n== Record work ==\n'
printf 'hero = "candidate-a"\n' > landing.txt
git add landing.txt
git commit -m "landing candidate A" >/dev/null
"${CLI}" snap "Landing page candidate A" -m "First approach"

printf 'hero = "candidate-b"\n' > landing.txt
git add landing.txt
git commit -m "landing candidate B" >/dev/null
"${CLI}" snap "Landing page candidate B" -m "Progressive disclosure is better"

printf '\n== Inspect ==\n'
"${CLI}" inspect

printf '\n== Done ==\n'
"${CLI}" done

printf '\nDemo complete\n'
