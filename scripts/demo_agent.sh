#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLI="${ROOT}/itt"
TMPDIR="$(mktemp -d)"

cleanup() {
  rm -rf "${TMPDIR}"
}

trap cleanup EXIT

run_next_action() {
  local inspect_payload action_cmd
  inspect_payload="$("${CLI}" inspect)"

  printf '\n== inspect ==\n'
  printf '%s\n' "${inspect_payload}"

  action_cmd="$(printf '%s' "${inspect_payload}" | python3 -c 'import json,sys; d=json.load(sys.stdin); a=d.get("suggested_next_action"); print(a["command"] if a else "")')"

  if [[ -z "${action_cmd}" ]]; then
    printf '\nNo suggested next action\n'
    return 1
  fi

  printf '\n== next action: %s ==\n' "${action_cmd}"
  eval "${CLI} ${action_cmd#itt }"
}

cd "${TMPDIR}"

git init >/dev/null
git config user.email intent@example.com
git config user.name Intent

printf 'seed\n' > README.md
git add README.md
git commit -m "seed" >/dev/null

"${CLI}" init >/dev/null

printf '\n== Step 1: follow suggestion ==\n'
run_next_action

printf 'hero = "candidate"\n' > candidate.txt

printf '\n== Step 2: follow suggestion ==\n'
run_next_action

printf '\n== Step 3: close ==\n'
"${CLI}" done

printf '\n== final inspect ==\n'
"${CLI}" inspect

printf '\nAgent demo complete\n'
