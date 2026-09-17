#!/bin/bash
# Start CLIProxyAPI on macOS/Linux (Intel Homebrew: /usr/local; Apple Silicon: /opt/homebrew).
# Prefers `brew services` when the Homebrew formula is installed.
set -euo pipefail

LOG_DIR="${HOME}/.cc-bridge"
LOG="${LOG_DIR}/gateway.log"
mkdir -p "$LOG_DIR"

BREW_PREFIX="$(brew --prefix 2>/dev/null || true)"
if [ -z "${BREW_PREFIX}" ]; then
  if [ "$(uname -m)" = "arm64" ]; then
    BREW_PREFIX="/opt/homebrew"
  else
    BREW_PREFIX="/usr/local"
  fi
fi

CLIPROXY="$(command -v cliproxyapi || true)"
[ -n "$CLIPROXY" ] || CLIPROXY="${BREW_PREFIX}/bin/cliproxyapi"

CFG="${HOME}/cliproxyapi/config.yaml"
if [ ! -f "$CFG" ]; then
  if [ -f "${BREW_PREFIX}/etc/cliproxyapi.conf" ]; then
    CFG="${BREW_PREFIX}/etc/cliproxyapi.conf"
  fi
fi

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"; }

listening() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:8317 -sTCP:LISTEN >/dev/null 2>&1
  else
    curl -fsS -m 1 -o /dev/null "http://127.0.0.1:8317/v1/models" 2>/dev/null
  fi
}

if listening; then
  log "already listening on 127.0.0.1:8317"
  echo "CLIProxyAPI already listening on 127.0.0.1:8317"
  exit 0
fi

if command -v brew >/dev/null 2>&1 && brew list --formula cliproxyapi >/dev/null 2>&1; then
  log "starting via brew services"
  brew services start cliproxyapi >/dev/null
else
  if [ ! -x "$CLIPROXY" ]; then
    echo "missing cliproxyapi binary (tried $CLIPROXY). brew install cliproxyapi" >&2
    exit 1
  fi
  if [ ! -f "$CFG" ]; then
    echo "missing config $CFG" >&2
    exit 1
  fi
  log "starting detached: $CLIPROXY --config $CFG"
  nohup "$CLIPROXY" --config "$CFG" >> "${LOG_DIR}/gateway-current.log" 2>> "${LOG_DIR}/gateway-current.err.log" &
  echo $! > "${LOG_DIR}/gateway.pid"
fi

ok=0
for _ in $(seq 1 20); do
  sleep 1
  if listening; then
    ok=1
    break
  fi
done

if [ "$ok" -eq 1 ]; then
  log "listening on 127.0.0.1:8317"
  echo "CLIProxyAPI listening on 127.0.0.1:8317"
else
  log "FAILED to bind 8317"
  echo "CLIProxyAPI failed to bind 127.0.0.1:8317 — see $LOG" >&2
  exit 1
fi
