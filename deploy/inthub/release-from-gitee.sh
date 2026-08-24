#!/usr/bin/env bash
# Stable production-host launcher. It resolves one exact Gitee main Commit,
# builds in a dedicated checkout, and hands the verified Bundle to the
# lock-protected blue-green activator embedded in that same Commit.
set -Eeuo pipefail

if [[ "$#" -ne 2 ]]; then
    echo "Usage: release-from-gitee.sh <release-sha> <lock-token>" >&2
    exit 2
fi

RELEASE_SHA="$1"
LOCK_TOKEN="$2"
REMOTE_ROOT="${INTHUB_REMOTE_ROOT:-/opt/inthub}"
GITEE_URL="https://gitee.com/dozybot/Intent.git"
GITEE_REF="refs/heads/main"
BUILDER_ROOT="${REMOTE_ROOT}/builder"
SOURCE_REPOSITORY="${BUILDER_ROOT}/source"
TOOLS_ROOT="${BUILDER_ROOT}/tools"
INCOMING_ROOT="${REMOTE_ROOT}/incoming"
RELEASE_DIRECTORY="${REMOTE_ROOT}/releases/${RELEASE_SHA}"
BUILD_LOCK="${REMOTE_ROOT}/.build-lock"
BUILD_LOCK_OWNED=false
BUNDLE_DIRECTORY=""
BUILD_OUTPUT_FILE=""

fail() {
    echo "IntHub Gitee source release failed: $*" >&2
    exit 1
}

cleanup() {
    if [[ "${BUILD_LOCK_OWNED}" == true \
        && -f "${BUILD_LOCK}/owner" \
        && "$(cat "${BUILD_LOCK}/owner" 2>/dev/null || true)" == "${LOCK_TOKEN}" ]]; then
        rm -f "${BUILD_LOCK}/owner" "${BUILD_LOCK}/metadata"
        rmdir "${BUILD_LOCK}" 2>/dev/null || true
    fi
    if [[ -n "${BUILD_OUTPUT_FILE}" ]]; then
        rm -f -- "${BUILD_OUTPUT_FILE}"
    fi
}
trap cleanup EXIT

[[ "${REMOTE_ROOT}" =~ ^/[A-Za-z0-9._/-]+$ && "${REMOTE_ROOT}" != *".."* ]] \
    || fail "remote root is unsafe"
[[ "${RELEASE_SHA}" =~ ^[0-9a-f]{40,64}$ ]] || fail "release SHA is invalid"
[[ "${LOCK_TOKEN}" =~ ^[A-Za-z0-9._-]+$ ]] || fail "lock token is invalid"

for command_name in awk curl docker git gzip mktemp python3 seq sha256sum tail tar tee; do
    command -v "${command_name}" >/dev/null 2>&1 \
        || fail "required server build command is unavailable: ${command_name}"
done
docker version >/dev/null
docker buildx version >/dev/null
docker buildx inspect default --bootstrap >/dev/null

for deployment_path in \
    "${REMOTE_ROOT}" \
    "${INCOMING_ROOT}" \
    "${REMOTE_ROOT}/releases" \
    "${REMOTE_ROOT}/backups" \
    "${REMOTE_ROOT}/logs" \
    "${REMOTE_ROOT}/shared" \
    "${BUILDER_ROOT}" \
    "${REMOTE_ROOT}/deploy"; do
    [[ -d "${deployment_path}" && ! -L "${deployment_path}" ]] \
        || fail "deployment directory is missing or symlinked: ${deployment_path}"
done
[[ ! -e "${REMOTE_ROOT}/.release-lock" ]] \
    || fail "a fail-closed production release lock already exists"
if ! mkdir "${BUILD_LOCK}" 2>/dev/null; then
    fail "another IntHub server build owns the fail-closed build lock"
