#!/usr/bin/env bash
# Watches the hosted IntHub from the off-site backup host, every five minutes.
# Two failed rounds in a row send one alert, a long outage sends a reminder,
# and recovery sends one more. The webhook lives in /etc/inthub-monitor.env.
#
#   check    run one round
#   test     send a test message to the webhook
#   install  write the systemd units
set -Eeuo pipefail
umask 077

BASE_URL="https://inthub.tenon.asia"
STATE_DIRECTORY="/var/lib/inthub-monitor"
ENV_FILE="/etc/inthub-monitor.env"
BACKUP_DIRECTORY="/var/backups/inthub"
FAILURES_BEFORE_ALERT=2
REMINDER_MINUTES=360
STATUS_MAX_AGE_MINUTES=120
BACKUP_MAX_AGE_MINUTES=1560

fail() {
    printf 'inthub-monitor: %s\n' "$*" >&2
    exit 1
}

notify() {
    # shellcheck disable=SC1090
    [[ -f "${ENV_FILE}" ]] && source "${ENV_FILE}"
    if [[ -z "${INTHUB_ALERT_WEBHOOK:-}" ]]; then
        printf 'inthub-monitor: no webhook, not sent: %s\n' "$1" >&2
        return 0
    fi
    # Feishu and Lark take one shape; WeCom and DingTalk take the other.
    python3 - "$1" "${INTHUB_ALERT_WEBHOOK}" <<'PY' \
        | curl --fail --silent --show-error --max-time 15 -H 'Content-Type: application/json' \
            --data-binary @- "${INTHUB_ALERT_WEBHOOK}" > /dev/null
import json
import sys

text, url = sys.argv[1:3]
feishu = "feishu" in url or "larksuite" in url
print(json.dumps({"msg_type": "text", "content": {"text": text}} if feishu
                 else {"msgtype": "text", "text": {"content": text}}, ensure_ascii=False))
PY
}

# Prints one line per problem, and nothing when all is well.
find_problems() {
    curl --fail --silent --max-time 15 "${BASE_URL}/readyz" > /dev/null || echo "服务未就绪（/readyz）"
    local status
    if status="$(curl --fail --silent --max-time 15 "${BASE_URL}/status.json")"; then
        python3 - "${status}" "${STATUS_MAX_AGE_MINUTES}" <<'PY'
import json
import sys
from datetime import datetime, timezone

status, limit = json.loads(sys.argv[1]), int(sys.argv[2])
checked = datetime.fromisoformat(status["checked_at"].replace("Z", "+00:00"))
if (datetime.now(timezone.utc) - checked).total_seconds() > limit * 60:
    print(f"生产机状态超过 {limit} 分钟没有更新")
for field, label in (("disk", "磁盘"), ("backup", "生产机备份"), ("offsite", "异地备份")):
    if status.get(field) != "ok":
        print(f"{label}异常：{status.get(field)}")
PY
    else
        echo "读不到 /status.json"
    fi
    [[ -n "$(find "${BACKUP_DIRECTORY}" -maxdepth 1 -type f -name 'inthub-*.dump.gpg' -mmin "-${BACKUP_MAX_AGE_MINUTES}" | head -n 1)" ]] \
        || echo "备份机上没有最近 26 小时内的备份"
}

cmd_check() {
    mkdir -p "${STATE_DIRECTORY}"
    local failures_file="${STATE_DIRECTORY}/failures" alerted_file="${STATE_DIRECTORY}/alerted"
    local problems failures
    problems="$(find_problems)"
    if [[ -z "${problems}" ]]; then
        [[ ! -e "${alerted_file}" ]] || notify "IntHub 已恢复"
        rm -f "${failures_file}" "${alerted_file}"
        return 0
    fi
    failures=$(( $(cat "${failures_file}" 2>/dev/null || echo 0) + 1 ))
    printf '%s\n' "${failures}" > "${failures_file}"
    (( failures >= FAILURES_BEFORE_ALERT )) || return 0
    if [[ -z "$(find "${alerted_file}" -mmin "-${REMINDER_MINUTES}" 2>/dev/null)" ]]; then
        notify "IntHub 告警（连续 ${failures} 轮）
${problems}"
        touch "${alerted_file}"
    fi
}

cmd_install() {
    [[ "$(id -u)" -eq 0 ]] || fail "install needs root"
    cat > /etc/systemd/system/inthub-monitor.service <<'EOF'
[Unit]
Description=IntHub outside monitor
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/inthub-monitor check
EOF
    cat > /etc/systemd/system/inthub-monitor.timer <<'EOF'
[Unit]
Description=IntHub outside monitor

[Timer]
OnCalendar=*:0/5
RandomizedDelaySec=20

[Install]
WantedBy=timers.target
EOF
    chmod 0644 /etc/systemd/system/inthub-monitor.service /etc/systemd/system/inthub-monitor.timer
    systemctl daemon-reload
    systemctl enable --now inthub-monitor.timer
}

case "${1:-}" in
    check) cmd_check ;;
    test) notify "IntHub 告警测试：能收到这条，说明告警通道正常" ;;
    install) cmd_install ;;
    *) fail "usage: monitor.sh check|test|install" ;;
esac
