#!/usr/bin/env bash
set -Eeuo pipefail

BASE_URL="${INTHUB_BASE_URL:-https://inthub.tenonai.cn}"
OLD_URL="${INTHUB_OLD_URL:-}"
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

    [[ "$(curl --silent --show-error --max-time 10 --output /dev/null --write-out '%{http_code}' "${base_url}/api/v2/history?project=smoke")" == 401 ]] \
        || { echo "Shared semantic history must require authentication." >&2; return 1; }
    [[ "$(curl --silent --show-error --max-time 10 --request POST --header 'Content-Type: application/json' --data '{\"project_name\":\"smoke\"}' --output /dev/null --write-out '%{http_code}' "${base_url}/api/v2/link")" == 401 ]] \
        || { echo "Shared project writes must require a CLI account token." >&2; return 1; }

    oauth_status="$(
        curl --silent --show-error --max-time 10 \
            --request POST --header 'Content-Type: application/json' --data '{"return_to":"/"}' \
            --output "${TMP_DIRECTORY}/${label}.authorization.json" --write-out '%{http_code}' \
            "${base_url}/api/v1/auth/tenon/prepare"
    )"
    [[ "${oauth_status}" == 200 ]] \
        || { echo "Expected Tenon OIDC preparation to succeed, got ${oauth_status}." >&2; return 1; }
    python3 - "${TMP_DIRECTORY}/${label}.authorization.json" <<'PY'
import json
import sys
from urllib.parse import urlparse
with open(sys.argv[1]) as source:
    payload = json.load(source)
target = urlparse(payload["result"]["authorizationUrl"])
assert payload["ok"] is True
assert target.scheme == "https" and target.netloc == "account.tenonai.cn"
assert target.path == "/api/auth/oauth2/authorize" and not target.fragment
PY
    curl --fail --silent --show-error --max-time 10 "${base_url}/auth/redirect" \
        > "${TMP_DIRECTORY}/${label}.transition.html"
    grep -q 'id="transition-title"' "${TMP_DIRECTORY}/${label}.transition.html" \
        || { echo "Fixed login transition page was not served." >&2; return 1; }

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

# The name before tenonai.cn answers 410 for the API and moves every page.
check_old_name() {
    local old_url="$1"
    local reply
    [[ "$(curl --silent --show-error --max-time 10 --output /dev/null --write-out '%{http_code}' "${old_url}/api/v1/projects")" == 410 ]] \
        || { echo "The old name must not serve the API." >&2; return 1; }
    for path in "/" "/healthz" "/device?code=SMOKE" "/privacy" "/config.json"; do
        reply="$(curl --silent --show-error --max-time 10 --output /dev/null --write-out '%{http_code} %{redirect_url}' "${old_url}${path}")"
        [[ "${reply}" == "301 ${BASE_URL}${path}" ]] \
            || { echo "The old name must move ${path} to ${BASE_URL}, got ${reply}." >&2; return 1; }
    done
    [[ "$(curl --silent --show-error --max-time 10 --request TRACE --output /dev/null --write-out '%{http_code}' "${old_url}/")" == 405 ]] \
        || { echo "Expected TRACE on the old name to return 405." >&2; return 1; }
}

if [[ -n "${LOOPBACK_URL}" ]]; then
    check_surface "${LOOPBACK_URL}" loopback
fi
check_surface "${BASE_URL}" public
if [[ -n "${OLD_URL}" ]]; then
    check_old_name "${OLD_URL}"
fi

echo "IntHub health, authentication boundary, OAuth entry, TRACE, and CSP checks passed."
