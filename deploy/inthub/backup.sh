#!/usr/bin/env bash
# Daily encrypted IntHub backups, one copy on the production host and one elsewhere.
#
#   dump     production, daily: dump PostgreSQL, verify, encrypt, keep 14 days
#   serve    production: SSH forced command for the off-site host's key
#   status   production, hourly: publish disk and backup state for the monitor
#   pull     off-site host, daily: fetch the newest backup, verify, keep 30 days
#   install  source|offsite: write the systemd units for one side
#
# The off-site host pulls, so a compromised production host cannot reach its copies.
# It only ever holds ciphertext: the passphrase lives on production and with the owner.
set -Eeuo pipefail
umask 077

ROOT="/opt/inthub"
DAILY="${ROOT}/backups/daily"
PASSPHRASE_FILE="${ROOT}/shared/backup.passphrase"
STATUS_DIRECTORY="/var/lib/inthub-status"
OFFSITE_DIRECTORY="/var/backups/inthub"
OFFSITE_KEY="/root/.ssh/inthub_backup_pull"
OFFSITE_ENV="/etc/inthub-backup.env"
KEEP_SOURCE_DAYS=14
KEEP_OFFSITE_DAYS=30
DISK_LIMIT_PERCENT=85
STALE_MINUTES=1560
NAME_PATTERN='^inthub-[0-9]{8}T[0-9]{6}Z\.dump\.gpg$'

fail() {
    printf 'inthub-backup: %s\n' "$*" >&2
    exit 1
}

newest_backup() {
    find "$1" -maxdepth 1 -type f -name 'inthub-*.dump.gpg' -printf '%f\n' | grep -E "${NAME_PATTERN}" | sort | tail -n 1
}

cmd_dump() {
    [[ -s "${PASSPHRASE_FILE}" ]] || fail "missing ${PASSPHRASE_FILE}"
    mkdir -p "${DAILY}"
    local name
    name="inthub-$(date -u +%Y%m%dT%H%M%SZ).dump.gpg"
    # Global: the EXIT trap runs after this function has returned.
    work="$(mktemp -d "${DAILY}/.work.XXXXXX")"
    trap 'gpgconf --homedir "${work}" --kill gpg-agent 2>/dev/null || true; rm -rf "${work}"' EXIT

    docker exec inthub-postgres sh -c \
        'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_dump --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --format=custom' \
        > "${work}/inthub.dump"
    [[ -s "${work}/inthub.dump" ]] || fail "PostgreSQL dump is empty"
    docker exec -i inthub-postgres pg_restore --list < "${work}/inthub.dump" > /dev/null

    gpg --homedir "${work}" --batch --quiet --pinentry-mode loopback \
        --passphrase-file "${PASSPHRASE_FILE}" --symmetric --cipher-algo AES256 \
        --output "${work}/${name}" "${work}/inthub.dump"
    (cd "${work}" && sha256sum "${name}" > "${name}.sha256")
    mv "${work}/${name}.sha256" "${DAILY}/"
    mv "${work}/${name}" "${DAILY}/"
    find "${DAILY}" -maxdepth 1 -type f -name 'inthub-*.dump.gpg*' -mtime +"${KEEP_SOURCE_DAYS}" -delete
}

cmd_serve() {
    local request="${SSH_ORIGINAL_COMMAND:-}" name
    case "${request}" in
        latest)
            name="$(newest_backup "${DAILY}")"
            [[ -n "${name}" ]] || fail "no backup yet"
            tar -C "${DAILY}" -cf - "${name}" "${name}.sha256"
            ;;
        "ack "*)
            name="${request#ack }"
            [[ "${name}" =~ ${NAME_PATTERN} && -f "${DAILY}/${name}" ]] || fail "unknown backup"
            printf '%s\n' "${name}" > "${DAILY}/.offsite-ack"
            ;;
        *)
            fail "refused"
            ;;
    esac
}

