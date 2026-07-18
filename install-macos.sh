#!/bin/bash
# Install the visible-agent bridge (multi-agentic-harness) on macOS/Linux.
# Usage: ./install-macos.sh [cliproxy-api-key] [cliproxy-base-url]
#
# Deploys the bridge + cross-platform Claude worker runner to ~/.agent-bridge/,
# writes the CLIProxyAPI connection config, installs the captain-doctrine skill,
# and registers the MCP server with Claude Code (user scope).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
BRIDGE_DIR="$HOME/.agent-bridge"
API_KEY="${1:-}"
BASE_URL="${2:-http://127.0.0.1:8317}"

# Python >=3.10 with the `mcp` package; prefer the shared skills venv when present.
if [ -x "$HOME/.claude/skills-venv/bin/python" ]; then
  PY="$HOME/.claude/skills-venv/bin/python"
else
  PY="$(command -v python3.12 || command -v python3.11 || command -v python3)"
  "$PY" -c "import mcp" 2>/dev/null || "$PY" -m pip install --user mcp
fi

mkdir -p "$BRIDGE_DIR"
cp "$HERE/visible_agent_bridge.py" "$HERE/claude_worker_runner.py" "$BRIDGE_DIR/"

if [ -n "$API_KEY" ]; then
  umask 077
  cat > "$BRIDGE_DIR/proxy.json" <<EOF
{
  "base_url": "$BASE_URL",
  "api_key": "$API_KEY",
  "claude_config_dir": ""
}
EOF
  echo "Wrote $BRIDGE_DIR/proxy.json (base_url=$BASE_URL)"
else
  echo "NOTE: no API key supplied; workers will only run with use_proxy=False until"
  echo "      $BRIDGE_DIR/proxy.json is written or CLIPROXY_API_KEY is exported."
fi

# Captain doctrine skill for the manager session.
if [ -d "$HERE/plugin/skills/claude-manages-codex" ]; then
  mkdir -p "$HOME/.claude/skills"
  rsync -a "$HERE/plugin/skills/claude-manages-codex/" "$HOME/.claude/skills/claude-manages-codex/"
  echo "Installed skill: claude-manages-codex"
fi

# Register the MCP server with Claude Code (user scope; idempotent).
claude mcp remove agent-visibility -s user >/dev/null 2>&1 || true
claude mcp add agent-visibility -s user -- "$PY" "$BRIDGE_DIR/visible_agent_bridge.py"
echo "Registered MCP server 'agent-visibility' (user scope) using $PY"

"$PY" -m py_compile "$BRIDGE_DIR/visible_agent_bridge.py" "$BRIDGE_DIR/claude_worker_runner.py"
echo "Install complete. Restart Claude Code, then check with the check_worker_backends MCP tool."
