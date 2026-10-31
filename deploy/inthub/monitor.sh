#!/usr/bin/env bash
# Watches the hosted IntHub from the off-site backup host, every five minutes.
# Two failed rounds in a row send one alert, a long outage sends a reminder,
# and recovery sends one more, through a Feishu app. Its credentials and the
# group live in /etc/inthub-monitor.env.
#
#   check       run one round
#   test        send a test message
#   set-secret  ask for the app secret on a terminal, store it, send a test
#   install     write the systemd units
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
    set -a
    # shellcheck disable=SC1090
    [[ -f "${ENV_FILE}" ]] && source "${ENV_FILE}"
    set +a
    if [[ -z "${INTHUB_FEISHU_APP_SECRET:-}" ]]; then
        printf 'inthub-monitor: no Feishu credentials, not sent: %s\n' "$1" >&2
        return 0
    fi
    python3 - "$1" <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

host =os.environ.get("INTHUB_FEISHU_HOST", "https://open.feishu.cn")


def post(path, body, token=None):
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(host + path, json.dumps(body).encode("utf-8"), headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            reply = json.load(response)
    except urllib.error.HTTPError as exc:  # Feishu reports refusals as 400 with a JSON body
        sys.exit(f"inthub-monitor: Feishu returned {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}")
    if reply.get("code"):
        sys.exit(f"inthub-monitor: Feishu refused: {reply.get('code')} {reply.get('msg')}")
    return reply


token = post("/open-apis/auth/v3/tenant_access_token/internal", {
    "app_id": os.environ["INTHUB_FEISHU_APP_ID"],
    "app_secret": os.environ["INTHUB_FEISHU_APP_SECRET"],
})["tenant_access_token"]
post("/open-apis/im/v1/messages?receive_id_type=chat_id", {
    "receive_id": os.environ["INTHUB_FEISHU_CHAT_ID"],
    "msg_type": "text",
    "content": json.dumps({"text": sys.argv[1]}, ensure_ascii=False),
}, token)
PY
}

# Asks for the secret on a terminal, so it never passes through a command line or a chat.
cmd_set_secret() {
    local secret
    read -rs -p "Feishu App Secret: " secret
    echo
    [[ -n "${secret}" ]] || fail "no secret entered"
    sed -i '/^INTHUB_FEISHU_APP_SECRET=/d' "${ENV_FILE}"
    printf 'INTHUB_FEISHU_APP_SECRET=%q\n' "${secret}" >> "${ENV_FILE}"
    notify "IntHub 告警测试：能收到这条，说明告警通道正常"
    echo "Sent. Check the Feishu group."
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
    set-secret) cmd_set_secret ;;
    install) cmd_install ;;
    *) fail "usage: monitor.sh check|test|set-secret|install" ;;
esac
