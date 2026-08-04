#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BUILDER="${INTHUB_BUILDER:-shared-linux-amd64}"
TARGET_PLATFORM="linux/amd64"
OUTPUT_ROOT="${INTHUB_RELEASE_OUTPUT_ROOT:-${REPOSITORY_ROOT}/dist/inthub}"
GITHUB_SYNC="${INTHUB_GITHUB_SYNC_STATUS:-pending}"
SMOKE_CONTAINER=""
STAGING_DIRECTORY=""

fail() {
    echo "IntHub release build failed: $*" >&2
    exit 1
}

cleanup() {
    if [[ -n "${SMOKE_CONTAINER}" ]]; then
        docker rm --force "${SMOKE_CONTAINER}" >/dev/null 2>&1 || true
    fi
    if [[ -n "${STAGING_DIRECTORY}" && -d "${STAGING_DIRECTORY}" ]]; then
        rm -rf -- "${STAGING_DIRECTORY}"
    fi
}
trap cleanup EXIT

for command_name in docker git gzip python3 tar; do
    command -v "${command_name}" >/dev/null 2>&1 \
        || fail "required command is unavailable: ${command_name}"
done

[[ "${GITHUB_SYNC}" == pending || "${GITHUB_SYNC}" == confirmed ]] \
    || fail "INTHUB_GITHUB_SYNC_STATUS must be pending or confirmed"
[[ "${BUILDER}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] \
    || fail "INTHUB_BUILDER contains unsupported characters"

cd "${REPOSITORY_ROOT}"

[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] \
    || fail "the Git worktree must be clean, including untracked files"
[[ "$(git branch --show-current)" == main ]] \
    || fail "official releases must be built from the main branch"

RELEASE_SHA="$(git rev-parse HEAD)"
[[ "${RELEASE_SHA}" =~ ^[0-9a-f]{40,64}$ ]] \
    || fail "Git did not return a full hexadecimal commit ID"
RELEASE_VERSION="$(git describe --tags --always --long)"
APP_IMAGE="inthub:${RELEASE_SHA}"
FINAL_DIRECTORY="${OUTPUT_ROOT}/${RELEASE_SHA}"
DATABASE_LOCK_LINE="$(
    python3 - "${SCRIPT_DIR}/runtime-images.lock.json" <<'PY'
import json
import pathlib
import sys

database = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))["images"]["database"]
values = [database[key] for key in ("reference", "pull_reference", "id")]
if any(not isinstance(value, str) or not value or "\t" in value for value in values):
    raise SystemExit("invalid database runtime image lock")
print("\t".join(values))
PY
)"
IFS=$'\t' read -r DATABASE_IMAGE DATABASE_PULL_REFERENCE DATABASE_IMAGE_ID \
    <<< "${DATABASE_LOCK_LINE}"
[[ -n "${DATABASE_IMAGE}" && -n "${DATABASE_PULL_REFERENCE}" && -n "${DATABASE_IMAGE_ID}" ]] \
    || fail "database runtime image lock is invalid"

if [[ -d "${FINAL_DIRECTORY}" ]]; then
    python3 "${SCRIPT_DIR}/release_manifest.py" verify \
        --bundle "${FINAL_DIRECTORY}" \
        --expected-sha "${RELEASE_SHA}" >/dev/null \
        || fail "an existing release bundle is invalid; it will not be overwritten"
    printf '%s\n' "${FINAL_DIRECTORY}"
    exit 0
fi

docker info >/dev/null 2>&1 \
    || fail "the local Docker Engine is unavailable"
docker buildx version >/dev/null 2>&1 \
    || fail "Docker Buildx is unavailable; install it before bootstrapping the shared Builder"

python3 -m pytest -q
git diff --check
git show --check --format= "${RELEASE_SHA}" >/dev/null
[[ "$(git rev-parse HEAD)" == "${RELEASE_SHA}" \
    && -z "$(git status --porcelain=v1 --untracked-files=all)" ]] \
    || fail "the repository changed while local qualification was running"

