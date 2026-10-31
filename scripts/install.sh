#!/usr/bin/env bash
# Install or upgrade the Intent CLI (`itt`) in an isolated environment.
# Uses uv or pipx when available; otherwise a private virtual environment, which
# also works on "externally managed" (PEP 668) Pythons such as Homebrew's or
# Debian's. Re-run to upgrade. Set INTENT_VERSION to pin a different release.
set -euo pipefail

REPO="${INTENT_REPO:-https://github.com/dozybot001/Intent.git}"
RELEASE_TAG="${INTENT_VERSION:-v7.6.7}"
# Releases before 7.1.0 were published under the distribution name intent-cli.
case "$RELEASE_TAG" in
  v[0-6].*|v7.0.*) DIST="intent-cli" ;;
  *) DIST="intent-history" ;;
esac
SPEC="${DIST} @ git+${REPO}@${RELEASE_TAG}"
VENV_DIR="${INTENT_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/intent}/venv"
BIN_DIR="${INTENT_BIN_DIR:-$HOME/.local/bin}"

info() { printf '\033[1;34m[intent]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[intent]\033[0m %s\n' "$*" >&2; exit 1; }

command -v git >/dev/null 2>&1 \
  || die "Git is required to download Intent ${RELEASE_TAG}. Install git, then retry."

PYTHON=""
for cmd in python3 python; do
  if command -v "$cmd" >/dev/null 2>&1 \
    && "$cmd" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    PYTHON="$(command -v "$cmd")"
    break
  fi
done
[ -n "$PYTHON" ] \
  || die "Python 3.9+ not found. Install it (for example 'brew install python' or 'sudo apt install python3'), then retry."
info "Python $("$PYTHON" -c 'import platform; print(platform.python_version())')"

HAVE_UV=0; HAVE_PIPX=0
command -v uv >/dev/null 2>&1 && HAVE_UV=1
if command -v pipx >/dev/null 2>&1 || "$PYTHON" -m pipx --version >/dev/null 2>&1; then HAVE_PIPX=1; fi
pipx_cmd() { if command -v pipx >/dev/null 2>&1; then pipx "$@"; else "$PYTHON" -m pipx "$@"; fi; }

# Intent 7.0 was installed as intent-cli. Remove that install (only one that
# provides `itt`) so a stale second `itt` cannot come back on a later upgrade.
if [ "$DIST" = "intent-history" ]; then
  if [ "$HAVE_UV" = 1 ] && uv tool list 2>/dev/null \
    | awk '/^[^- ]/ {tool=$1} tool=="intent-cli" && $1=="-" && $2=="itt" {found=1} END {exit !found}'; then
    info "Removing the previous intent-cli installation (uv)..."
    uv tool uninstall intent-cli >/dev/null 2>&1 || true
  fi
  if [ "$HAVE_PIPX" = 1 ] && pipx_cmd list --json 2>/dev/null | "$PYTHON" -c '
import json, sys
venv = json.load(sys.stdin).get("venvs", {}).get("intent-cli")
sys.exit(0 if venv and "itt" in venv["metadata"]["main_package"]["apps"] else 1)' 2>/dev/null; then
    info "Removing the previous intent-cli installation (pipx)..."
    pipx_cmd uninstall intent-cli >/dev/null 2>&1 || true
  fi
fi

if [ "$HAVE_UV" = 1 ]; then
  info "Installing Intent ${RELEASE_TAG} with uv..."
  uv tool install --force --python "$PYTHON" "$SPEC"
elif [ "$HAVE_PIPX" = 1 ]; then
  info "Installing Intent ${RELEASE_TAG} with pipx..."
  pipx_cmd install --force --python "$PYTHON" "$SPEC"
else
  info "uv and pipx not found; installing Intent ${RELEASE_TAG} into ${VENV_DIR}..."
  "$PYTHON" -m venv --clear "$VENV_DIR" \
    || die "Could not create a virtual environment. On Debian/Ubuntu run 'sudo apt install python3-venv' (or install pipx), then retry."
  "$VENV_DIR/bin/python" -m pip install --quiet --disable-pip-version-check "$SPEC" \
    || die "pip could not install Intent ${RELEASE_TAG}."
  mkdir -p "$BIN_DIR"
  ln -sf "$VENV_DIR/bin/itt" "$BIN_DIR/itt"
fi

ITT="$(command -v itt || true)"
[ -n "$ITT" ] || ITT="$BIN_DIR/itt"
"$ITT" version >/dev/null 2>&1 || die "Installation finished, but '$ITT version' failed."
info "Installed: $ITT"
case ":$PATH:" in
  *":$(dirname "$ITT"):"*) ;;
  *)
    case "${SHELL##*/}" in
      zsh) RC_FILE="~/.zshrc" ;;
      bash) RC_FILE="~/.bashrc" ;;
      *) RC_FILE="~/.profile" ;;
    esac
    info "Add $(dirname "$ITT") to PATH, e.g. echo 'export PATH=\"$(dirname "$ITT"):\$PATH\"' >> $RC_FILE"
    ;;
esac
info "Next: add the agent skill (needs Node.js): npx skills add dozybot001/Intent -g -a claude-code -a codex -y"
info "Then run 'itt init' in a project."
