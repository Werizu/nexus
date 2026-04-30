#!/bin/bash
# NEXUS Mac Agent Installer
# Usage: curl -fsSL https://werizu.github.io/nexus/install-mac.sh | bash

set -e

INSTALL_DIR="$HOME/.nexus-agent"
PLIST_NAME="com.nexus.agent"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

echo ""
echo "  NEXUS Mac Agent Installer"
echo "  ========================="
echo ""

# ── Credentials ────────────────────────────────────────
echo "  Dein NEXUS Admin muss dir einen Account angelegt haben."
echo ""
read -p "  Brain IP (Tailscale IP des Brain Pi): " BRAIN_IP
read -p "  NEXUS Username: " NEXUS_USER
read -sp "  NEXUS Passwort: " NEXUS_PASS
echo ""

if [ -z "$BRAIN_IP" ] || [ -z "$NEXUS_USER" ] || [ -z "$NEXUS_PASS" ]; then
    echo "  [!] Alle Felder sind erforderlich."
    exit 1
fi

# ── Verify connection ──────────────────────────────────
echo ""
echo "  [1/4] Verbindung zum Brain prüfen..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://${BRAIN_IP}:8000/api/v1/health" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" != "200" ]; then
    echo "  [!] Brain nicht erreichbar unter http://${BRAIN_IP}:8000"
    echo "  Prüfe: Ist Tailscale aktiv? Ist der Brain Pi eingeschaltet?"
    exit 1
fi
echo "  [✓] Brain erreichbar"

# ── Check Python ───────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "  [!] Python 3 nicht gefunden. Bitte installieren: brew install python3"
    exit 1
fi

# ── Download files ─────────────────────────────────────
echo "  [2/4] Agent herunterladen..."
mkdir -p "$INSTALL_DIR"

BASE="https://raw.githubusercontent.com/Werizu/nexus/main/agent-mac"
for f in nexus_agent_mac.py requirements.txt; do
    curl -fsSL "$BASE/$f" -o "$INSTALL_DIR/$f"
done
echo "  [✓] Agent heruntergeladen"

# ── Write config with credentials ──────────────────────
echo "  [3/4] Konfiguration schreiben..."
cat > "$INSTALL_DIR/config.yaml" <<EOF
mqtt:
  broker: "$BRAIN_IP"
  port: 1883
auth:
  username: "$NEXUS_USER"
  password: "$NEXUS_PASS"
agent:
  report_interval: 10
alerts:
  cpu: 90
  ram: 90
  disk: 90
  cooldown: 300
EOF

# ── Install dependencies ──────────────────────────────
if [ ! -d "$INSTALL_DIR/venv" ]; then
    python3 -m venv "$INSTALL_DIR/venv"
fi
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
echo "  [✓] Dependencies installiert"

# ── Create & load LaunchAgent ─────────────────────────
echo "  [4/4] Autostart einrichten..."

if launchctl list | grep -q "$PLIST_NAME" 2>/dev/null; then
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
fi

PYTHON_PATH="$INSTALL_DIR/venv/bin/python"
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

launchctl load "$PLIST_PATH"

echo ""
echo "  ════════════════════════════════════════════════"
echo "  NEXUS Mac Agent installiert!"
echo "  ════════════════════════════════════════════════"
echo ""
echo "  Der Agent registriert sich automatisch beim Brain."
echo "  Dein Gerät erscheint in wenigen Sekunden im Dashboard."
echo ""
echo "  Status:    launchctl list | grep nexus"
echo "  Logs:      tail -f ~/.nexus-agent/nexus-agent-mac.log"
echo "  Stoppen:   launchctl unload ~/Library/LaunchAgents/com.nexus.agent.plist"
echo "  Entfernen: rm -rf ~/.nexus-agent ~/Library/LaunchAgents/com.nexus.agent.plist"
echo ""
