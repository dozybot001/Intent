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

printf '\n== Candidate A ==\n'
printf 'hero = "candidate-a"\n' > landing.txt
"${CLI}" snap "Landing page candidate A"
git add landing.txt
git commit -m "landing candidate A" >/dev/null

printf '\n== Candidate B ==\n'
printf 'hero = "candidate-b"\n' > landing.txt
"${CLI}" snap "Landing page candidate B"
git add landing.txt
git commit -m "landing candidate B" >/dev/null

printf '\n== Adopt ==\n'
"${CLI}" adopt --checkpoint cp-002 -m "Adopt progressive disclosure layout"

printf '\n== git log --oneline ==\n'
git log --oneline

printf '\n== itt log ==\n'
"${CLI}" log

printf '\nDemo complete\n'
