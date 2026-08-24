#!/usr/bin/env bash
# One-time (or explicit control-plane upgrade) bootstrap for the stable server
# launcher. It does not build, migrate, restart, or switch production traffic.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEPLOY_HOST="${INTHUB_DEPLOY_HOST:-agenthub-prod}"
REMOTE_ROOT="${INTHUB_REMOTE_ROOT:-/opt/inthub}"
LAUNCHER="${SCRIPT_DIR}/release-from-gitee.sh"
STAGING_PATH="${REMOTE_ROOT}/incoming/.release-from-gitee.$$.sh"

fail() {
    echo "IntHub Gitee deployment bootstrap failed: $*" >&2
    exit 1
}

for command_name in git rsync shasum ssh; do
    command -v "${command_name}" >/dev/null 2>&1 \
        || fail "required bootstrap command is unavailable: ${command_name}"
done
[[ "${DEPLOY_HOST}" =~ ^[A-Za-z0-9][A-Za-z0-9._@:-]*$ ]] \
    || fail "INTHUB_DEPLOY_HOST contains unsupported characters"
[[ "${REMOTE_ROOT}" =~ ^/[A-Za-z0-9._/-]+$ && "${REMOTE_ROOT}" != *".."* ]] \
    || fail "INTHUB_REMOTE_ROOT is unsafe"

cd "${REPOSITORY_ROOT}"
[[ "$(git branch --show-current)" == main ]] || fail "bootstrap must use main"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] \
    || fail "bootstrap requires a clean worktree"
LOCAL_SHA="$(shasum -a 256 "${LAUNCHER}" | awk '{print $1}')"

ssh -o BatchMode=yes "${DEPLOY_HOST}" "
    set -eu
    remote_uid=\$(id -u)
    remote_gid=\$(id -g)
    sudo -n install -d -m 0750 -o \"\${remote_uid}\" -g \"\${remote_gid}\" \
        '${REMOTE_ROOT}' \
        '${REMOTE_ROOT}/incoming' \
        '${REMOTE_ROOT}/releases' \
        '${REMOTE_ROOT}/backups' \
        '${REMOTE_ROOT}/logs' \
        '${REMOTE_ROOT}/shared' \
        '${REMOTE_ROOT}/builder' \
        '${REMOTE_ROOT}/deploy'
    test -f '${REMOTE_ROOT}/shared/inthub.env'
    test ! -L '${REMOTE_ROOT}/shared/inthub.env'
    test \"\$(stat -c '%a' '${REMOTE_ROOT}/shared/inthub.env')\" = 600
    test ! -e '${REMOTE_ROOT}/.release-lock'
    test ! -e '${REMOTE_ROOT}/.build-lock'
"
rsync --archive "${LAUNCHER}" "${DEPLOY_HOST}:${STAGING_PATH}"
ssh -o BatchMode=yes "${DEPLOY_HOST}" "
    set -eu
    test \"\$(sha256sum '${STAGING_PATH}' | awk '{print \$1}')\" = '${LOCAL_SHA}'
    install -m 0755 '${STAGING_PATH}' '${REMOTE_ROOT}/deploy/release-from-gitee.sh'
    rm -f '${STAGING_PATH}'
    test \"\$(sha256sum '${REMOTE_ROOT}/deploy/release-from-gitee.sh' | awk '{print \$1}')\" = '${LOCAL_SHA}'
    git ls-remote https://gitee.com/dozybot/Intent.git refs/heads/main >/dev/null
    docker version >/dev/null
    docker buildx inspect default --bootstrap >/dev/null
"
echo "IntHub Gitee exact-Commit deployment prerequisites are configured."
