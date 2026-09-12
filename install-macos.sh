#!/bin/bash
# Install the Multi-Agentic Harness on macOS/Linux.
# Usage: ./install-macos.sh
#
# This script installs both parts of the Multi-Agentic Harness:
#   Part 1: The Multi-Agent Worker Bridge (Claude manages Cursor, Grok, Agy, and headless workers)
#   Part 2: Provider Profiles & Launchers (clx, clg, cld for Grok, Gemini, and DeepSeek in Claude Code)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
USER_HOME="$HOME"

echo "============================================================"
echo "Installing Multi-Agentic Harness"
echo "============================================================"

# Python >=3.10 with the `mcp` package
if [ -x "$HOME/.claude/skills-venv/bin/python" ]; then
  PY="$HOME/.claude/skills-venv/bin/python"
else
  PY="$(command -v python3.12 || command -v python3.11 || command -v python3)"
fi
echo "Using Python: $PY"

# Check for FastMCP or MCPServer capability (supports both mcp 1.x and mcp 2.x+)
MCP_CHECK_CODE='
import sys
try:
    from mcp.server.fastmcp import FastMCP
    sys.exit(0)
except (ImportError, ModuleNotFoundError):
    try:
        from mcp.server.mcpserver import MCPServer
        sys.exit(0)
    except (ImportError, ModuleNotFoundError):
        try:
            from fastmcp import FastMCP
            sys.exit(0)
        except (ImportError, ModuleNotFoundError):
            sys.exit(1)
'

if ! "$PY" -c "$MCP_CHECK_CODE" 2>/dev/null; then
  echo "Installing python mcp package..."
  "$PY" -m pip install --user mcp
  if ! "$PY" -c "$MCP_CHECK_CODE" 2>/dev/null; then
    "$PY" -m pip install --user fastmcp
  fi
fi

# ---------------------------------------------------------------------------
# PART 1: Multi-Agent Worker Bridge (claude-manages-xxx)
# ---------------------------------------------------------------------------
echo ""
echo "--- Part 1: Multi-Agent Worker Bridge ---"

BRIDGE_DIR="$USER_HOME/.agent-bridge"
mkdir -p "$BRIDGE_DIR"
cp "$HERE/visible_agent_bridge.py" "$HERE/claude_worker_runner.py" "$HERE/cursor_worker_runner.py" "$HERE/captain_checkup.py" "$HERE/cursor_cloud_api.py" "$BRIDGE_DIR/"
echo "Deployed bridge runners to $BRIDGE_DIR"

# Captain doctrine skill for the manager session
if [ -d "$HERE/plugin/skills/claude-manages-codex" ]; then
  mkdir -p "$USER_HOME/.claude/skills"
  rsync -a "$HERE/plugin/skills/claude-manages-codex/" "$USER_HOME/.claude/skills/claude-manages-codex/"
  echo "Installed skill: claude-manages-codex"
fi

# Register the MCP server with Claude Code (user scope; idempotent)
claude mcp remove agent-visibility -s user >/dev/null 2>&1 || true
claude mcp add agent-visibility -s user -- "$PY" "$BRIDGE_DIR/visible_agent_bridge.py"
echo "Registered MCP server 'agent-visibility' (user scope)"

"$PY" -m py_compile "$BRIDGE_DIR/visible_agent_bridge.py" "$BRIDGE_DIR/claude_worker_runner.py" "$BRIDGE_DIR/cursor_worker_runner.py" "$BRIDGE_DIR/captain_checkup.py" "$BRIDGE_DIR/cursor_cloud_api.py"
echo "Python bridge syntax validated successfully."

# ---------------------------------------------------------------------------
# PART 2: Provider Profiles, Launchers & Gateway (clx, clg, cld)
# ---------------------------------------------------------------------------
echo ""
echo "--- Part 2: Provider Profiles & Launchers (clx, clg, cld) ---"

# 1. Deploy subagent definitions to ~/.claude/agents/
if [ -d "$HERE/plugin/agents" ]; then
  mkdir -p "$USER_HOME/.claude/agents"
  cp "$HERE/plugin/agents/"*.md "$USER_HOME/.claude/agents/"
  echo "Installed subagent definitions: grok, agy-gemini-3-8-flash, deepseek"
fi

