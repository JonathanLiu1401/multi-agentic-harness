#!/bin/bash
# Install the Multi-Agentic Harness on macOS/Linux.
# Usage: ./install-macos.sh
#
# Intel Mac notes:
#   - Homebrew lives at /usr/local (not /opt/homebrew).
#   - python3 on PATH may be a leftover python.org 3.7; this installer refuses
#     anything older than 3.10 and prefers 3.12+/skills-venv.
#   - Visible workers open Terminal.app (BRIDGE_TERMINAL overrides the app).
#   - CLIProxyAPI is the Homebrew formula `cliproxyapi` (brew services).
#
# A previous install is removed first (see uninstall-macos.sh) so stale
# ~/.local/bin/clx and ~/.agent-bridge copies cannot shadow the new files.
# Set SKIP_UNINSTALL=1 to keep the previous user files.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
USER_HOME="$HOME"
ARCH="$(uname -m)"

echo "============================================================"
echo "Installing Multi-Agentic Harness"
echo "Host: $(uname -s) ${ARCH}"
echo "============================================================"

if [ "${SKIP_UNINSTALL:-}" != "1" ] && [ -x "$HERE/uninstall-macos.sh" ]; then
  if [ -d "$USER_HOME/.agent-bridge" ] || [ -e "$USER_HOME/.local/bin/clx" ]; then
    echo "Previous harness detected — uninstalling it first so the new copy can take over."
    bash "$HERE/uninstall-macos.sh"
    echo ""
  fi
fi

# Python >=3.10. Never use the python.org 3.7 that Intel Macs often prepend
# via ~/.bash_profile (/Library/Frameworks/Python.framework/Versions/3.7).
pick_python() {
  local cand bin ver major minor
  for cand in \
    "$HOME/.claude/skills-venv/bin/python" \
    python3.14 python3.13 python3.12 python3.11 python3.10 \
    /usr/local/bin/python3.14 /usr/local/bin/python3.13 /usr/local/bin/python3.12 \
    /opt/homebrew/bin/python3.14 /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12
  do
    bin=""
    if [ -x "$cand" ]; then
      bin="$cand"
    elif command -v "$cand" >/dev/null 2>&1; then
      bin="$(command -v "$cand")"
    else
      continue
    fi
    ver="$("$bin" -c 'import sys; print("%d.%d"%sys.version_info[:2])' 2>/dev/null || true)"
    [ -n "$ver" ] || continue
    major="${ver%%.*}"
    minor="${ver#*.}"
    if [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; }; then
      echo "$bin"
      return 0
    fi
  done
  return 1
}

PY="$(pick_python)" || {
  echo "ERROR: Python 3.10+ is required. On this Intel Mac, \`python3\` is often 3.7 from python.org." >&2
  echo "Install with:  brew install python@3.12" >&2
  exit 1
}
echo "Using Python: $PY ($("$PY" -c 'import sys,platform; print(sys.version.split()[0], platform.machine())'))"

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
for f in visible_agent_bridge.py claude_worker_runner.py cursor_worker_runner.py captain_checkup.py cursor_cloud_api.py grok_worker_runner.py agy_worker_runner.py; do
  if [ -f "$HERE/$f" ]; then
    cp "$HERE/$f" "$BRIDGE_DIR/"
  fi
done
if [ -f "$HERE/gateway/cursor_anthropic_gateway.py" ]; then
  cp "$HERE/gateway/cursor_anthropic_gateway.py" "$BRIDGE_DIR/"
fi
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

compile_files=("$BRIDGE_DIR/visible_agent_bridge.py")
for f in claude_worker_runner.py cursor_worker_runner.py captain_checkup.py cursor_cloud_api.py grok_worker_runner.py agy_worker_runner.py cursor_anthropic_gateway.py; do
  [ -f "$BRIDGE_DIR/$f" ] && compile_files+=("$BRIDGE_DIR/$f")
done
"$PY" -m py_compile "${compile_files[@]}"
echo "Python bridge syntax validated successfully."

# ---------------------------------------------------------------------------
# PART 2: Provider Profiles, Launchers & Gateway (clx, clg, cld)
# ---------------------------------------------------------------------------
echo ""
echo "--- Part 2: Provider Profiles & Launchers (clx, clg, cld, clo, clc) ---"

# 1. Deploy subagent definitions to ~/.claude/agents/
if [ -d "$HERE/plugin/agents" ]; then
  mkdir -p "$USER_HOME/.claude/agents"
  cp "$HERE/plugin/agents/"*.md "$USER_HOME/.claude/agents/"
  echo "Installed subagent definitions: grok, agy-gemini-3-8-flash, deepseek, openrouter"
