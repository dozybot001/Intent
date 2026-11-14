#!/usr/bin/env bash
# Keeps the three newest release environments that prepare-release-env.sh built
# and removes older ones. release.sh runs it after a release is accepted; it
# warns instead of failing, because the release is already live.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL_ROOT="${INTHUB_RELEASE_TOOL_ROOT:-${SCRIPT_DIR}/../../dist/inthub-tools}"
KEEP=3

[[ -d "${TOOL_ROOT}" ]] || exit 0
count=0
while IFS= read -r environment; do
    count=$((count + 1))
    if ((count > KEEP)); then
        rm -rf -- "${environment}" \
            || echo "IntHub release environment was not removed: ${environment}" >&2
    fi
done < <(ls -dt -- "${TOOL_ROOT}"/cpython-*/ 2>/dev/null)
exit 0