cmd_status() {
    local disk=ok backup=ok offsite=ok used temporary
    used="$(df --output=pcent "${ROOT}" | tail -n 1 | tr -dc '0-9')"
    (( used < DISK_LIMIT_PERCENT )) || disk=low
    [[ -n "$(find "${DAILY}" -maxdepth 1 -type f -name 'inthub-*.dump.gpg' -mmin "-${STALE_MINUTES}" | head -n 1)" ]] || backup=stale
    [[ -n "$(find "${DAILY}" -maxdepth 1 -type f -name '.offsite-ack' -mmin "-${STALE_MINUTES}")" ]] || offsite=stale
    temporary="$(mktemp "${STATUS_DIRECTORY}/.status.XXXXXX")"
    printf '{"disk":"%s","backup":"%s","offsite":"%s","checked_at":"%s"}\n' \
        "${disk}" "${backup}" "${offsite}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "${temporary}"
    chmod 0644 "${temporary}"
    mv "${temporary}" "${STATUS_DIRECTORY}/status.json"
}

cmd_pull() {
    # shellcheck disable=SC1090
    source "${OFFSITE_ENV}"
    [[ -n "${INTHUB_BACKUP_SOURCE:-}" ]] || fail "INTHUB_BACKUP_SOURCE is not set in ${OFFSITE_ENV}"
    mkdir -p "${OFFSITE_DIRECTORY}"
    local name
    local remote=(ssh -i "${OFFSITE_KEY}" -o BatchMode=yes -o IdentitiesOnly=yes "${INTHUB_BACKUP_SOURCE}")
    work="$(mktemp -d "${OFFSITE_DIRECTORY}/.work.XXXXXX")"
    trap 'rm -rf "${work}"' EXIT
    "${remote[@]}" latest | tar -xf - -C "${work}"
    name="$(newest_backup "${work}")"
    [[ -n "${name}" ]] || fail "the source sent no backup"
    (cd "${work}" && sha256sum --check --quiet "${name}.sha256")
    mv "${work}/${name}.sha256" "${OFFSITE_DIRECTORY}/"
    mv "${work}/${name}" "${OFFSITE_DIRECTORY}/"
    "${remote[@]}" "ack ${name}"
    find "${OFFSITE_DIRECTORY}" -maxdepth 1 -type f -name 'inthub-*.dump.gpg*' -mtime +"${KEEP_OFFSITE_DAYS}" -delete
}

write_timer() {
    local unit="$1" description="$2" user="$3" command="$4" calendar="$5"
    cat > "/etc/systemd/system/${unit}.service" <<EOF
[Unit]
Description=${description}
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=${user}
ExecStart=${command}
EOF
    cat > "/etc/systemd/system/${unit}.timer" <<EOF
[Unit]
Description=${description}

[Timer]
OnCalendar=${calendar}
Persistent=true
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
EOF
    chmod 0644 "/etc/systemd/system/${unit}.service" "/etc/systemd/system/${unit}.timer"
    systemctl daemon-reload
    systemctl enable --now "${unit}.timer"
}

cmd_install() {
    [[ "$(id -u)" -eq 0 ]] || fail "install needs root"
    case "${1:-}" in
        source)
            install -d -o ubuntu -g ubuntu -m 0755 "${STATUS_DIRECTORY}"
            write_timer inthub-backup "IntHub daily backup" ubuntu "${ROOT}/deploy/backup.sh dump" "*-*-* 03:20:00 Asia/Shanghai"
            write_timer inthub-backup-status "IntHub backup status" ubuntu "${ROOT}/deploy/backup.sh status" "hourly"
            ;;
        offsite)
            write_timer inthub-backup-pull "IntHub off-site backup pull" root "/usr/local/sbin/inthub-backup pull" "*-*-* 04:20:00 Asia/Shanghai"
            ;;
        *)
            fail "usage: backup.sh install source|offsite"
            ;;
    esac
}

case "${1:-}" in
    dump | serve | status | pull) "cmd_$1" ;;
    install) cmd_install "${2:-}" ;;
    *) fail "usage: backup.sh dump|serve|status|pull|install" ;;
esac
