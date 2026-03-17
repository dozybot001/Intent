#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
BUILD_VENV="$(mktemp -d)"
INSTALL_VENV="$(mktemp -d)"
BUILD_OUT="$(mktemp -d)"

cleanup() {
  rm -rf "${BUILD_VENV}"
  rm -rf "${INSTALL_VENV}"
  rm -rf "${BUILD_OUT}"
}

trap cleanup EXIT

cd "${ROOT}"

printf '\n== unit tests ==\n'
"${PYTHON}" -m unittest discover -s tests -v

printf '\n== smoke ==\n'
"${ROOT}/scripts/smoke.sh"

printf '\n== history demo ==\n'
"${ROOT}/scripts/demo_history.sh" >/dev/null
printf 'History demo passed\n'

printf '\n== agent demo ==\n'
"${ROOT}/scripts/demo_agent.sh" >/dev/null
printf 'Agent demo passed\n'

printf '\n== build ==\n'
"${PYTHON}" -m venv "${BUILD_VENV}"
"${BUILD_VENV}/bin/python" -m pip install --upgrade pip build >/dev/null
"${BUILD_VENV}/bin/python" -m build --outdir "${BUILD_OUT}" >/dev/null
printf 'Build passed\n'

printf '\n== install from wheel ==\n'
"${PYTHON}" -m venv "${INSTALL_VENV}"
"${INSTALL_VENV}/bin/python" -m pip install --upgrade pip >/dev/null
"${INSTALL_VENV}/bin/python" -m pip install "${BUILD_OUT}"/intent_cli-*.whl >/dev/null
"${INSTALL_VENV}/bin/itt" version >/dev/null
"${INSTALL_VENV}/bin/itt" --help >/dev/null
printf 'Wheel install passed\n'

printf '\nAll checks passed\n'
