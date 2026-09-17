#!/bin/bash
# Remove a previous Multi-Agentic Harness user install on macOS.
# Does NOT uninstall Homebrew cliproxyapi, Grok/Claude CLIs, or OAuth tokens.
#
# Usage: ./uninstall-macos.sh
set -euo pipefail

USER_HOME="$HOME"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${USER_HOME}/.agent-bridge-uninstall-${STAMP}"
mkdir -p "$BACKUP"

echo "============================================================"
echo "Uninstalling previous Multi-Agentic Harness (macOS)"
echo "Backups: $BACKUP"
echo "============================================================"

if command -v claude >/dev/null 2>&1; then
  claude mcp remove agent-visibility -s user >/dev/null 2>&1 || true
  echo "Removed Claude Code MCP server 'agent-visibility' (user scope)"
fi

if [ -d "${USER_HOME}/.agent-bridge" ]; then
  cp -a "${USER_HOME}/.agent-bridge" "${BACKUP}/agent-bridge"
  rm -rf "${USER_HOME}/.agent-bridge"
  echo "Removed ${USER_HOME}/.agent-bridge (backed up)"
fi

# Old Jul-2026 launcher lived on ~/.local/bin and shadows ~/bin on this machine.
for cmd in clx clg cld clo clc; do
  for dest in "${USER_HOME}/.local/bin/${cmd}" "${USER_HOME}/bin/${cmd}"; do
    if [ -e "$dest" ] || [ -L "$dest" ]; then
      mkdir -p "${BACKUP}/launchers"
      cp -a "$dest" "${BACKUP}/launchers/"
      rm -f "$dest"
      echo "Removed $dest"
    fi
  done
done

if [ -d "${USER_HOME}/.claude/skills/claude-manages-codex" ]; then
  mkdir -p "${BACKUP}/skills"
  cp -a "${USER_HOME}/.claude/skills/claude-manages-codex" "${BACKUP}/skills/"
  rm -rf "${USER_HOME}/.claude/skills/claude-manages-codex"
  echo "Removed ~/.claude/skills/claude-manages-codex (backed up)"
fi

# Isolated Claude Code profiles: keep directories (session history) but the
# installer will replace settings.json / CLAUDE.md. Back up current copies.
for prof in claude-clx claude-clg claude-cld claude-clo claude-clc; do
  pDir="${USER_HOME}/.${prof}"
  if [ -d "$pDir" ]; then
    mkdir -p "${BACKUP}/profiles/.${prof}"
    [ -f "$pDir/settings.json" ] && cp -a "$pDir/settings.json" "${BACKUP}/profiles/.${prof}/"
    [ -f "$pDir/CLAUDE.md" ] && cp -a "$pDir/CLAUDE.md" "${BACKUP}/profiles/.${prof}/"
    echo "Backed up profile settings for .${prof}"
  fi
done

# LaunchAgents installed by this repo (not Homebrew's cliproxyapi formula).
for label in com.multiagentic.cliproxyapi com.multiagentic.clc-gateway; do
  plist="${USER_HOME}/Library/LaunchAgents/${label}.plist"
  if [ -f "$plist" ]; then
    launchctl unload "$plist" >/dev/null 2>&1 || true
    mkdir -p "${BACKUP}/LaunchAgents"
    mv "$plist" "${BACKUP}/LaunchAgents/"
    echo "Unloaded $label"
  fi
done

# Drop only the harness MCP block from grok config; leave the rest of the file.
if [ -f "${USER_HOME}/.grok/config.toml" ] && grep -q 'mcp_servers.agent-visibility' "${USER_HOME}/.grok/config.toml"; then
  cp -a "${USER_HOME}/.grok/config.toml" "${BACKUP}/grok-config.toml"
  python3.12 - <<'PY' 2>/dev/null || true
from pathlib import Path
p = Path.home() / ".grok" / "config.toml"
text = p.read_text(encoding="utf-8")
out = []
skip = False
for line in text.splitlines(True):
    if line.startswith("[mcp_servers.agent-visibility"):
        skip = True
        continue
    if skip and line.startswith("[") and not line.startswith("[mcp_servers.agent-visibility"):
        skip = False
    if not skip:
        out.append(line)
p.write_text("".join(out), encoding="utf-8")
PY
  echo "Removed [mcp_servers.agent-visibility] from ~/.grok/config.toml"
fi

echo ""
echo "Kept (on purpose):"
echo "  - Homebrew cliproxyapi + ~/.cli-proxy-api OAuth tokens"
echo "  - grok / claude / cursor-agent CLIs"
echo "  - ~/.claude-clx (and sibling) profile directories"
echo "Uninstall complete. Run ./install-macos.sh to install the current harness."
