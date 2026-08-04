#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "$#" -ne 3 ]]; then
    echo "Usage: remote-release.sh <remote-root> <release-sha> <lock-token>" >&2
    exit 2
fi

REMOTE_ROOT="$1"
RELEASE_SHA="$2"
LOCK_TOKEN="$3"
SCRIPT_DIRECTORY="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASE_LOCK="${REMOTE_ROOT}/.release-lock"
SHARED_ENV="${REMOTE_ROOT}/shared/inthub.env"
RELEASES_ROOT="${REMOTE_ROOT}/releases"
RELEASE_DIRECTORY="${RELEASES_ROOT}/${RELEASE_SHA}"
CURRENT_LINK="${REMOTE_ROOT}/current"
BACKUPS_ROOT="${REMOTE_ROOT}/backups"
CADDY_SITE="/etc/caddy/sites-enabled/inthub.caddy"
PUBLIC_URL="https://inthub.tenon.asia"
PRIVATE_NETWORK="inthub-private"
PREVIOUS_DIRECTORY=""
PREVIOUS_CONTAINER=""
PREVIOUS_PORT=""
CANDIDATE_CONTAINER=""
CANDIDATE_PORT=""
CANDIDATE_SLOT=""
BACKUP_DIRECTORY=""
CADDY_BACKUP=""
CADDY_SWITCHED=false
CURRENT_SWITCHED=false
ROLLBACK_ARMED=false
RELEASE_ACCEPTED=false

fail() {
    echo "IntHub remote release failed: $*" >&2
    return 1
}

docker_command() {
    sudo -n docker "$@"
}

compose_release() {
    local project_name="$1"
    local release_directory="$2"
    local release_sha="$3"
    local release_version="$4"
    local app_container="$5"
    local bind_port="$6"
    shift 6
    sudo -n env \
        "INTHUB_RELEASE=${release_sha}" \
        "INTHUB_PACKAGE_VERSION=${release_version}" \
        "INTHUB_APP_CONTAINER=${app_container}" \
        "INTHUB_BIND_PORT=${bind_port}" \
        docker compose \
            --project-name "${project_name}" \
            --env-file "${SHARED_ENV}" \
            --file "${release_directory}/compose.yaml" \
            "$@"
}

release_version() {
    python3 - "$1" <<'PY'
import json
import pathlib
import re
import sys

value = json.loads((pathlib.Path(sys.argv[1]) / "manifest.json").read_text(encoding="utf-8"))["version"]
if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", value) is None:
    raise SystemExit("invalid release version")
print(value)
PY
}

container_running() {
    [[ "$(docker_command inspect --format '{{.State.Running}}' "$1" 2>/dev/null || true)" == true ]]
}

wait_for_database() {
    local health=""
    for _ in $(seq 1 60); do
        health="$(docker_command inspect --format '{{.State.Health.Status}}' inthub-postgres 2>/dev/null || true)"
        [[ "${health}" == healthy ]] && return 0
        sleep 2
    done
    docker_command logs --tail 120 inthub-postgres >&2 || true
    return 1
}

wait_for_app() {
    local container="$1"
    local port="$2"
    local health=""
    for _ in $(seq 1 60); do
        health="$(docker_command inspect --format '{{.State.Health.Status}}' "${container}" 2>/dev/null || true)"
        if [[ "${health}" == healthy ]] \
            && curl --fail --silent --show-error --max-time 5 \
                "http://127.0.0.1:${port}/readyz" >/dev/null; then
            return 0
        fi
        sleep 2
    done
    docker_command logs --tail 120 "${container}" >&2 || true
    return 1
}

render_caddy() {
    local source_file="$1"
    local target_file="$2"
    local port="$3"
    python3 - "${source_file}" "${target_file}" "${port}" <<'PY'
import pathlib
import sys

source = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
needle = "reverse_proxy 127.0.0.1:7250"
if source.count(needle) != 1:
    raise SystemExit("IntHub Caddy template must contain exactly one canonical upstream")
port = sys.argv[3]
if port not in {"7250", "7251"}:
    raise SystemExit("candidate port is outside the IntHub slot set")
pathlib.Path(sys.argv[2]).write_text(
    source.replace(needle, f"reverse_proxy 127.0.0.1:{port}"),
    encoding="utf-8",
)
PY
}

