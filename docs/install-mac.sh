#!/bin/bash
# NEXUS Mac Agent Installer
# Usage: curl -fsSL https://werizu.github.io/nexus/install-mac.sh | bash

set -e

BRAIN_IP="${NEXUS_BRAIN:-192.168.178.202}"
INSTALL_DIR="$HOME/.nexus-agent"
PLIST_NAME="com.nexus.agent"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

echo ""
echo "  NEXUS Mac Agent Installer"
echo "  Brain: $BRAIN_IP"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "  [!] Python 3 nicht gefunden. Bitte installieren: brew install python3"
    exit 1
fi

# Create directory
mkdir -p "$INSTALL_DIR"

# Download files
BASE="https://raw.githubusercontent.com/Werizu/nexus/main/agent-mac"
for f in nexus_agent_mac.py requirements.txt; do
    curl -fsSL "$BASE/$f" -o "$INSTALL_DIR/$f"
    echo "  Downloaded $f"
done

# Write config
cat > "$INSTALL_DIR/config.yaml" <<EOF
mqtt:
  broker: "$BRAIN_IP"
  port: 1883
  client_id: "nexus-agent-mac"
agent:
  device_id: "main_mac"
  name: "$(hostname -s)"
  report_interval: 10
alerts:
  cpu: 90
  ram: 90
  disk: 90
  cooldown: 300
EOF

# Install deps
python3 -m pip install --quiet -r "$INSTALL_DIR/requirements.txt" 2>/dev/null

# Unload existing service if present
if launchctl list | grep -q "$PLIST_NAME" 2>/dev/null; then
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
fi

# Create LaunchAgent plist
PYTHON_PATH=$(which python3)
cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_PATH}</string>
        <string>${INSTALL_DIR}/nexus_agent_mac.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${INSTALL_DIR}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${INSTALL_DIR}/nexus-agent-mac.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${INSTALL_DIR}/nexus-agent-mac.stderr.log</string>
</dict>
</plist>
EOF

# Load service
launchctl load "$PLIST_PATH"

echo ""
echo "  NEXUS Mac Agent installiert!"
echo "  Status:    launchctl list | grep nexus"
echo "  Logs:      tail -f ~/.nexus-agent/nexus-agent-mac.log"
echo "  Stoppen:   launchctl unload ~/Library/LaunchAgents/com.nexus.agent.plist"
echo "  Entfernen: rm -rf ~/.nexus-agent ~/Library/LaunchAgents/com.nexus.agent.plist"
echo ""
