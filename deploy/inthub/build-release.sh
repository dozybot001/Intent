#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BUILDER="${INTHUB_BUILDER:-default}"
EXPECTED_BUILDER_DRIVER="${INTHUB_BUILDER_DRIVER:-docker}"
TARGET_PLATFORM="linux/amd64"
OUTPUT_ROOT="${INTHUB_RELEASE_OUTPUT_ROOT:-${REPOSITORY_ROOT}/dist/inthub}"
REQUIRED_PYTEST_VERSION="8.4.2"
SMOKE_CONTAINER=""
STAGING_DIRECTORY=""
CONTEXT_DIRECTORY=""

fail() {
    echo "IntHub release build failed: $*" >&2
    exit 1
}

image_config_id() {
    local reference="$1"
    docker image save "${reference}" \
        | python3 "${SCRIPT_DIR}/release_manifest.py" image-config-id \
            --reference "${reference}"
}

cleanup() {
    if [[ -n "${SMOKE_CONTAINER}" ]]; then
        docker rm --force "${SMOKE_CONTAINER}" >/dev/null 2>&1 || true
    fi
    if [[ -n "${CONTEXT_DIRECTORY}" && -d "${CONTEXT_DIRECTORY}" ]]; then
        rm -rf -- "${CONTEXT_DIRECTORY}"
    fi
    if [[ -n "${STAGING_DIRECTORY}" && -d "${STAGING_DIRECTORY}" ]]; then
        rm -rf -- "${STAGING_DIRECTORY}"
    fi
}
trap cleanup EXIT

for command_name in awk docker git grep gzip python3 seq tar; do
    command -v "${command_name}" >/dev/null 2>&1 \
        || fail "required command is unavailable: ${command_name}"
done

