#!/bin/bash
# Stop CLIProxyAPI started by start-gateway.sh or brew services.
set -euo pipefail

LOG_DIR="${HOME}/.cc-bridge"
mkdir -p "$LOG_DIR"

if command -v brew >/dev/null 2>&1 && brew list --formula cliproxyapi >/dev/null 2>&1; then
  brew services stop cliproxyapi >/dev/null 2>&1 || true
fi

if [ -f "${LOG_DIR}/gateway.pid" ]; then
  pid="$(cat "${LOG_DIR}/gateway.pid" 2>/dev/null || true)"
  if [ -n "${pid}" ] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    sleep 1
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "${LOG_DIR}/gateway.pid"
fi

# Do not pkill brew's formula blindly if it was started outside this script
# and is still wanted; only reap orphans holding 8317 after a failed stop.
if command -v lsof >/dev/null 2>&1; then
  pids="$(lsof -nP -iTCP:8317 -sTCP:LISTEN -t 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill 2>/dev/null || true
  fi
fi

echo "CLIProxyAPI stopped (port 8317 should be free)."
