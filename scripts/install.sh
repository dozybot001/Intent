#!/usr/bin/env bash
set -euo pipefail

REPO="https://github.com/dozybot001/Intent.git"

info()  { printf '\033[1;34m[intent]\033[0m %s\n' "$*"; }
err()   { printf '\033[1;31m[intent]\033[0m %s\n' "$*" >&2; }

# --- Python ---
PYTHON=""
for cmd in python3 python; do
  if command -v "$cmd" >/dev/null 2>&1; then
    PYTHON="$cmd"
    break
  fi
done

if [ -z "$PYTHON" ]; then
  err "Python not found. Install Python 3.9+ first."
  exit 1
fi

PY_VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$("$PYTHON" -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$("$PYTHON" -c 'import sys; print(sys.version_info.minor)')

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
  err "Python $PY_VERSION found, but 3.9+ is required."
  exit 1
fi
info "Python $PY_VERSION"

# --- pipx ---
if ! command -v pipx >/dev/null 2>&1; then
  info "Installing pipx..."
  "$PYTHON" -m pip install --user pipx 2>/dev/null || "$PYTHON" -m pip install pipx
  "$PYTHON" -m pipx ensurepath 2>/dev/null || true
  export PATH="$HOME/.local/bin:$PATH"
fi
info "pipx $(pipx --version)"

# --- intent-cli ---
info "Installing intent-cli..."
pipx install "intent-cli @ git+${REPO}" --force

info "Done! Run 'itt version' to verify."
info "To add the agent skill: npx skills add dozybot001/Intent -g --all"