mkdir -p "${OUTPUT_ROOT}"
STAGING_DIRECTORY="$(mktemp -d "${OUTPUT_ROOT}/.staging.${RELEASE_SHA}.XXXXXX")"
BUNDLE_DIRECTORY="${STAGING_DIRECTORY}/bundle"
CONTEXT_DIRECTORY="${STAGING_DIRECTORY}/context"
mkdir "${BUNDLE_DIRECTORY}" "${CONTEXT_DIRECTORY}"

# Both the source evidence and the Docker context come from the exact commit,
# never from an rsync of the live working tree.
git archive \
    --format=tar.gz \
    --prefix="Intent-${RELEASE_SHA}/" \
    "${RELEASE_SHA}" > "${BUNDLE_DIRECTORY}/source.tar.gz"
tar -xzf "${BUNDLE_DIRECTORY}/source.tar.gz" \
    --strip-components=1 \
    -C "${CONTEXT_DIRECTORY}"
python3 "${SCRIPT_DIR}/release_manifest.py" scan \
    --source "${CONTEXT_DIRECTORY}" >/dev/null

BUILDER_INSPECT="${STAGING_DIRECTORY}/builder-inspect.txt"
docker buildx inspect "${BUILDER}" --bootstrap > "${BUILDER_INSPECT}" \
    || fail "shared Builder ${BUILDER} is unavailable; bootstrap it outside the release lock"
BUILDER_DRIVER="$(awk -F: '/^Driver:/ { sub(/^[[:space:]]+/, "", $2); print $2; exit }' "${BUILDER_INSPECT}")"
[[ -n "${BUILDER_DRIVER}" ]] || BUILDER_DRIVER=unknown
BUILDX_VERSION="$(docker buildx version | tr '\n' ' ' | sed 's/[[:space:]]\+$//')"

docker buildx build \
    --builder "${BUILDER}" \
    --platform "${TARGET_PLATFORM}" \
    --load \
    --tag "${APP_IMAGE}" \
    --build-arg "INTHUB_VERSION=${RELEASE_VERSION}" \
    --build-arg "INTHUB_REVISION=${RELEASE_SHA}" \
    --file "${CONTEXT_DIRECTORY}/Dockerfile" \
    "${CONTEXT_DIRECTORY}"

LOCAL_DATABASE_ID="$(
    docker image inspect --format '{{.Id}}' "${DATABASE_IMAGE}" 2>/dev/null || true
)"
if [[ "${LOCAL_DATABASE_ID}" != "${DATABASE_IMAGE_ID}" ]]; then
    docker pull --platform "${TARGET_PLATFORM}" "${DATABASE_PULL_REFERENCE}"
    docker tag "${DATABASE_PULL_REFERENCE}" "${DATABASE_IMAGE}"
fi

APP_PLATFORM="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "${APP_IMAGE}")"
DATABASE_PLATFORM="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "${DATABASE_IMAGE}")"
[[ "${APP_PLATFORM}" == "${TARGET_PLATFORM}" ]] \
    || fail "application image targets ${APP_PLATFORM}, expected ${TARGET_PLATFORM}"
[[ "${DATABASE_PLATFORM}" == "${TARGET_PLATFORM}" ]] \
    || fail "database image targets ${DATABASE_PLATFORM}, expected ${TARGET_PLATFORM}"
[[ "$(docker image inspect --format '{{.Id}}' "${DATABASE_IMAGE}")" == "${DATABASE_IMAGE_ID}" ]] \
    || fail "database image does not match deploy/inthub/runtime-images.lock.json"

# Exercise the exact production image under its production filesystem and
# privilege boundary before packaging it.
SMOKE_CONTAINER="inthub-release-smoke-${RELEASE_SHA:0:12}-$$"
docker run \
    --detach \
    --platform "${TARGET_PLATFORM}" \
    --name "${SMOKE_CONTAINER}" \
    --read-only \
    --tmpfs /tmp:rw,nosuid,nodev,noexec,size=32m,mode=1777 \
    --tmpfs /data:rw,nosuid,nodev,noexec,size=64m,uid=10001,gid=10001,mode=0700 \
    --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --env INTHUB_REQUIRE_AUTH=0 \
    --env INTHUB_SERVE_WEB=1 \
    "${APP_IMAGE}" >/dev/null

