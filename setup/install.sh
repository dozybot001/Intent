#!/usr/bin/env bash
set -euo pipefail

AGENT="auto"
DRY_RUN=0
REPO_URL="${INTENT_REPO_URL:-https://github.com/dozybot001/Intent.git}"
REPO_REF="${INTENT_REPO_REF:-main}"
INTENT_HOME="${INTENT_HOME:-$HOME/.intent}"
REPO_DIR="${INTENT_HOME}/repo"
BIN_DIR="${INTENT_HOME}/bin"
LAUNCHER_PATH="${BIN_DIR}/itt"
LOCAL_REPO=""
PATH_MARKER_BEGIN="# >>> Intent CLI >>>"
PATH_MARKER_END="# <<< Intent CLI <<<"
PATH_UPDATED=0
RC_FILE=""

usage() {
  cat <<'EOF'
Usage: ./setup/install.sh [--agent auto|codex|claude|cursor] [--dry-run]

Clone or refresh the local Intent repository checkout at ~/.intent/repo, expose
the repo-backed `itt` command, and run `itt setup` for the detected or
requested agent.
EOF
}

print_cmd() {
  local rendered=""
  for part in "$@"; do
    rendered+=$(printf '%q ' "${part}")
  done
  printf '  %s\n' "${rendered% }"
}

note() {
  printf '  # %s\n' "$1"
}

detect_rc_file() {
  case "${SHELL:-}" in
    */zsh)
      RC_FILE="${HOME}/.zshrc"
      ;;
    */bash)
      RC_FILE="${HOME}/.bashrc"
      ;;
    *)
      RC_FILE=""
      ;;
  esac
}

path_export_line() {
  printf 'export PATH="%s:$PATH"\n' "${BIN_DIR}"
}

path_is_configured() {
  case ":${PATH}:" in
    *":${BIN_DIR}:"*)
      return 0
      ;;
  esac

  if [[ -n "${RC_FILE}" ]] && [[ -f "${RC_FILE}" ]]; then
    if grep -Fq "${PATH_MARKER_BEGIN}" "${RC_FILE}"; then
      return 0
    fi
    if grep -Fq "${BIN_DIR}" "${RC_FILE}"; then
      return 0
    fi
  fi

  return 1
}

configure_shell_path() {
  if path_is_configured; then
    return 0
  fi

  if [[ -z "${RC_FILE}" ]]; then
    return 0
  fi

  touch "${RC_FILE}"
  {
    printf '\n%s\n' "${PATH_MARKER_BEGIN}"
    path_export_line
    printf '%s\n' "${PATH_MARKER_END}"
  } >>"${RC_FILE}"
  PATH_UPDATED=1
}

require_command() {
  local name="$1"
  if ! command -v "${name}" >/dev/null 2>&1; then
    echo "Required command is missing: ${name}" >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)
      shift
      AGENT="${1:-}"
      ;;
    auto|codex|claude|cursor)
      AGENT="$1"
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

SCRIPT_SOURCE="${BASH_SOURCE[0]-}"
if [[ -n "${SCRIPT_SOURCE}" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "${SCRIPT_SOURCE}")" && pwd)"
  if [[ -f "${SCRIPT_DIR}/../pyproject.toml" && -f "${SCRIPT_DIR}/../itt" ]]; then
    LOCAL_REPO="$(cd "${SCRIPT_DIR}/.." && pwd)"
  fi
fi

detect_rc_file

PREPARE_REMOTE_CMD=(/bin/sh -c "rm -rf \"${REPO_DIR}\" && mkdir -p \"${INTENT_HOME}\" && git clone --depth 1 --branch \"${REPO_REF}\" \"${REPO_URL}\" \"${REPO_DIR}\"")
PREPARE_LOCAL_CMD=(/bin/sh -c "rm -rf \"${REPO_DIR}\" && mkdir -p \"${INTENT_HOME}\" && cp -R \"${LOCAL_REPO}\" \"${REPO_DIR}\"")
LAUNCHER_CMD=(/bin/sh -c "mkdir -p \"${BIN_DIR}\" && chmod +x \"${REPO_DIR}/itt\" && ln -sfn \"${REPO_DIR}/itt\" \"${LAUNCHER_PATH}\"")
SETUP_CMD=("${REPO_DIR}/itt" setup --agent "${AGENT}")
DOCTOR_CMD=("${REPO_DIR}/itt" doctor)

if [[ "${AGENT}" != "auto" ]]; then
  DOCTOR_CMD+=(--agent "${AGENT}")
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
  printf 'Bootstrap plan:\n'
  if [[ -z "${LOCAL_REPO}" ]]; then
    print_cmd "${PREPARE_REMOTE_CMD[@]}"
  else
    print_cmd "${PREPARE_LOCAL_CMD[@]}"
  fi
  print_cmd "${LAUNCHER_CMD[@]}"
  if ! path_is_configured; then
    if [[ -n "${RC_FILE}" ]]; then
      note "append ${BIN_DIR} to PATH in ${RC_FILE}"
    else
      note "add ${BIN_DIR} to PATH manually so itt is available in new shells"
    fi
  fi
  print_cmd "${SETUP_CMD[@]}"
  print_cmd "${DOCTOR_CMD[@]}"
  exit 0
fi

require_command git
require_command python3

if [[ -z "${LOCAL_REPO}" ]]; then
  "${PREPARE_REMOTE_CMD[@]}"
else
  "${PREPARE_LOCAL_CMD[@]}"
fi

"${LAUNCHER_CMD[@]}"
configure_shell_path
"${SETUP_CMD[@]}"
"${DOCTOR_CMD[@]}"

printf 'Intent repository: %s\n' "${REPO_DIR}"
printf 'Intent command: %s\n' "${LAUNCHER_PATH}"
if [[ "${PATH_UPDATED}" -eq 1 ]]; then
  printf 'Shell profile updated: %s\n' "${RC_FILE}"
  printf 'Open a new shell or run:\n'
  printf '  %s\n' "$(path_export_line)"
elif ! path_is_configured; then
  printf 'Add this directory to PATH if you want `itt` in new shells:\n'
  printf '  %s\n' "${BIN_DIR}"
fi
