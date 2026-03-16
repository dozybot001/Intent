#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
BUILD_VENV="$(mktemp -d)"

cleanup() {
  rm -rf "${BUILD_VENV}"
}

trap cleanup EXIT

cd "${ROOT}"

printf '\n== unit tests ==\n'
"${PYTHON}" -m unittest discover -s tests -v

printf '\n== smoke ==\n'
"${ROOT}/scripts/smoke.sh"

printf '\n== human demo ==\n'
"${ROOT}/scripts/demo_log.sh" >/dev/null
printf 'Human demo passed\n'

printf '\n== agent demo ==\n'
"${ROOT}/scripts/demo_agent.sh" >/dev/null
printf 'Agent demo passed\n'

printf '\n== build ==\n'
"${PYTHON}" -m venv "${BUILD_VENV}"
"${BUILD_VENV}/bin/python" -m pip install --upgrade pip build >/dev/null
"${BUILD_VENV}/bin/python" -m build >/dev/null
printf 'Build passed\n'

printf '\nAll checks passed\n'
