#!/usr/bin/env bash
# The only supported production entry: qualify locally, publish the exact
# Commit to Gitee, then let the isolated production Builder create one
# immutable Bundle and activate it through the existing blue-green contract.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEPLOY_HOST="${INTHUB_DEPLOY_HOST:-agenthub-prod}"
REMOTE_ROOT="${INTHUB_REMOTE_ROOT:-/opt/inthub}"
GITEE_URL="https://gitee.com/dozybot/Intent.git"
GITEE_REF="refs/heads/main"
PUBLIC_URL="https://inthub.tenon.asia"

fail() {
    echo "IntHub Gitee release failed: $*" >&2
    exit 1
}

for command_name in curl git shasum ssh; do
    command -v "${command_name}" >/dev/null 2>&1 \
        || fail "required release command is unavailable: ${command_name}"
done
[[ "${DEPLOY_HOST}" =~ ^[A-Za-z0-9][A-Za-z0-9._@:-]*$ ]] \
    || fail "INTHUB_DEPLOY_HOST contains unsupported characters"
[[ "${REMOTE_ROOT}" =~ ^/[A-Za-z0-9._/-]+$ && "${REMOTE_ROOT}" != *".."* ]] \
    || fail "INTHUB_REMOTE_ROOT is unsafe"

cd "${REPOSITORY_ROOT}"
bash "${SCRIPT_DIR}/qualify-release.sh"
RELEASE_SHA="$(git rev-parse HEAD)"
[[ "${RELEASE_SHA}" =~ ^[0-9a-f]{40,64}$ ]] \
    || fail "Git did not return a full hexadecimal Commit ID"

LAUNCHER_SHA="$(shasum -a 256 "${SCRIPT_DIR}/release-from-gitee.sh" | awk '{print $1}')"
REMOTE_LAUNCHER_SHA="$(
    ssh -o BatchMode=yes "${DEPLOY_HOST}" \
        "sha256sum '${REMOTE_ROOT}/deploy/release-from-gitee.sh' 2>/dev/null | awk '{print \$1}'"
)"
[[ "${REMOTE_LAUNCHER_SHA}" == "${LAUNCHER_SHA}" ]] \
    || fail "server launcher is missing or stale; run deploy/inthub/bootstrap-gitee-deployment.sh"

REMOTE_BEFORE="$(git ls-remote "${GITEE_URL}" "${GITEE_REF}" | awk 'NR == 1 {print $1}')"
if [[ -n "${REMOTE_BEFORE}" ]]; then
    [[ "${REMOTE_BEFORE}" =~ ^[0-9a-f]{40,64}$ ]] \
        || fail "Gitee returned an invalid main Commit"
    git merge-base --is-ancestor "${REMOTE_BEFORE}" "${RELEASE_SHA}" \
        || fail "Gitee main is not an ancestor of the requested release"
fi
git push "${GITEE_URL}" "${RELEASE_SHA}:${GITEE_REF}"
REMOTE_AFTER="$(git ls-remote "${GITEE_URL}" "${GITEE_REF}" | awk 'NR == 1 {print $1}')"
[[ "${REMOTE_AFTER}" == "${RELEASE_SHA}" ]] \
    || fail "Gitee main did not settle on the requested release SHA"

LOCK_TOKEN="gitee-${RELEASE_SHA:0:12}-$$-$(date -u +%Y%m%dT%H%M%SZ)"
ssh \
    -o BatchMode=yes \
    -o ServerAliveInterval=15 \
    -o ServerAliveCountMax=4 \
    "${DEPLOY_HOST}" \
    "bash '${REMOTE_ROOT}/deploy/release-from-gitee.sh' '${RELEASE_SHA}' '${LOCK_TOKEN}'"

ACTIVE_RELEASE="$(ssh -o BatchMode=yes "${DEPLOY_HOST}" "readlink -f '${REMOTE_ROOT}/current'")"
[[ "${ACTIVE_RELEASE}" == "${REMOTE_ROOT}/releases/${RELEASE_SHA}" ]] \
    || fail "server release returned success but current points elsewhere"
curl --fail --silent --show-error --max-time 10 "${PUBLIC_URL}/healthz" >/dev/null
echo "Released IntHub ${RELEASE_SHA} from the verified Gitee exact Commit."
