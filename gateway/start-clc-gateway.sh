#!/bin/bash
# Start the Cursor Anthropic translator on 127.0.0.1:8318 (macOS/Linux).
set -euo pipefail

LOG_DIR="${HOME}/.cc-bridge"
LOG="${LOG_DIR}/clc-gateway-start.log"
RUN_LOG="${LOG_DIR}/clc-gateway-current.log"
ERR_LOG="${LOG_DIR}/clc-gateway-current.err.log"
mkdir -p "$LOG_DIR"

SCRIPT="${HOME}/.agent-bridge/cursor_anthropic_gateway.py"
if [ ! -f "$SCRIPT" ]; then
  SCRIPT="${HOME}/github-tools/multi-agentic-harness/gateway/cursor_anthropic_gateway.py"
fi
if [ ! -f "$SCRIPT" ]; then
  echo "missing cursor_anthropic_gateway.py" >&2
  exit 1
fi

pick_python() {
  for cand in \
    "${HOME}/.claude/skills-venv/bin/python" \
    python3.14 python3.13 python3.12 python3.11 python3.10
  do
    if [ -x "$cand" ] || command -v "$cand" >/dev/null 2>&1; then
      bin="$cand"
      command -v "$cand" >/dev/null 2>&1 && bin="$(command -v "$cand")"
      [ -x "$cand" ] && bin="$cand"
      ver="$("$bin" -c 'import sys; print("%d.%d"%sys.version_info[:2])' 2>/dev/null || true)"
      major="${ver%%.*}"; minor="${ver#*.}"
      if [ -n "$ver" ] && [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; then
        echo "$bin"
        return 0
      fi
    fi
  done
  return 1
}

PY="$(pick_python)" || { echo "need Python 3.10+ (this Intel Mac's default python3 is often 3.7)" >&2; exit 1; }

listening() {
  lsof -nP -iTCP:8318 -sTCP:LISTEN >/dev/null 2>&1
}

if listening; then
  echo "clc gateway already listening on 127.0.0.1:8318"
  exit 0
fi

export CLC_WORKSPACE="${CLC_WORKSPACE:-$HOME}"
if [ -r "${HOME}/.cc-bridge/secrets/cursor-api.key" ]; then
  export CURSOR_API_KEY="$(tr -d '\r\n' < "${HOME}/.cc-bridge/secrets/cursor-api.key")"
fi

printf '%s === clc gateway start ===\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$LOG"
nohup "$PY" "$SCRIPT" --port 8318 --workspace "$HOME" >> "$RUN_LOG" 2>> "$ERR_LOG" &
echo $! > "${LOG_DIR}/clc-gateway.pid"

ok=0
for _ in $(seq 1 40); do
  sleep 1
  if listening; then
    ok=1
    break
  fi
done

if [ "$ok" -eq 1 ]; then
  echo "clc gateway listening on 127.0.0.1:8318"
else
  echo "clc gateway failed to bind 8318 — see $RUN_LOG / $ERR_LOG" >&2
  exit 1
fi