SMOKE_HEALTH=""
for _ in $(seq 1 45); do
    SMOKE_HEALTH="$(
        docker inspect --format '{{.State.Health.Status}}' "${SMOKE_CONTAINER}" 2>/dev/null || true
    )"
    [[ "${SMOKE_HEALTH}" == healthy ]] && break
    [[ "${SMOKE_HEALTH}" == unhealthy ]] && break
    sleep 1
done
if [[ "${SMOKE_HEALTH}" != healthy ]]; then
    docker logs --tail 100 "${SMOKE_CONTAINER}" >&2 || true
    fail "the packaged application image did not become healthy"
fi
docker exec "${SMOKE_CONTAINER}" python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3).read(); urllib.request.urlopen('http://127.0.0.1:8000/readyz', timeout=3).read()"
docker rm --force "${SMOKE_CONTAINER}" >/dev/null
SMOKE_CONTAINER=""

docker save "${APP_IMAGE}" "${DATABASE_IMAGE}" \
    | gzip -n > "${BUNDLE_DIRECTORY}/images.tar.gz"

RELEASE_SOURCE_DIRECTORY="${CONTEXT_DIRECTORY}/deploy/inthub"
install -m 0644 "${RELEASE_SOURCE_DIRECTORY}/compose.yaml" "${BUNDLE_DIRECTORY}/compose.yaml"
install -m 0644 "${RELEASE_SOURCE_DIRECTORY}/inthub.caddy" "${BUNDLE_DIRECTORY}/inthub.caddy"
install -m 0755 "${RELEASE_SOURCE_DIRECTORY}/release_manifest.py" "${BUNDLE_DIRECTORY}/release_manifest.py"
install -m 0755 "${RELEASE_SOURCE_DIRECTORY}/remote-release.sh" "${BUNDLE_DIRECTORY}/remote-release.sh"
install -m 0644 "${RELEASE_SOURCE_DIRECTORY}/runtime-images.lock.json" "${BUNDLE_DIRECTORY}/runtime-images.lock.json"
install -m 0755 "${RELEASE_SOURCE_DIRECTORY}/smoke.sh" "${BUNDLE_DIRECTORY}/smoke.sh"

python3 "${SCRIPT_DIR}/release_manifest.py" create \
    --bundle "${BUNDLE_DIRECTORY}" \
    --repository "${CONTEXT_DIRECTORY}" \
    --git-sha "${RELEASE_SHA}" \
    --version "${RELEASE_VERSION}" \
    --github-sync "${GITHUB_SYNC}" \
    --builder "${BUILDER}" \
    --builder-driver "${BUILDER_DRIVER}" \
    --buildx-version "${BUILDX_VERSION}" \
    --app-image "${APP_IMAGE}" \
    --database-image "${DATABASE_IMAGE}" >/dev/null
python3 "${SCRIPT_DIR}/release_manifest.py" checksums \
    --bundle "${BUNDLE_DIRECTORY}" >/dev/null
python3 "${SCRIPT_DIR}/release_manifest.py" verify \
    --bundle "${BUNDLE_DIRECTORY}" \
    --expected-sha "${RELEASE_SHA}" >/dev/null

[[ "$(git rev-parse HEAD)" == "${RELEASE_SHA}" \
    && -z "$(git status --porcelain=v1 --untracked-files=all)" ]] \
    || fail "the repository changed while the release bundle was being built"

mv "${BUNDLE_DIRECTORY}" "${FINAL_DIRECTORY}"
rmdir "${STAGING_DIRECTORY}"
STAGING_DIRECTORY=""
printf '%s\n' "${FINAL_DIRECTORY}"