restore_current() {
    if [[ "${CURRENT_SWITCHED}" != true ]]; then
        return 0
    fi
    if [[ "${PREVIOUS_DIRECTORY}" == "${RELEASES_ROOT}"/* ]]; then
        local rollback_link="${REMOTE_ROOT}/.current.rollback.${LOCK_TOKEN}"
        rm -f "${rollback_link}"
        ln -s "${PREVIOUS_DIRECTORY}" "${rollback_link}"
        mv -Tf "${rollback_link}" "${CURRENT_LINK}"
    elif [[ "$(readlink -f "${CURRENT_LINK}" 2>/dev/null || true)" == "${RELEASE_DIRECTORY}" ]]; then
        rm -f "${CURRENT_LINK}"
    fi
}

restore_caddy() {
    if [[ "${CADDY_SWITCHED}" != true ]]; then
        return 0
    fi
    if [[ -n "${CADDY_BACKUP}" && -f "${CADDY_BACKUP}" ]]; then
        sudo -n install -m 0644 -o root -g root "${CADDY_BACKUP}" "${CADDY_SITE}"
    else
        sudo -n rm -f "${CADDY_SITE}"
    fi
    sudo -n caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
    sudo -n systemctl reload caddy
}

rollback_release() {
    local exit_code="$?"
    trap - ERR HUP INT TERM
    set +e
    if [[ "${ROLLBACK_ARMED}" == true && "${RELEASE_ACCEPTED}" != true ]]; then
        echo "IntHub acceptance failed; restoring the previous traffic boundary." >&2
        restore_caddy || echo "CRITICAL: failed to restore the previous IntHub Caddy site." >&2
        restore_current || echo "CRITICAL: failed to restore the previous current pointer." >&2
        if [[ -n "${CANDIDATE_CONTAINER}" ]]; then
            docker_command rm --force "${CANDIDATE_CONTAINER}" >/dev/null 2>&1 || \
                echo "CRITICAL: failed to stop the rejected IntHub candidate." >&2
        fi
        if [[ -n "${PREVIOUS_CONTAINER}" ]] && ! container_running "${PREVIOUS_CONTAINER}"; then
            echo "CRITICAL: the previous IntHub application is not running after rollback." >&2
        fi
    fi
    if [[ -f "${RELEASE_LOCK}/owner" \
        && "$(cat "${RELEASE_LOCK}/owner" 2>/dev/null)" == "${LOCK_TOKEN}" ]]; then
        rm -f "${RELEASE_LOCK}/owner" "${RELEASE_LOCK}/metadata"
        rmdir "${RELEASE_LOCK}" 2>/dev/null || true
    fi
    exit "${exit_code}"
}
trap rollback_release EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'false' ERR

[[ "${REMOTE_ROOT}" =~ ^/[A-Za-z0-9._/-]+$ && "${REMOTE_ROOT}" != *".."* ]] \
    || fail "remote root is unsafe"
[[ "${RELEASE_SHA}" =~ ^[0-9a-f]{40,64}$ ]] || fail "release SHA is invalid"
[[ "${LOCK_TOKEN}" =~ ^[A-Za-z0-9._-]+$ ]] || fail "lock token is invalid"
[[ -f "${RELEASE_LOCK}/owner" ]] || fail "release lock owner is missing"
[[ "$(cat "${RELEASE_LOCK}/owner")" == "${LOCK_TOKEN}" ]] \
    || fail "release lock is not owned by this operation"
[[ "${SCRIPT_DIRECTORY}" == "${REMOTE_ROOT}/incoming/"* ]] \
    || fail "release bundle is outside the project incoming directory"
for deployment_path in \
    "${REMOTE_ROOT}" \
    "${REMOTE_ROOT}/incoming" \
    "${RELEASES_ROOT}" \
    "${BACKUPS_ROOT}" \
    "${REMOTE_ROOT}/shared"; do
    [[ -d "${deployment_path}" && ! -L "${deployment_path}" ]] \
        || fail "deployment directory is missing or symlinked: ${deployment_path}"
done
[[ -f "${SHARED_ENV}" && ! -L "${SHARED_ENV}" ]] \
    || fail "production env is missing, non-regular, or symlinked"
[[ "$(stat -c '%a' "${SHARED_ENV}")" == 600 ]] \
    || fail "production env must have mode 0600"
if sudo -n test -e "${CADDY_SITE}"; then
    sudo -n test -f "${CADDY_SITE}" || fail "IntHub Caddy site is not a regular file"
    ! sudo -n test -L "${CADDY_SITE}" || fail "IntHub Caddy site must not be a symlink"
fi

for command_name in curl gzip python3 sha256sum; do
    command -v "${command_name}" >/dev/null 2>&1 \
        || fail "required production command is unavailable: ${command_name}"
done
sudo -n docker version >/dev/null
sudo -n docker compose version >/dev/null
sudo -n caddy version >/dev/null
sudo -n systemctl is-active caddy >/dev/null

python3 "${SCRIPT_DIRECTORY}/release_manifest.py" verify \
    --bundle "${SCRIPT_DIRECTORY}" \
    --expected-sha "${RELEASE_SHA}" >/dev/null

mkdir -p "${RELEASES_ROOT}" "${BACKUPS_ROOT}"
if [[ -e "${RELEASE_DIRECTORY}" ]]; then
    [[ -d "${RELEASE_DIRECTORY}" && ! -L "${RELEASE_DIRECTORY}" ]] \
        || fail "existing release path is not a regular directory"
    EXISTING_MANIFEST_SHA="$(sha256sum "${RELEASE_DIRECTORY}/manifest.json" | awk '{print $1}')"
    INCOMING_MANIFEST_SHA="$(sha256sum "${SCRIPT_DIRECTORY}/manifest.json" | awk '{print $1}')"
    [[ "${EXISTING_MANIFEST_SHA}" == "${INCOMING_MANIFEST_SHA}" ]] \
        || fail "existing release has different immutable content"
    python3 "${RELEASE_DIRECTORY}/release_manifest.py" verify \
        --bundle "${RELEASE_DIRECTORY}" \
        --expected-sha "${RELEASE_SHA}" >/dev/null
    BUNDLE_TO_REMOVE="${SCRIPT_DIRECTORY}"
    SCRIPT_DIRECTORY="${RELEASE_DIRECTORY}"
    rm -rf -- "${BUNDLE_TO_REMOVE}"
else
    mv "${SCRIPT_DIRECTORY}" "${RELEASE_DIRECTORY}"
    SCRIPT_DIRECTORY="${RELEASE_DIRECTORY}"
    chmod -R a-w "${RELEASE_DIRECTORY}"
fi

python3 "${SCRIPT_DIRECTORY}/release_manifest.py" verify \
    --bundle "${SCRIPT_DIRECTORY}" \
    --expected-sha "${RELEASE_SHA}" >/dev/null
RELEASE_VERSION="$(release_version "${SCRIPT_DIRECTORY}")"

mapfile -t IMAGE_EXPECTATIONS < <(
    python3 - "${SCRIPT_DIRECTORY}/manifest.json" <<'PY'
import json
import pathlib
import re
import sys

manifest = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
for role in ("app", "database"):
    image = manifest["images"][role]
    values = (image["reference"], image["id"], image["os"], image["architecture"])
    if any(not isinstance(value, str) for value in values):
        raise SystemExit("invalid image metadata")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/:@+-]*", image["reference"]) is None:
        raise SystemExit("unsafe image reference")
    print("\t".join(values))
PY
)
[[ "${#IMAGE_EXPECTATIONS[@]}" -eq 2 ]] || fail "manifest image metadata is incomplete"
IFS=$'\t' read -r APP_IMAGE_REFERENCE EXPECTED_APP_ID EXPECTED_APP_OS EXPECTED_APP_ARCHITECTURE \
    <<< "${IMAGE_EXPECTATIONS[0]}"
IFS=$'\t' read -r DATABASE_IMAGE_REFERENCE EXPECTED_DATABASE_ID EXPECTED_DATABASE_OS EXPECTED_DATABASE_ARCHITECTURE \
    <<< "${IMAGE_EXPECTATIONS[1]}"

PREVIOUS_DIRECTORY="$(readlink -f "${CURRENT_LINK}" 2>/dev/null || true)"
if [[ -n "${PREVIOUS_DIRECTORY}" && "${PREVIOUS_DIRECTORY}" != "${RELEASES_ROOT}"/* ]]; then
    fail "current points outside the IntHub release root"
fi

if sudo -n test -f "${CADDY_SITE}"; then
    mapfile -t ACTIVE_PORTS < <(
        sudo -n awk '/^[[:space:]]*reverse_proxy[[:space:]]+127\.0\.0\.1:(7250|7251)[[:space:]]*$/ { sub(/^.*:/, "", $2); print $2 }' \
            "${CADDY_SITE}"
    )
    [[ "${#ACTIVE_PORTS[@]}" -eq 1 ]] || fail "installed IntHub Caddy site has an unknown upstream"
    PREVIOUS_PORT="${ACTIVE_PORTS[0]}"
    if [[ "${PREVIOUS_PORT}" == 7250 ]]; then
        CANDIDATE_PORT=7251
        CANDIDATE_SLOT=green
        if container_running inthub-app-blue; then
            PREVIOUS_CONTAINER=inthub-app-blue
        elif container_running inthub-app; then
            PREVIOUS_CONTAINER=inthub-app
        fi
    else
        CANDIDATE_PORT=7250
        CANDIDATE_SLOT=blue
        container_running inthub-app-green && PREVIOUS_CONTAINER=inthub-app-green
    fi
    [[ -n "${PREVIOUS_CONTAINER}" ]] \
        || fail "Caddy points to a slot without a running IntHub application"
else
    [[ -z "${PREVIOUS_DIRECTORY}" ]] \
        || fail "current exists but the IntHub Caddy site is missing"
    CANDIDATE_PORT=7250
    CANDIDATE_SLOT=blue
fi
CANDIDATE_CONTAINER="inthub-app-${CANDIDATE_SLOT}"

if [[ "${PREVIOUS_DIRECTORY}" == "${RELEASE_DIRECTORY}" ]]; then
    [[ -n "${PREVIOUS_CONTAINER}" ]] || fail "active release has no serving container"
    [[ "$(docker_command inspect --format '{{.Config.Image}}' "${PREVIOUS_CONTAINER}")" \
        == "inthub:${RELEASE_SHA}" ]] \
        || fail "current points to this release but the serving image does not"
    wait_for_app "${PREVIOUS_CONTAINER}" "${PREVIOUS_PORT}" \
        || fail "the active release is not healthy"
    INTHUB_BASE_URL="${PUBLIC_URL}" \
    INTHUB_LOOPBACK_URL="http://127.0.0.1:${PREVIOUS_PORT}" \
        bash "${RELEASE_DIRECTORY}/smoke.sh"
    RELEASE_ACCEPTED=true
    echo "IntHub release ${RELEASE_SHA} is already active and healthy."
    exit 0
fi

BACKUP_TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIRECTORY="$(mktemp -d "${BACKUPS_ROOT}/${BACKUP_TIMESTAMP}-${RELEASE_SHA}.XXXXXX")"
chmod 0700 "${BACKUP_DIRECTORY}"
install -m 0600 "${SHARED_ENV}" "${BACKUP_DIRECTORY}/inthub.env"
install -m 0600 "${RELEASE_DIRECTORY}/manifest.json" "${BACKUP_DIRECTORY}/release-manifest.json"

if docker_command volume inspect inthub-postgres-data >/dev/null 2>&1; then
    [[ "$(docker_command inspect --format '{{.State.Running}}' inthub-postgres 2>/dev/null || true)" == true ]] \
        || fail "the existing PostgreSQL volume cannot be backed up because its container is not running"
    [[ "$(docker_command inspect --format '{{.Image}}' inthub-postgres)" == "${EXPECTED_DATABASE_ID}" ]] \
        || fail "database runtime differs from the immutable lock; use a separate database maintenance procedure"
    docker_command exec inthub-postgres sh -c \
        'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_dump --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --format=custom' \
        > "${BACKUP_DIRECTORY}/inthub.dump"
    chmod 0600 "${BACKUP_DIRECTORY}/inthub.dump"
    [[ -s "${BACKUP_DIRECTORY}/inthub.dump" ]] || fail "PostgreSQL backup is empty"
    docker_command exec -i inthub-postgres pg_restore --list \
        < "${BACKUP_DIRECTORY}/inthub.dump" >/dev/null
fi

gzip -dc "${RELEASE_DIRECTORY}/images.tar.gz" | docker_command load >/dev/null
for expectation in "${IMAGE_EXPECTATIONS[@]}"; do
    IFS=$'\t' read -r image_reference expected_id expected_os expected_architecture \
        <<< "${expectation}"
    actual_id="$(docker_command image inspect --format '{{.Id}}' "${image_reference}")"
    actual_os="$(docker_command image inspect --format '{{.Os}}' "${image_reference}")"
    actual_architecture="$(docker_command image inspect --format '{{.Architecture}}' "${image_reference}")"
    [[ "${actual_id}" == "${expected_id}" ]] || fail "loaded image ID mismatch for ${image_reference}"
    [[ "${actual_os}/${actual_architecture}" == "${expected_os}/${expected_architecture}" ]] \
        || fail "loaded image platform mismatch for ${image_reference}"
done

APP_REVISION="$(
    docker_command image inspect \
        --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' \
        "inthub:${RELEASE_SHA}"
)"
APP_VERSION="$(
    docker_command image inspect \
        --format '{{index .Config.Labels "org.opencontainers.image.version"}}' \
        "inthub:${RELEASE_SHA}"
)"
[[ "${APP_REVISION}" == "${RELEASE_SHA}" ]] || fail "application revision label mismatch"
[[ "${APP_VERSION}" == "${RELEASE_VERSION}" ]] || fail "application version label mismatch"

if ! docker_command network inspect "${PRIVATE_NETWORK}" >/dev/null 2>&1; then
    docker_command network create "${PRIVATE_NETWORK}" >/dev/null
fi
[[ "$(docker_command network inspect --format '{{.Driver}}/{{.Scope}}' "${PRIVATE_NETWORK}")" == bridge/local ]] \
    || fail "the IntHub private network has an unexpected driver or scope"

# Keep the database in the stable project and start the application in the
# inactive slot. The current serving container remains untouched throughout
# candidate health and public acceptance.
if ! container_running inthub-postgres; then
    compose_release \
        inthub \
        "${RELEASE_DIRECTORY}" "${RELEASE_SHA}" "${RELEASE_VERSION}" \
        inthub-app-bootstrap 7259 \
        up --detach --no-build --pull never database
fi
wait_for_database || fail "PostgreSQL did not become healthy"
[[ "$(docker_command inspect --format '{{if index .NetworkSettings.Networks "inthub-private"}}attached{{end}}' inthub-postgres)" \
    == attached ]] || fail "PostgreSQL is not attached to the IntHub private network"

ROLLBACK_ARMED=true
compose_release \
    "inthub-${CANDIDATE_SLOT}" \
    "${RELEASE_DIRECTORY}" "${RELEASE_SHA}" "${RELEASE_VERSION}" \
    "${CANDIDATE_CONTAINER}" "${CANDIDATE_PORT}" \
    up --detach --no-deps --no-build --pull never --force-recreate app
wait_for_app "${CANDIDATE_CONTAINER}" "${CANDIDATE_PORT}" \
    || fail "candidate application did not become healthy"

CADDY_CANDIDATE="${BACKUP_DIRECTORY}/inthub.caddy.candidate"
render_caddy "${RELEASE_DIRECTORY}/inthub.caddy" "${CADDY_CANDIDATE}" "${CANDIDATE_PORT}"
chmod 0600 "${CADDY_CANDIDATE}"
if sudo -n test -f "${CADDY_SITE}"; then
    CADDY_BACKUP="${BACKUP_DIRECTORY}/inthub.caddy"
    sudo -n cp "${CADDY_SITE}" "${CADDY_BACKUP}"
    sudo -n chown "$(id -u):$(id -g)" "${CADDY_BACKUP}"
    chmod 0600 "${CADDY_BACKUP}"
fi
CADDY_SWITCHED=true
sudo -n install -m 0644 -o root -g root "${CADDY_CANDIDATE}" "${CADDY_SITE}"
sudo -n caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
sudo -n systemctl reload caddy

INTHUB_BASE_URL="${PUBLIC_URL}" \
INTHUB_LOOPBACK_URL="http://127.0.0.1:${CANDIDATE_PORT}" \
    bash "${RELEASE_DIRECTORY}/smoke.sh"

CURRENT_CANDIDATE="${REMOTE_ROOT}/.current.${LOCK_TOKEN}"
rm -f "${CURRENT_CANDIDATE}"
ln -s "${RELEASE_DIRECTORY}" "${CURRENT_CANDIDATE}"
mv -Tf "${CURRENT_CANDIDATE}" "${CURRENT_LINK}"
CURRENT_SWITCHED=true

[[ "$(readlink -f "${CURRENT_LINK}")" == "${RELEASE_DIRECTORY}" ]] \
    || fail "current did not switch to the accepted release"
[[ "$(docker_command inspect --format '{{.Config.Image}}' "${CANDIDATE_CONTAINER}")" \
    == "inthub:${RELEASE_SHA}" ]] \
    || fail "serving application image does not match current"

RELEASE_ACCEPTED=true
ROLLBACK_ARMED=false
if [[ -n "${PREVIOUS_CONTAINER}" ]]; then
    docker_command stop "${PREVIOUS_CONTAINER}" >/dev/null \
        || echo "WARNING: the inactive previous IntHub container could not be stopped." >&2
fi
echo "IntHub release ${RELEASE_SHA} passed candidate, traffic-switch, and public acceptance."