fi

# 2. Deploy launchers to ~/bin and ~/.local/bin (this Intel Mac already has ~/.local/bin on PATH).
if [ -d "$HERE/launchers" ]; then
  mkdir -p "$USER_HOME/bin" "$USER_HOME/.local/bin"
  for cmd in clx clg cld clo clc; do
    if [ -f "$HERE/launchers/$cmd" ]; then
      cp "$HERE/launchers/$cmd" "$USER_HOME/bin/$cmd"
      cp "$HERE/launchers/$cmd" "$USER_HOME/.local/bin/$cmd"
      chmod +x "$USER_HOME/bin/$cmd" "$USER_HOME/.local/bin/$cmd"
    fi
  done
  echo "Installed launchers (clx, clg, cld, clo, clc) to $USER_HOME/bin and $USER_HOME/.local/bin"
fi

# Ensure ~/bin is on PATH for new shells. Skip unwritable rc files (e.g. root-owned ~/.zshrc).
MARKER="# multi-agentic-harness launchers (macOS)"
for rc in "$USER_HOME/.bashrc" "$USER_HOME/.bash_profile" "$USER_HOME/.zshrc"; do
  [ -e "$rc" ] || continue
  [ -w "$rc" ] || { echo "Skipping PATH patch (not writable): $rc"; continue; }
  grep -q "$MARKER" "$rc" && continue
  printf '\n%s\nexport PATH="$HOME/bin:$HOME/.local/bin:$PATH"\n' "$MARKER" >> "$rc"
  echo "Added ~/bin to PATH in $rc"
done

# 3. Deploy profile templates and symlink agents & skills
for prof in claude-clx claude-clg claude-cld claude-clo claude-clc; do
  pDir="$USER_HOME/.$prof"
  mkdir -p "$pDir"
  if [ -d "$HERE/templates/$prof" ]; then
    cp "$HERE/templates/$prof/settings.json" "$pDir/settings.json"
    cp "$HERE/templates/$prof/CLAUDE.md" "$pDir/CLAUDE.md"
    if [ -d "$HERE/templates/$prof/commands" ]; then
      mkdir -p "$pDir/commands"
      cp "$HERE/templates/$prof/commands/"* "$pDir/commands/"
    fi
  fi
  [ -e "$pDir/agents" ] || ln -s "$USER_HOME/.claude/agents" "$pDir/agents"
  [ -e "$pDir/skills" ] || ln -s "$USER_HOME/.claude/skills" "$pDir/skills"
  echo "Configured profile: .$prof"
done

# 4. Initialize Secrets Directory
SECRETS_DIR="$USER_HOME/.cc-bridge/secrets"
mkdir -p "$SECRETS_DIR" "$USER_HOME/.cc-bridge"
if [ ! -f "$SECRETS_DIR/clx-api.key" ]; then
  seeded=""
  # Prefer a key already used by the previous clx launcher or Homebrew cliproxyapi.conf.
  latest_backup="$(ls -td "$USER_HOME"/.agent-bridge-uninstall-* 2>/dev/null | head -1 || true)"
  if [ -n "$latest_backup" ] && [ -f "$latest_backup/launchers/clx" ]; then
    seeded="$(awk -F= '/CLX_KEY=/{gsub(/"/,"",$2); print $2; exit}' "$latest_backup/launchers/clx" || true)"
  fi
  if [ -z "$seeded" ] && [ -f /usr/local/etc/cliproxyapi.conf ]; then
    seeded="$("$PY" -c '
import re, pathlib
text = pathlib.Path("/usr/local/etc/cliproxyapi.conf").read_text()
keys = re.findall(r"api-keys:\s*\n(?:[ \t]*- \"([^\"]+)\")", text)
print(keys[0] if keys else "")
' 2>/dev/null || true)"
  fi
  if [ -n "$seeded" ]; then
    printf '%s\n' "$seeded" > "$SECRETS_DIR/clx-api.key"
    echo "Reused existing CLIProxyAPI client key: $SECRETS_DIR/clx-api.key"
  else
    hex=$(openssl rand -hex 24 2>/dev/null || "$PY" -c "import secrets; print(secrets.token_hex(24))")
    echo "ccp-$hex" > "$SECRETS_DIR/clx-api.key"
    echo "Generated local gateway client key: $SECRETS_DIR/clx-api.key"
  fi
  chmod 600 "$SECRETS_DIR/clx-api.key"
