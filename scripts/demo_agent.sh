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
  local inspect_payload args_json
  inspect_payload="$("${CLI}" inspect --json)"

  printf '\n== inspect ==\n'
  printf '%s\n' "${inspect_payload}"

  args_json="$(printf '%s' "${inspect_payload}" | python3 -c 'import json,sys; payload=json.load(sys.stdin); actions=payload.get("suggested_next_actions", []); print(json.dumps(actions[0]["args"] if actions else []))')"

  if [[ "${args_json}" == "[]" ]]; then
    printf '\nNo suggested next action\n'
    return 1
  fi

  printf '\n== next action ==\n'
  python3 - "$CLI" "${args_json}" <<'PY'
import json
import shlex
import subprocess
import sys

cli = sys.argv[1]
args = json.loads(sys.argv[2])
print(shlex.join([cli, *args]))
subprocess.run([cli, *args], check=True)
PY
}

cd "${TMPDIR}"

git init >/dev/null
git config user.email intent@example.com
git config user.name Intent

printf 'seed\n' > README.md
git add README.md
git commit -m "seed" >/dev/null

"${CLI}" init >/dev/null

printf '\n== Step 1 ==\n'
run_next_action

printf 'hero = "candidate"\n' > candidate.txt

printf '\n== Step 2 ==\n'
run_next_action

printf '\n== Step 3 ==\n'
run_next_action

printf '\n== final inspect ==\n'
"${CLI}" inspect --json

printf '\nAgent demo complete\n'