[[ "${BUILDER}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] \
    || fail "INTHUB_BUILDER contains unsupported characters"
[[ "${EXPECTED_BUILDER_DRIVER}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] \
    || fail "INTHUB_BUILDER_DRIVER contains unsupported characters"

cd "${REPOSITORY_ROOT}"

[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] \
    || fail "the Git worktree must be clean, including untracked files"
[[ "$(git branch --show-current)" == main ]] \
    || fail "official releases must be built from the main branch"
[[ "$(git rev-parse --is-shallow-repository)" == false ]] \
    || fail "official releases require a complete, non-shallow Git history"

RELEASE_SHA="$(git rev-parse HEAD)"
[[ "${RELEASE_SHA}" =~ ^[0-9a-f]{40,64}$ ]] \
    || fail "Git did not return a full hexadecimal commit ID"
[[ -z "$(git ls-files --stage | awk '$1 == "160000" {print $4}')" ]] \
    || fail "submodules require an explicit project release policy"
if git grep -n 'filter=lfs' "${RELEASE_SHA}" -- ':(glob)**/.gitattributes' >/dev/null 2>&1; then
    fail "Git LFS requires an explicit project release policy"
fi
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
    || fail "Docker Buildx is unavailable"

mkdir -p "${OUTPUT_ROOT}"
STAGING_DIRECTORY="$(mktemp -d "${OUTPUT_ROOT}/.preflight.${RELEASE_SHA}.XXXXXX")"
BUILDER_INSPECT="${STAGING_DIRECTORY}/builder-inspect.txt"
docker buildx inspect "${BUILDER}" --bootstrap > "${BUILDER_INSPECT}" \
    || fail "configured Builder ${BUILDER} is unavailable"
BUILDER_DRIVER="$(awk -F: '/^Driver:/ { sub(/^[[:space:]]+/, "", $2); print $2; exit }' "${BUILDER_INSPECT}")"
[[ "${BUILDER_DRIVER}" == "${EXPECTED_BUILDER_DRIVER}" ]] \
    || fail "Builder ${BUILDER} uses ${BUILDER_DRIVER}, expected ${EXPECTED_BUILDER_DRIVER}"
grep -Eq 'Platforms:.*(^|,|[[:space:]])linux/amd64(,|[[:space:]]|$)' "${BUILDER_INSPECT}" \
    || fail "Builder ${BUILDER} does not advertise linux/amd64"
BUILDKIT_VERSION="$(awk -F: '/BuildKit version:/ { sub(/^[[:space:]]+/, "", $2); print $2; exit }' "${BUILDER_INSPECT}")"
[[ "${BUILDKIT_VERSION}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+ ]] \
    || fail "Builder ${BUILDER} did not report a valid BuildKit version"
BUILDX_VERSION="$(docker buildx version | tr '\n' ' ' | sed 's/[[:space:]]\+$//')"

APP_BASE_IMAGE="$(awk '$1 == "FROM" {print $2; exit}' Dockerfile)"
[[ "${APP_BASE_IMAGE}" =~ ^[A-Za-z0-9][A-Za-z0-9._/:+-]*@sha256:[0-9a-f]{64}$ ]] \
    || fail "Dockerfile base image must use a SHA-256 digest"
if ! docker image inspect "${APP_BASE_IMAGE}" >/dev/null 2>&1; then
    docker pull --platform "${TARGET_PLATFORM}" "${APP_BASE_IMAGE}"
fi
[[ "$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "${APP_BASE_IMAGE}")" == "${TARGET_PLATFORM}" ]] \
    || fail "application base image does not match ${TARGET_PLATFORM}"

LOCAL_DATABASE_ID="$(image_config_id "${DATABASE_IMAGE}" 2>/dev/null || true)"
if [[ "${LOCAL_DATABASE_ID}" != "${DATABASE_IMAGE_ID}" ]]; then
    docker pull --platform "${TARGET_PLATFORM}" "${DATABASE_PULL_REFERENCE}"
    docker tag "${DATABASE_PULL_REFERENCE}" "${DATABASE_IMAGE}"
fi
[[ "$(image_config_id "${DATABASE_IMAGE}")" == "${DATABASE_IMAGE_ID}" ]] \
    || fail "database image does not match deploy/inthub/runtime-images.lock.json"
[[ "$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "${DATABASE_IMAGE}")" == "${TARGET_PLATFORM}" ]] \
    || fail "database runtime lock does not resolve to ${TARGET_PLATFORM}"

QUALIFICATION_PYTHON="$(bash "${SCRIPT_DIR}/prepare-release-env.sh")"

QUALIFICATION_PYTHON_VERSION="$(
    "${QUALIFICATION_PYTHON}" -c 'import platform; print(platform.python_version())'
)"
QUALIFICATION_PYTEST_VERSION="$(
    "${QUALIFICATION_PYTHON}" -c 'import importlib.metadata; print(importlib.metadata.version("pytest"))' 2>/dev/null
)" || fail "the prepared release environment does not contain pytest"
[[ "${QUALIFICATION_PYTEST_VERSION}" == "${REQUIRED_PYTEST_VERSION}" ]] \
    || fail "pytest ${REQUIRED_PYTEST_VERSION} is required, found ${QUALIFICATION_PYTEST_VERSION}"

bash "${SCRIPT_DIR}/qualify-release.sh" "${RELEASE_SHA}"
[[ "$(git rev-parse HEAD)" == "${RELEASE_SHA}" \
    && -z "$(git status --porcelain=v1 --untracked-files=all)" ]] \
    || fail "the repository changed while local qualification was running"

rm -rf -- "${STAGING_DIRECTORY}"
STAGING_DIRECTORY="$(mktemp -d "${OUTPUT_ROOT}/.staging.${RELEASE_SHA}.XXXXXX")"
BUNDLE_DIRECTORY="${STAGING_DIRECTORY}"
CONTEXT_DIRECTORY="$(mktemp -d "${OUTPUT_ROOT}/.context.${RELEASE_SHA}.XXXXXX")"

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
DATABASE_SCHEMA_VERSION="$(
    PYTHONPATH="${CONTEXT_DIRECTORY}" python3 -c \
        'from apps.inthub_api.db import LATEST_SCHEMA_VERSION; print(LATEST_SCHEMA_VERSION)'
)"
[[ "${DATABASE_SCHEMA_VERSION}" =~ ^[1-9][0-9]*$ ]] \
    || fail "candidate database schema version is invalid"

docker buildx build \
    --builder "${BUILDER}" \
    --platform "${TARGET_PLATFORM}" \
    --load \
    --tag "${APP_IMAGE}" \
    --build-arg "INTHUB_VERSION=${RELEASE_VERSION}" \
    --build-arg "INTHUB_REVISION=${RELEASE_SHA}" \
    --build-arg "INTHUB_SCHEMA_VERSION=${DATABASE_SCHEMA_VERSION}" \
    --file "${CONTEXT_DIRECTORY}/Dockerfile" \
    "${CONTEXT_DIRECTORY}"

APP_PLATFORM="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "${APP_IMAGE}")"
DATABASE_PLATFORM="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "${DATABASE_IMAGE}")"
[[ "${APP_PLATFORM}" == "${TARGET_PLATFORM}" ]] \
    || fail "application image targets ${APP_PLATFORM}, expected ${TARGET_PLATFORM}"
[[ "${DATABASE_PLATFORM}" == "${TARGET_PLATFORM}" ]] \
    || fail "database image targets ${DATABASE_PLATFORM}, expected ${TARGET_PLATFORM}"
[[ "$(image_config_id "${DATABASE_IMAGE}")" == "${DATABASE_IMAGE_ID}" ]] \
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
    --database-schema-version "${DATABASE_SCHEMA_VERSION}" \
    --builder "${BUILDER}" \
    --builder-driver "${BUILDER_DRIVER}" \
    --buildx-version "${BUILDX_VERSION}" \
    --buildkit-version "${BUILDKIT_VERSION}" \
    --python-version "${QUALIFICATION_PYTHON_VERSION}" \
    --pytest-version "${QUALIFICATION_PYTEST_VERSION}" \
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

rm -rf -- "${CONTEXT_DIRECTORY}"
CONTEXT_DIRECTORY=""
chmod -R a-w "${BUNDLE_DIRECTORY}"
mv "${STAGING_DIRECTORY}" "${FINAL_DIRECTORY}"
STAGING_DIRECTORY=""
printf '%s\n' "${FINAL_DIRECTORY}"