fi
if [ ! -f "$SECRETS_DIR/openrouter-api.key" ]; then
  echo "clo: no $SECRETS_DIR/openrouter-api.key yet. Save your sk-or- key there (OpenRouter Dashboard -> Keys)."
fi
if [ ! -f "$SECRETS_DIR/cursor-api.key" ]; then
  echo "clc: no $SECRETS_DIR/cursor-api.key yet. Save your crsr_ key there (Cursor Dashboard -> API keys)."
fi
for fn in refresh_clo_models.py clo_or_hook.py ddg_search_server.py start-gateway.sh stop-gateway.sh start-clc-gateway.sh; do
  if [ -f "$HERE/gateway/$fn" ]; then
    cp "$HERE/gateway/$fn" "$USER_HOME/.cc-bridge/$fn"
    case "$fn" in *.sh) chmod +x "$USER_HOME/.cc-bridge/$fn" ;; esac
  fi
done
if [ -x "$HERE/gateway/install-autostart-macos.sh" ]; then
  bash "$HERE/gateway/install-autostart-macos.sh" || echo "WARNING: CLIProxyAPI autostart install failed (brew services may already own it)."
fi

# 5. Inject pricing cache into .claude.json files
# Official published rates (September 2026):
#   Google Gemini (https://ai.google.dev/pricing): Flash $0.75 in / $3.75 out / $0.075 cache read; Pro $2.00 in / $12.00 out / $0.20 cache read
#   xAI Grok (https://docs.x.ai/developers/pricing): Grok 4.6 $2.00 in / $6.00 out / $0.50 cache read (<200k tokens); Grok 4.5 $2.00 in / $6.00 out / $0.30 cache read
#   DeepSeek (https://api-docs.deepseek.com/quick_start/pricing): Flash $0.30 in / $1.20 out / $0.006 cache read (peak); V4 Pro $1.32 in / $3.96 out / $0.044 cache read (peak)
"$PY" - << 'EOF'
import json, os, shutil, sys

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
    os.path.expanduser("~/.claude-clo/.claude.json"),
    os.path.expanduser("~/.claude-clc/.claude.json"),
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

    mcps = d.setdefault("mcpServers", {})
    if isinstance(mcps, dict) and "agent-visibility" not in mcps:
        bridge_py = os.path.expanduser("~/.agent-bridge/visible_agent_bridge.py")
        mcps["agent-visibility"] = {
            "type": "stdio",
            "command": sys.executable,
            "args": [bridge_py],
            "env": {}
        }

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

if [ -f "$HERE/gateway/inject_clc_pricing.py" ]; then
  (cd "$HERE/gateway" && "$PY" inject_clc_pricing.py) || echo "WARNING: clc pricing inject failed."
fi

# Layer-2 MCP for Grok workers (submit_captain_report / request_captain_help).
GROK_TOML="$USER_HOME/.grok/config.toml"
if [ -f "$GROK_TOML" ] && ! grep -q 'mcp_servers.agent-visibility' "$GROK_TOML"; then
  cp -a "$GROK_TOML" "$GROK_TOML.bak"
  cat >> "$GROK_TOML" <<EOF

[mcp_servers.agent-visibility]
command = "$PY"
args = ["$BRIDGE_DIR/visible_agent_bridge.py"]
enabled = true
EOF
  echo "Wired Grok MCP server agent-visibility in ~/.grok/config.toml"
fi

echo ""
echo "============================================================"
echo "Installation Completed Successfully!"
echo "============================================================"
echo "Host: macOS ${ARCH} (Intel Homebrew prefix /usr/local when x86_64)."
echo "Part 1 (Worker Bridge): MCP server 'agent-visibility' registered."
echo "Part 2 (Custom Launchers): clx, clg, cld, clo, clc in ~/bin and ~/.local/bin."
echo ""
echo "To start a custom session:"
echo "  clx   -> Grok 4.6 (500k context)"
echo "  clg   -> Gemini 3.8 Flash / 3.1 Pro (1M context)"
echo "  cld   -> DeepSeek V4.1 Flash / V4 Pro (1M context)"
echo "  clo   -> OpenRouter catalog (1M, default Anthropic Sonnet latest)"
echo "  clc   -> Cursor catalog (1M, translator on 127.0.0.1:8318)"
echo "Visible Grok workers open Terminal.app (set BRIDGE_HEADLESS=1 to skip the window)."