fi
BUILD_LOCK_OWNED=true
(
    umask 077
    printf '%s\n' "${LOCK_TOKEN}" > "${BUILD_LOCK}/owner"
    {
        printf 'release_sha=%s\n' "${RELEASE_SHA}"
        printf 'source=gitee-exact-commit\n'
        printf 'repository=%s\n' "${GITEE_URL}"
        printf 'started_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    } > "${BUILD_LOCK}/metadata"
)

REMOTE_SHA="$(git ls-remote "${GITEE_URL}" "${GITEE_REF}" | awk 'NR == 1 {print $1}')"
[[ "${REMOTE_SHA}" == "${RELEASE_SHA}" ]] \
    || fail "Gitee main does not match the requested release SHA"

if [[ -e "${RELEASE_DIRECTORY}" ]]; then
    [[ -d "${RELEASE_DIRECTORY}" && ! -L "${RELEASE_DIRECTORY}" ]] \
        || fail "existing release path is unsafe"
    python3 "${RELEASE_DIRECTORY}/release_manifest.py" verify \
        --bundle "${RELEASE_DIRECTORY}" \
        --expected-sha "${RELEASE_SHA}" >/dev/null
    BUNDLE_DIRECTORY="${INCOMING_ROOT}/${RELEASE_SHA}-reuse-${LOCK_TOKEN}"
    [[ ! -e "${BUNDLE_DIRECTORY}" ]] || fail "release reuse staging path already exists"
    cp -a "${RELEASE_DIRECTORY}" "${BUNDLE_DIRECTORY}"
    chmod u+w "${BUNDLE_DIRECTORY}"
else
    if [[ -e "${SOURCE_REPOSITORY}" ]]; then
        [[ -d "${SOURCE_REPOSITORY}/.git" && ! -L "${SOURCE_REPOSITORY}" ]] \
            || fail "server Builder checkout is not a regular Git repository"
        git -C "${SOURCE_REPOSITORY}" reset --hard HEAD >/dev/null
        git -C "${SOURCE_REPOSITORY}" clean -fdx >/dev/null
    else
        git clone --no-checkout "${GITEE_URL}" "${SOURCE_REPOSITORY}"
    fi
    git -C "${SOURCE_REPOSITORY}" remote set-url origin "${GITEE_URL}"
    git -C "${SOURCE_REPOSITORY}" fetch --prune --tags origin "${GITEE_REF}"
    [[ "$(git -C "${SOURCE_REPOSITORY}" rev-parse FETCH_HEAD)" == "${RELEASE_SHA}" ]] \
        || fail "the fetched Gitee Commit does not match the requested release SHA"
    git -C "${SOURCE_REPOSITORY}" checkout -B main "${RELEASE_SHA}" >/dev/null
    git -C "${SOURCE_REPOSITORY}" reset --hard "${RELEASE_SHA}" >/dev/null
    git -C "${SOURCE_REPOSITORY}" clean -fdx >/dev/null
    [[ "$(git -C "${SOURCE_REPOSITORY}" rev-parse HEAD)" == "${RELEASE_SHA}" ]] \
        || fail "server Builder checkout did not settle on the requested Commit"

    BUILD_OUTPUT_FILE="$(mktemp "${BUILDER_ROOT}/.build-output.${RELEASE_SHA}.XXXXXX")"
    {
        cd "${SOURCE_REPOSITORY}"
        INTHUB_BUILDER=default \
        INTHUB_BUILDER_DRIVER=docker \
        INTHUB_RELEASE_OUTPUT_ROOT="${INCOMING_ROOT}" \
        INTHUB_RELEASE_TOOL_ROOT="${TOOLS_ROOT}" \
        INTHUB_QUALIFICATION_ROOT="${BUILDER_ROOT}/qualification" \
            bash deploy/inthub/build-release.sh
    } | tee "${BUILD_OUTPUT_FILE}"
    BUNDLE_DIRECTORY="$(tail -n 1 "${BUILD_OUTPUT_FILE}")"
    rm -f -- "${BUILD_OUTPUT_FILE}"
    BUILD_OUTPUT_FILE=""
    [[ "${BUNDLE_DIRECTORY}" == "${INCOMING_ROOT}/${RELEASE_SHA}" ]] \
        || fail "server build returned an unexpected Bundle path"
fi

python3 "${BUNDLE_DIRECTORY}/release_manifest.py" verify \
    --bundle "${BUNDLE_DIRECTORY}" \
    --expected-sha "${RELEASE_SHA}" >/dev/null
INTHUB_RELEASE_SOURCE=gitee-exact-commit \
    bash "${BUNDLE_DIRECTORY}/remote-release.sh" \
        "${REMOTE_ROOT}" "${RELEASE_SHA}" "${LOCK_TOKEN}"
