#!/usr/bin/env bash
# Create or reuse the exact local Python qualification environment. The cache
# is project-owned and ignored by Git; dependency changes select a new path.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TOOL_ROOT="${INTHUB_RELEASE_TOOL_ROOT:-${REPOSITORY_ROOT}/dist/inthub-tools}"
REQUIRED_PYTEST_VERSION="8.4.2"
STAGING_DIRECTORY=""
LOCK_DIRECTORY=""

fail() {
    echo "IntHub release environment failed: $*" >&2
    exit 1
}

cleanup() {
    if [[ -n "${STAGING_DIRECTORY}" && -d "${STAGING_DIRECTORY}" ]]; then
        rm -rf -- "${STAGING_DIRECTORY}"
    fi
    if [[ -n "${LOCK_DIRECTORY}" && -d "${LOCK_DIRECTORY}" ]]; then
        rmdir "${LOCK_DIRECTORY}" 2>/dev/null || true
    fi
}
trap cleanup EXIT

for command_name in python3 shasum; do
    command -v "${command_name}" >/dev/null 2>&1 \
        || fail "required command is unavailable: ${command_name}"
done

if [[ -n "${INTHUB_RELEASE_PYTHON:-}" ]]; then
    [[ "${INTHUB_RELEASE_PYTHON}" == /* && -x "${INTHUB_RELEASE_PYTHON}" ]] \
        || fail "INTHUB_RELEASE_PYTHON must be an executable absolute path"
    RELEASE_PYTHON="${INTHUB_RELEASE_PYTHON}"
else
    PYTHON_ID="$(python3 -c 'import platform; print(f"{platform.python_implementation().lower()}-{platform.python_version()}")')"
    DEPENDENCY_ID="$(
        {
            printf '%s\n' "${PYTHON_ID}"
            shasum -a 256 "${REPOSITORY_ROOT}/pyproject.toml"
        } | shasum -a 256 | awk '{print $1}'
    )"
    ENVIRONMENT_DIRECTORY="${TOOL_ROOT}/${PYTHON_ID}-${DEPENDENCY_ID}"
    RELEASE_PYTHON="${ENVIRONMENT_DIRECTORY}/bin/python"
    if [[ ! -x "${RELEASE_PYTHON}" ]]; then
        mkdir -p "${TOOL_ROOT}"
        LOCK_DIRECTORY="${ENVIRONMENT_DIRECTORY}.lock"
        mkdir "${LOCK_DIRECTORY}" 2>/dev/null \
            || fail "another process is preparing ${ENVIRONMENT_DIRECTORY}"
        STAGING_DIRECTORY="$(mktemp -d "${TOOL_ROOT}/.staging.${DEPENDENCY_ID}.XXXXXX")"
        cd "${REPOSITORY_ROOT}"
        python3 -m venv "${STAGING_DIRECTORY}/venv"
        "${STAGING_DIRECTORY}/venv/bin/python" -m pip install \
            --disable-pip-version-check \
            ".[server,release]" >&2
        mv "${STAGING_DIRECTORY}/venv" "${ENVIRONMENT_DIRECTORY}"
        rmdir "${STAGING_DIRECTORY}"
        STAGING_DIRECTORY=""
        rmdir "${LOCK_DIRECTORY}"
        LOCK_DIRECTORY=""
    fi
fi

PYTEST_VERSION="$(
    "${RELEASE_PYTHON}" -c 'import importlib.metadata; print(importlib.metadata.version("pytest"))'
)" || fail "release Python does not contain pytest"
[[ "${PYTEST_VERSION}" == "${REQUIRED_PYTEST_VERSION}" ]] \
    || fail "release Python must contain pytest ${REQUIRED_PYTEST_VERSION}, found ${PYTEST_VERSION}"
"${RELEASE_PYTHON}" -c 'import psycopg' \
    || fail "release Python does not contain PostgreSQL support"

printf '%s\n' "${RELEASE_PYTHON}"
