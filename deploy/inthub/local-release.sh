#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEPLOY_HOST="${INTHUB_DEPLOY_HOST:-agenthub-prod}"
REMOTE_ROOT="${INTHUB_REMOTE_ROOT:-/opt/inthub}"
OUTPUT_ROOT="${INTHUB_RELEASE_OUTPUT_ROOT:-${REPOSITORY_ROOT}/dist/inthub}"
UPLOAD_DIRECTORY=""
LOCK_TOKEN=""
LOCAL_OWNS_LOCK=false
REMOTE_EXECUTION_STARTED=false

fail() {
    echo "IntHub release failed: $*" >&2
    exit 1
}

cleanup() {
    if [[ "${REMOTE_EXECUTION_STARTED}" == true ]]; then
        return
    fi
    if [[ -n "${UPLOAD_DIRECTORY}" ]]; then
        ssh "${DEPLOY_HOST}" "rm -rf -- '${UPLOAD_DIRECTORY}'" >/dev/null 2>&1 || true
    fi
    if [[ "${LOCAL_OWNS_LOCK}" == true && -n "${LOCK_TOKEN}" ]]; then
        ssh "${DEPLOY_HOST}" "
            if test -f '${REMOTE_ROOT}/.release-lock/owner' \
                && test \"\$(cat '${REMOTE_ROOT}/.release-lock/owner')\" = '${LOCK_TOKEN}'; then
                rm -f '${REMOTE_ROOT}/.release-lock/owner' '${REMOTE_ROOT}/.release-lock/metadata'
                rmdir '${REMOTE_ROOT}/.release-lock' 2>/dev/null || true
            fi
        " >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

for command_name in git python3 rsync shasum ssh; do
    command -v "${command_name}" >/dev/null 2>&1 \
        || fail "required command is unavailable: ${command_name}"
done
[[ "${REMOTE_ROOT}" =~ ^/[A-Za-z0-9._/-]+$ && "${REMOTE_ROOT}" != *".."* ]] \
    || fail "INTHUB_REMOTE_ROOT is unsafe"
[[ "${DEPLOY_HOST}" =~ ^[A-Za-z0-9][A-Za-z0-9._@:-]*$ ]] \
    || fail "INTHUB_DEPLOY_HOST contains unsupported characters"

cd "${REPOSITORY_ROOT}"
bash "${SCRIPT_DIR}/build-release.sh"

RELEASE_SHA="$(git rev-parse HEAD)"
BUNDLE_DIRECTORY="${OUTPUT_ROOT}/${RELEASE_SHA}"
python3 "${SCRIPT_DIR}/release_manifest.py" verify \
    --bundle "${BUNDLE_DIRECTORY}" \
    --expected-sha "${RELEASE_SHA}" >/dev/null

LOCK_TOKEN="release-${RELEASE_SHA:0:12}-$$-$(date -u +%Y%m%dT%H%M%SZ)"
UPLOAD_DIRECTORY="${REMOTE_ROOT}/incoming/${RELEASE_SHA}-${LOCK_TOKEN}"
REMOTE_SCRIPT_SHA="$(shasum -a 256 "${BUNDLE_DIRECTORY}/remote-release.sh" | awk '{print $1}')"
CHECKSUM_FILE_SHA="$(shasum -a 256 "${BUNDLE_DIRECTORY}/SHA256SUMS" | awk '{print $1}')"

# Bootstrap only project-owned directories before upload. No source remote,
# image registry, database, service, or ingress is touched at this stage.
ssh "${DEPLOY_HOST}" "
    set -eu
    remote_uid=\$(id -u)
    remote_gid=\$(id -g)
    for path in \
        '${REMOTE_ROOT}' \
        '${REMOTE_ROOT}/incoming' \
        '${REMOTE_ROOT}/releases' \
        '${REMOTE_ROOT}/backups' \
        '${REMOTE_ROOT}/logs' \
        '${REMOTE_ROOT}/shared'; do
        if test -L \"\${path}\"; then
            echo \"Refusing symlinked IntHub deployment path: \${path}\" >&2
            exit 1
        fi
    done
    sudo -n install -d -m 0750 -o \"\${remote_uid}\" -g \"\${remote_gid}\" \
        '${REMOTE_ROOT}' \
        '${REMOTE_ROOT}/incoming' \
        '${REMOTE_ROOT}/releases' \
        '${REMOTE_ROOT}/backups' \
        '${REMOTE_ROOT}/logs' \
        '${REMOTE_ROOT}/shared'
    test ! -e '${UPLOAD_DIRECTORY}'
    mkdir -m 0700 '${UPLOAD_DIRECTORY}'
    test -f '${REMOTE_ROOT}/shared/inthub.env'
    test ! -L '${REMOTE_ROOT}/shared/inthub.env'
    test \"\$(stat -c '%a' '${REMOTE_ROOT}/shared/inthub.env')\" = 600
"

# REMOTE_ROOT, DEPLOY_HOST, RELEASE_SHA, and LOCK_TOKEN are restricted to a
# shell-safe character set above.  macOS ships openrsync 2.6.9, so this command
# intentionally uses only its portable archive-mode argument surface.
rsync --archive \
    "${BUNDLE_DIRECTORY}/" \
    "${DEPLOY_HOST}:${UPLOAD_DIRECTORY}/"

ssh "${DEPLOY_HOST}" "
    set -eu
    test \"\$(sha256sum '${UPLOAD_DIRECTORY}/remote-release.sh' | awk '{print \$1}')\" \
        = '${REMOTE_SCRIPT_SHA}'
    test \"\$(sha256sum '${UPLOAD_DIRECTORY}/SHA256SUMS' | awk '{print \$1}')\" \
        = '${CHECKSUM_FILE_SHA}'
    (cd '${UPLOAD_DIRECTORY}' && sha256sum --check --strict SHA256SUMS >/dev/null)
    python3 '${UPLOAD_DIRECTORY}/release_manifest.py' verify \
        --bundle '${UPLOAD_DIRECTORY}' \
        --expected-sha '${RELEASE_SHA}' >/dev/null
    if mkdir '${REMOTE_ROOT}/.release-lock' 2>/dev/null; then
        printf '%s\n' '${LOCK_TOKEN}' > '${REMOTE_ROOT}/.release-lock/owner'
        {
            printf 'release_sha=%s\n' '${RELEASE_SHA}'
            printf 'bundle_id=%s\n' '${RELEASE_SHA}'
            printf 'client_host=%s\n' \"\$(hostname)\"
            printf 'started_at=%s\n' \"\$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
        } > '${REMOTE_ROOT}/.release-lock/metadata'
    else
        echo 'Another IntHub release owns the fail-closed release lock.' >&2
        exit 1
    fi
"
LOCAL_OWNS_LOCK=true

# Once remote execution begins, an interrupted SSH connection must leave the
# lock fail-closed for inspection; local cleanup must not race an unknown
# production outcome.
REMOTE_EXECUTION_STARTED=true
ssh \
    -o ServerAliveInterval=15 \
    -o ServerAliveCountMax=4 \
    "${DEPLOY_HOST}" \
    "bash '${UPLOAD_DIRECTORY}/remote-release.sh' '${REMOTE_ROOT}' '${RELEASE_SHA}' '${LOCK_TOKEN}'"
LOCAL_OWNS_LOCK=false

ACTIVE_RELEASE="$(ssh "${DEPLOY_HOST}" "readlink -f '${REMOTE_ROOT}/current'")"
[[ "${ACTIVE_RELEASE}" == "${REMOTE_ROOT}/releases/${RELEASE_SHA}" ]] \
    || fail "remote release returned success but current points elsewhere"

echo "Released IntHub ${RELEASE_SHA} from a locally qualified immutable bundle."
