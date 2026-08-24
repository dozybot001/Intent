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
    local showcase_status
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

    showcase_status="$(
        curl --silent --show-error --max-time 10 \
            --output "${TMP_DIRECTORY}/${label}.showcase.html" --write-out '%{http_code}' \
            "${base_url}/showcase"
    )"
    [[ "${showcase_status}" == 200 ]] \
        || { echo "Expected the showcase shell to return 200, got ${showcase_status}." >&2; return 1; }
    curl --fail --silent --show-error --max-time 10 \
        "${base_url}/showcase/config.json" \
        > "${TMP_DIRECTORY}/${label}.showcase-config.json"
    python3 - "${TMP_DIRECTORY}/${label}.showcase-config.json" <<'PY'
import json
import pathlib
import sys

config = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
if config.get("publicMode") is not True:
    raise SystemExit("showcase config must enable publicMode")
if config.get("authRequired") is not False:
    raise SystemExit("showcase config must not require a private browser session")
if config.get("publicProfileSlug") != "showcase":
    raise SystemExit("showcase config must resolve the showcase profile")
PY

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

echo "IntHub health, authentication boundary, showcase shell, OAuth entry, TRACE, and CSP checks passed."