# 2. Deploy launchers to ~/bin/
if [ -d "$HERE/launchers" ]; then
  mkdir -p "$USER_HOME/bin"
  for cmd in clx clg cld; do
    if [ -f "$HERE/launchers/$cmd" ]; then
      cp "$HERE/launchers/$cmd" "$USER_HOME/bin/$cmd"
      chmod +x "$USER_HOME/bin/$cmd"
    fi
  done
  echo "Installed launchers (clx, clg, cld) to $USER_HOME/bin"
fi

# 3. Deploy profile templates and symlink agents & skills
for prof in claude-clx claude-clg claude-cld; do
  pDir="$USER_HOME/.$prof"
  mkdir -p "$pDir"
  if [ -d "$HERE/templates/$prof" ]; then
    cp "$HERE/templates/$prof/settings.json" "$pDir/settings.json"
    cp "$HERE/templates/$prof/CLAUDE.md" "$pDir/CLAUDE.md"
  fi
  [ -e "$pDir/agents" ] || ln -s "$USER_HOME/.claude/agents" "$pDir/agents"
  [ -e "$pDir/skills" ] || ln -s "$USER_HOME/.claude/skills" "$pDir/skills"
  echo "Configured profile: .$prof"
done

# 4. Initialize Secrets Directory
SECRETS_DIR="$USER_HOME/.cc-bridge/secrets"
mkdir -p "$SECRETS_DIR"
if [ ! -f "$SECRETS_DIR/clx-api.key" ]; then
  hex=$(openssl rand -hex 24 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(24))")
  echo "ccp-$hex" > "$SECRETS_DIR/clx-api.key"
  chmod 600 "$SECRETS_DIR/clx-api.key"
  echo "Generated local gateway client key: $SECRETS_DIR/clx-api.key"
fi

# 5. Inject pricing cache into .claude.json files
# Official published rates (September 2026):
#   Google Gemini (https://ai.google.dev/pricing): Flash $0.75 in / $3.75 out / $0.075 cache read; Pro $2.00 in / $12.00 out / $0.20 cache read
#   xAI Grok (https://docs.x.ai/developers/pricing): Grok 4.6 $2.00 in / $6.00 out / $0.50 cache read (<200k tokens); Grok 4.5 $2.00 in / $6.00 out / $0.30 cache read
#   DeepSeek (https://api-docs.deepseek.com/quick_start/pricing): Flash $0.30 in / $1.20 out / $0.006 cache read (peak); V4 Pro $1.32 in / $3.96 out / $0.044 cache read (peak)
"$PY" - << 'EOF'
import json, os, shutil

