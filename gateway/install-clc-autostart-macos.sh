#!/bin/bash
# Register the Cursor Anthropic translator (clc) to start at login on macOS.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.multiagentic.clc-gateway"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
START="${HOME}/.cc-bridge/start-clc-gateway.sh"
mkdir -p "${HOME}/Library/LaunchAgents" "${HOME}/.cc-bridge"
cp "$HERE/start-clc-gateway.sh" "$START"
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
  <true/>
  <key>StandardOutPath</key>
  <string>${HOME}/.cc-bridge/clc-gateway-launchd.log</string>
  <key>StandardErrorPath</key>
  <string>${HOME}/.cc-bridge/clc-gateway-launchd.err.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST" >/dev/null 2>&1 || true
launchctl load "$PLIST"
echo "CLCCursorGateway autostart: $PLIST"
"$START" || true
