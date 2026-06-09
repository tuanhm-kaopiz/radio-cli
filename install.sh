#!/usr/bin/env bash
set -euo pipefail

APP_NAME="radio-cli"
DEFAULT_REPO="https://github.com/YOUR_USERNAME/radio-cli.git"
REPO_URL="${RADIO_CLI_REPO:-$DEFAULT_REPO}"
BRANCH="${RADIO_CLI_BRANCH:-main}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="${RADIO_CLI_HOME:-$DATA_HOME/$APP_NAME/app}"
VENV_DIR="$APP_DIR/.venv"
LOCAL_BIN_DIR="${RADIO_CLI_BIN_DIR:-$HOME/.local/bin}"
GLOBAL_BIN_DIR="${RADIO_CLI_GLOBAL_BIN_DIR:-/usr/local/bin}"
RADIO_BIN=""

log() { printf '%s\n' "==> $*"; }
warn() { printf '%s\n' "WARN: $*" >&2; }
fail() { printf '%s\n' "ERROR: $*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

run_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif have sudo; then
    sudo "$@"
  else
    return 1
  fi
}

pick_python() {
  for candidate in python3.12 python3.11 python3.10 python3; do
    if have "$candidate" && "$candidate" - <<'PY_CHECK' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY_CHECK
    then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

install_system_deps() {
  local os
  os="$(uname -s 2>/dev/null || printf unknown)"

  if have git && have mpv && pick_python >/dev/null 2>&1; then
    return 0
  fi

  log "Checking system dependencies"
  case "$os" in
    Linux*)
      if have apt-get; then
        run_root apt-get update || warn "apt-get update failed"
        run_root apt-get install -y git python3 python3-venv python3-pip mpv || warn "Could not install all apt packages"
      elif have dnf; then
        run_root dnf install -y git python3 python3-pip mpv || warn "Could not install all dnf packages"
      elif have pacman; then
        run_root pacman -Sy --needed --noconfirm git python python-pip mpv || warn "Could not install all pacman packages"
      elif have zypper; then
        run_root zypper install -y git python3 python3-pip mpv || warn "Could not install all zypper packages"
      else
        warn "No supported Linux package manager found. Please install git, Python >= 3.10, and mpv."
      fi
      ;;
    Darwin*)
      if have brew; then
        brew install git python mpv || warn "Could not install all Homebrew packages"
      else
        warn "Homebrew not found. Please install git, Python >= 3.10, and mpv."
      fi
      ;;
    *)
      warn "Unsupported OS for automatic system packages. Please install git, Python >= 3.10, and mpv."
      ;;
  esac
}

ensure_repo() {
  [ "$REPO_URL" != "$DEFAULT_REPO" ] || warn "Using placeholder repo URL. Set RADIO_CLI_REPO after publishing the repository."

  mkdir -p "$(dirname "$APP_DIR")"
  if [ -d "$APP_DIR/.git" ]; then
    log "Updating $APP_DIR"
    git -C "$APP_DIR" fetch --depth 1 origin "$BRANCH"
    git -C "$APP_DIR" checkout "$BRANCH"
    git -C "$APP_DIR" reset --hard "origin/$BRANCH"
  elif [ -e "$APP_DIR" ]; then
    fail "$APP_DIR already exists and is not a git checkout. Move it or set RADIO_CLI_HOME."
  else
    log "Installing from $REPO_URL"
    git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
  fi
}

ensure_path() {
  local target="$VENV_DIR/bin/radio"

  if [ -d "$GLOBAL_BIN_DIR" ] && run_root ln -sfn "$target" "$GLOBAL_BIN_DIR/radio" 2>/dev/null; then
    RADIO_BIN="$GLOBAL_BIN_DIR/radio"
    return 0
  fi

  mkdir -p "$LOCAL_BIN_DIR"
  ln -sfn "$target" "$LOCAL_BIN_DIR/radio"
  RADIO_BIN="$LOCAL_BIN_DIR/radio"

  case ":$PATH:" in
    *":$LOCAL_BIN_DIR:"*) return 0 ;;
  esac

  local rc_file=""
  if [ -n "${ZSH_VERSION:-}" ]; then
    rc_file="$HOME/.zshrc"
  elif [ -n "${BASH_VERSION:-}" ]; then
    rc_file="$HOME/.bashrc"
  elif [ -f "$HOME/.zshrc" ]; then
    rc_file="$HOME/.zshrc"
  elif [ -f "$HOME/.bashrc" ]; then
    rc_file="$HOME/.bashrc"
  fi

  if [ -n "$rc_file" ]; then
    if ! grep -Fq 'radio-cli installer' "$rc_file" 2>/dev/null; then
      {
        printf '\n# radio-cli installer\n'
        printf 'export PATH="$HOME/.local/bin:$PATH"\n'
      } >> "$rc_file"
      log "Added $LOCAL_BIN_DIR to PATH in $rc_file"
    fi
  else
    warn "$LOCAL_BIN_DIR is not in PATH. Add it to your shell PATH if radio is not found."
  fi
}

main() {
  install_system_deps

  have git || fail "git is required"
  local python_bin
  python_bin="$(pick_python)" || fail "Python >= 3.10 is required"

  ensure_repo

  log "Creating virtual environment"
  "$python_bin" -m venv "$VENV_DIR"

  log "Installing radio-cli"
  "$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
  "$VENV_DIR/bin/python" -m pip install -e "$APP_DIR"

  ensure_path

  log "Installed: $RADIO_BIN"
  "$RADIO_BIN" doctor || true

  printf '\nDone. Open a new terminal if your shell did not pick up the radio command yet.\n'
  case "$RADIO_BIN" in
    "$HOME/.local/bin"/*)
      printf 'For this terminal only, you can also run:\n'
      printf '  export PATH="$HOME/.local/bin:$PATH"\n\n'
      ;;
  esac
  printf 'Try:\n'
  printf '  radio tui\n'
}

main "$@"
