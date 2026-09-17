#!/bin/bash
# Register CLIProxyAPI to start at login on macOS.
# Prefers Homebrew services (Intel: /usr/local, Apple Silicon: /opt/homebrew).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

if command -v brew >/dev/null 2>&1 && brew list --formula cliproxyapi >/dev/null 2>&1; then
  brew services start cliproxyapi
  echo "CLIProxyAPI autostart: brew services (homebrew.mxcl.cliproxyapi)"
  "$HERE/start-gateway.sh"
  exit 0
fi

LABEL="com.multiagentic.cliproxyapi"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
START="${HOME}/.cc-bridge/start-gateway.sh"
mkdir -p "${HOME}/Library/LaunchAgents" "${HOME}/.cc-bridge"
cp "$HERE/start-gateway.sh" "$START"
chmod +x "$START"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${START}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
  <key>StandardOutPath</key>
  <string>${HOME}/.cc-bridge/gateway-launchd.log</string>
  <key>StandardErrorPath</key>
  <string>${HOME}/.cc-bridge/gateway-launchd.err.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST" >/dev/null 2>&1 || true
launchctl load "$PLIST"
echo "CLIProxyAPI autostart: $PLIST"
"$HERE/start-gateway.sh"
