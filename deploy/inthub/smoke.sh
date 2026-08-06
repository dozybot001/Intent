#!/usr/bin/env bash
set -Eeuo pipefail

BASE_URL="${INTHUB_BASE_URL:-https://inthub.tenon.asia}"
LOOPBACK_URL="${INTHUB_LOOPBACK_URL:-}"
TMP_DIRECTORY="$(mktemp -d)"

cleanup() {
    rm -rf -- "${TMP_DIRECTORY}"
}
trap cleanup EXIT

check_surface() {
    local base_url="$1"
    local label="$2"
    local project_status
    local oauth_status
    local trace_status

    curl --fail --silent --show-error --max-time 10 "${base_url}/healthz" >/dev/null
    curl --fail --silent --show-error --max-time 10 "${base_url}/readyz" >/dev/null
    curl --fail --silent --show-error --max-time 10 \
        --dump-header "${TMP_DIRECTORY}/${label}.headers" \
        --output /dev/null \
        "${base_url}/"

    project_status="$(
        curl --silent --show-error --max-time 10 \
            --output /dev/null --write-out '%{http_code}' \
            "${base_url}/api/v1/projects"
    )"
    [[ "${project_status}" == 401 ]] \
        || { echo "Expected anonymous projects to return 401, got ${project_status}." >&2; return 1; }

    oauth_status="$(
        curl --silent --show-error --max-time 10 \
            --output /dev/null --write-out '%{http_code}' \
            "${base_url}/api/v1/auth/github/start"
    )"
    [[ "${oauth_status}" == 302 || "${oauth_status}" == 303 ]] \
        || { echo "Expected GitHub OAuth start to redirect, got ${oauth_status}." >&2; return 1; }

    trace_status="$(
        curl --silent --show-error --max-time 10 \
            --request TRACE --output /dev/null --write-out '%{http_code}' \
            "${base_url}/"
    )"
    [[ "${trace_status}" == 405 ]] \
        || { echo "Expected TRACE to return 405, got ${trace_status}." >&2; return 1; }

    grep -Eiq '^content-security-policy: .*frame-ancestors .none' \
        "${TMP_DIRECTORY}/${label}.headers" \
        && grep -Eiq '^content-security-policy: .*object-src .none' \
            "${TMP_DIRECTORY}/${label}.headers" \
        || { echo "The ${label} response is missing the required CSP." >&2; return 1; }
}

if [[ -n "${LOOPBACK_URL}" ]]; then
    check_surface "${LOOPBACK_URL}" loopback
fi
check_surface "${BASE_URL}" public

echo "IntHub health, authentication boundary, OAuth entry, TRACE, and CSP checks passed."
