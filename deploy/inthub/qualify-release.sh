#!/usr/bin/env bash
# Qualify one clean, complete main Commit without building the production App
# image. This gate runs locally before publishing to Gitee and runs again in
# the isolated server Builder before the one production image build.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TARGET_PLATFORM="linux/amd64"
EXPECTED_SHA="${1:-}"
QUALIFICATION_ROOT="${INTHUB_QUALIFICATION_ROOT:-${REPOSITORY_ROOT}/dist/inthub-qualification}"
REQUIRED_PYTEST_VERSION="8.4.2"
TEST_DATABASE_CONTAINER=""
SOURCE_DIRECTORY=""

fail() {
    echo "IntHub release qualification failed: $*" >&2
    exit 1
}

image_config_id() {
    local reference="$1"
    docker image save "${reference}" \
        | python3 "${SCRIPT_DIR}/release_manifest.py" image-config-id \
            --reference "${reference}"
}

cleanup() {
    if [[ -n "${TEST_DATABASE_CONTAINER}" ]]; then
        docker rm --force "${TEST_DATABASE_CONTAINER}" >/dev/null 2>&1 || true
    fi
    if [[ -n "${SOURCE_DIRECTORY}" && -d "${SOURCE_DIRECTORY}" ]]; then
        rm -rf -- "${SOURCE_DIRECTORY}"
    fi
}
trap cleanup EXIT

for command_name in awk docker git grep gzip python3 seq tar; do
    command -v "${command_name}" >/dev/null 2>&1 \
        || fail "required command is unavailable: ${command_name}"
done
if [[ -n "${EXPECTED_SHA}" && ! "${EXPECTED_SHA}" =~ ^[0-9a-f]{40,64}$ ]]; then
    fail "requested release SHA is invalid"
fi

cd "${REPOSITORY_ROOT}"
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] \
    || fail "the Git worktree must be clean, including untracked files"
[[ "$(git branch --show-current)" == main ]] \
    || fail "official releases must be qualified from main"
[[ "$(git rev-parse --is-shallow-repository)" == false ]] \
    || fail "official releases require a complete, non-shallow Git history"

RELEASE_SHA="$(git rev-parse HEAD)"
[[ "${RELEASE_SHA}" =~ ^[0-9a-f]{40,64}$ ]] \
    || fail "Git did not return a full hexadecimal Commit ID"
if [[ -n "${EXPECTED_SHA}" && "${RELEASE_SHA}" != "${EXPECTED_SHA}" ]]; then
    fail "HEAD does not match the requested release SHA"
fi
[[ -z "$(git ls-files --stage | awk '$1 == "160000" {print $4}')" ]] \
    || fail "submodules require an explicit project release policy"
if git grep -n 'filter=lfs' "${RELEASE_SHA}" -- ':(glob)**/.gitattributes' >/dev/null 2>&1; then
    fail "Git LFS requires an explicit project release policy"
fi

docker info >/dev/null 2>&1 || fail "Docker Engine is unavailable"
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
PYTEST_VERSION="$(
    "${QUALIFICATION_PYTHON}" -c 'import importlib.metadata; print(importlib.metadata.version("pytest"))'
)" || fail "the prepared release environment does not contain pytest"
[[ "${PYTEST_VERSION}" == "${REQUIRED_PYTEST_VERSION}" ]] \
    || fail "pytest ${REQUIRED_PYTEST_VERSION} is required, found ${PYTEST_VERSION}"

TEST_DATABASE_CONTAINER="inthub-qualification-postgres-${RELEASE_SHA:0:12}-$$"
docker run \
    --detach \
    --rm \
    --platform "${TARGET_PLATFORM}" \
    --name "${TEST_DATABASE_CONTAINER}" \
    --env POSTGRES_DB=inthub_test \
    --env POSTGRES_USER=inthub_test \
    --env POSTGRES_PASSWORD=inthub_test_password \
    --publish 127.0.0.1::5432 \
    "${DATABASE_IMAGE}" >/dev/null
TEST_DATABASE_READY=false
for _ in $(seq 1 60); do
    if docker exec "${TEST_DATABASE_CONTAINER}" \
        pg_isready --username inthub_test --dbname inthub_test >/dev/null 2>&1; then
        TEST_DATABASE_READY=true
        break
    fi
    if [[ "$(docker inspect --format '{{.State.Running}}' "${TEST_DATABASE_CONTAINER}" 2>/dev/null || true)" != true ]]; then
        break
    fi
    sleep 1
done
if [[ "${TEST_DATABASE_READY}" != true ]]; then
    docker logs "${TEST_DATABASE_CONTAINER}" >&2 || true
    fail "the qualification PostgreSQL container did not become ready"
fi
TEST_DATABASE_PORT="$(
    docker port "${TEST_DATABASE_CONTAINER}" 5432/tcp | awk -F: '/127\.0\.0\.1:/ {print $NF; exit}'
)"
[[ "${TEST_DATABASE_PORT}" =~ ^[1-9][0-9]*$ ]] \
    || fail "could not resolve the qualification PostgreSQL port"
INTHUB_TEST_POSTGRES_URL="postgresql://inthub_test:inthub_test_password@127.0.0.1:${TEST_DATABASE_PORT}/inthub_test" \
    "${QUALIFICATION_PYTHON}" -m pytest -q
docker rm --force "${TEST_DATABASE_CONTAINER}" >/dev/null
TEST_DATABASE_CONTAINER=""

git diff --check
git show --check --format= "${RELEASE_SHA}" >/dev/null
mkdir -p "${QUALIFICATION_ROOT}"
SOURCE_DIRECTORY="$(mktemp -d "${QUALIFICATION_ROOT}/.source.${RELEASE_SHA}.XXXXXX")"
git archive --format=tar.gz --prefix="Intent-${RELEASE_SHA}/" "${RELEASE_SHA}" \
    > "${SOURCE_DIRECTORY}/source.tar.gz"
mkdir "${SOURCE_DIRECTORY}/context"
tar -xzf "${SOURCE_DIRECTORY}/source.tar.gz" \
    --strip-components=1 \
    -C "${SOURCE_DIRECTORY}/context"
python3 "${SCRIPT_DIR}/release_manifest.py" scan \
    --source "${SOURCE_DIRECTORY}/context" >/dev/null

[[ "$(git rev-parse HEAD)" == "${RELEASE_SHA}" \
    && -z "$(git status --porcelain=v1 --untracked-files=all)" ]] \
    || fail "the repository changed while qualification was running"
printf '%s\n' "${RELEASE_SHA}"