model_costs = {
    "gemini-3.8-flash-high(high)": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-3.8-flash-high(medium)": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-3.8-flash-high(low)": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-3.8-flash-high": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-3.8-flash": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-3.7-flash-high(high)": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-3.7-flash": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-3.6-flash-high(high)": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-3.6-flash": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},
    "gemini-2.5-flash": {"inputTokens": 0.30, "outputTokens": 2.50, "promptCacheWriteTokens": 0.30, "promptCacheReadTokens": 0.03, "webSearchRequests": 0.01},
    "gemini-3.1-pro-low(high)": {"inputTokens": 2.00, "outputTokens": 12.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.20, "webSearchRequests": 0.01},
    "gemini-3.1-pro-low(low)": {"inputTokens": 2.00, "outputTokens": 12.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.20, "webSearchRequests": 0.01},
    "gemini-3.1-pro": {"inputTokens": 2.00, "outputTokens": 12.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.20, "webSearchRequests": 0.01},
    "gemini-2.5-pro": {"inputTokens": 1.25, "outputTokens": 10.00, "promptCacheWriteTokens": 1.25, "promptCacheReadTokens": 0.125, "webSearchRequests": 0.01},
    "agy-gemini-3-8-flash": {"inputTokens": 0.75, "outputTokens": 3.75, "promptCacheWriteTokens": 0.75, "promptCacheReadTokens": 0.075, "webSearchRequests": 0.01},

    "grok-4.6(xhigh)": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.50, "webSearchRequests": 0.01},
    "grok-4.6(high)": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.50, "webSearchRequests": 0.01},
    "grok-4.6(medium)": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.50, "webSearchRequests": 0.01},
    "grok-4.6(low)": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.50, "webSearchRequests": 0.01},
    "grok-4.6": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.50, "webSearchRequests": 0.01},
    "grok-4.5(high)": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.30, "webSearchRequests": 0.01},
    "grok-4.5(low)": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.30, "webSearchRequests": 0.01},
    "grok-4.5": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.30, "webSearchRequests": 0.01},
    "grok": {"inputTokens": 2.00, "outputTokens": 6.00, "promptCacheWriteTokens": 2.00, "promptCacheReadTokens": 0.50, "webSearchRequests": 0.01},

    "deepseek-flash[1m]": {"inputTokens": 0.30, "outputTokens": 1.20, "promptCacheWriteTokens": 0.30, "promptCacheReadTokens": 0.006, "webSearchRequests": 0.01},
    "deepseek-flash": {"inputTokens": 0.30, "outputTokens": 1.20, "promptCacheWriteTokens": 0.30, "promptCacheReadTokens": 0.006, "webSearchRequests": 0.01},
    "deepseek-v4.1-flash": {"inputTokens": 0.30, "outputTokens": 1.20, "promptCacheWriteTokens": 0.30, "promptCacheReadTokens": 0.006, "webSearchRequests": 0.01},
    "deepseek-v4-pro[1m]": {"inputTokens": 1.32, "outputTokens": 3.96, "promptCacheWriteTokens": 1.32, "promptCacheReadTokens": 0.044, "webSearchRequests": 0.01},
    "deepseek-v4-pro": {"inputTokens": 1.32, "outputTokens": 3.96, "promptCacheWriteTokens": 1.32, "promptCacheReadTokens": 0.044, "webSearchRequests": 0.01},
    "deepseek-chat": {"inputTokens": 0.30, "outputTokens": 1.20, "promptCacheWriteTokens": 0.30, "promptCacheReadTokens": 0.006, "webSearchRequests": 0.01},
    "deepseek-reasoner": {"inputTokens": 1.32, "outputTokens": 3.96, "promptCacheWriteTokens": 1.32, "promptCacheReadTokens": 0.044, "webSearchRequests": 0.01},
    "deepseek": {"inputTokens": 0.30, "outputTokens": 1.20, "promptCacheWriteTokens": 0.30, "promptCacheReadTokens": 0.006, "webSearchRequests": 0.01}
}

paths = [
    os.path.expanduser("~/.claude-clg/.claude.json"),
    os.path.expanduser("~/.claude-clx/.claude.json"),
    os.path.expanduser("~/.claude-cld/.claude.json"),
    os.path.expanduser("~/.claude.json")
]

for p in paths:
    d = None
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception as exc:
            print(f"WARNING: Could not parse {p} as valid JSON ({exc}). Skipping to protect file from data loss.")
            continue
        try:
            shutil.copy2(p, p + ".bak")
        except Exception:
            pass
    else:
        d = {
            "hasCompletedOnboarding": True,
            "bypassPermissionsModeAccepted": True
        }

    if not isinstance(d, dict):
        print(f"WARNING: {p} root is not a JSON object. Skipping to protect file.")
        continue

    d["hasCompletedOnboarding"] = True
    d["bypassPermissionsModeAccepted"] = True
    cache = d.setdefault("additionalModelCostsCache", {})
    if isinstance(cache, dict):
        cache.update(model_costs)
    else:
        d["additionalModelCostsCache"] = model_costs

    tmp = f"{p}.tmp.{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(tmp, p)
    except Exception as exc:
        print(f"ERROR: Failed to write {p}: {exc}")
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except Exception: pass
EOF
echo "Injected real API pricing into .claude.json config caches safely via Python."

echo ""
echo "============================================================"
echo "Installation Completed Successfully!"
echo "============================================================"
echo "Part 1 (Worker Bridge): MCP server 'agent-visibility' registered."
echo "Part 2 (Custom Launchers): clx (Grok), clg (Gemini), cld (DeepSeek) ready in ~/bin."
echo ""
echo "To start a custom session:"
echo "  clx   -> Grok 4.6 (500k context)"
echo "  clg   -> Gemini 3.8 Flash / 3.1 Pro (1M context)"
echo "  cld   -> DeepSeek V4.1 Flash / V4 Pro (1M context)"
