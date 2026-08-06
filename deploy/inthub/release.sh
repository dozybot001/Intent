#!/usr/bin/env bash
# Stable one-command operator interface. GitHub, cloud CI, and external image
# registries are deliberately outside the production release path.
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "${SCRIPT_DIR}/local-release.sh" "$@"
