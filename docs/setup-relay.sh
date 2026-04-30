#!/bin/bash
# NEXUS WOL Relay Setup
# Usage: curl -fsSL https://werizu.github.io/nexus/setup-relay.sh | bash
#
# Richtet einen Raspberry Pi als WOL-Relay ein.
# Installiert: Tailscale + wakeonlan. Sonst nichts.

set -e

BRAIN_IP="${NEXUS_BRAIN:-}"

echo ""
echo "  NEXUS WOL Relay Setup"
echo "  ====================="
echo ""

# ── Checks ──────────────────────────────────────────────

if [ "$(id -u)" -eq 0 ]; then
    echo "  [!] Bitte NICHT als root ausfuehren (sudo wird automatisch genutzt)"
    exit 1
fi

# Check: Ethernet connected?
ETH_IF=$(ip -o link show | awk -F': ' '/eth[0-9]|enx/{print $2; exit}')
if [ -z "$ETH_IF" ]; then
    echo "  [!] Kein Ethernet-Adapter gefunden."
    echo "  WOL-Relay muss per LAN-Kabel angeschlossen sein."
    echo ""
    read -p "  Trotzdem fortfahren? (j/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[JjYy]$ ]]; then exit 1; fi
else
    ETH_STATE=$(cat /sys/class/net/$ETH_IF/operstate 2>/dev/null || echo "unknown")
    if [ "$ETH_STATE" = "up" ]; then
        echo "  [✓] Ethernet: $ETH_IF (verbunden)"
    else
        echo "  [!] Ethernet: $ETH_IF (nicht verbunden — Kabel anschliessen!)"
    fi
fi

# ── 1. System updaten ───────────────────────────────────

echo ""
echo "  [1/4] System aktualisieren..."
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

# ── 2. wakeonlan installieren ───────────────────────────

echo "  [2/4] wakeonlan installieren..."
sudo apt-get install -y -qq wakeonlan

echo "  [✓] wakeonlan $(wakeonlan --version 2>/dev/null || echo 'installiert')"

# ── 3. Tailscale installieren ───────────────────────────

echo "  [3/4] Tailscale installieren..."
if command -v tailscale &>/dev/null; then
    echo "  [✓] Tailscale bereits installiert"
else
    curl -fsSL https://tailscale.com/install.sh | sh
fi

# Tailscale starten falls noch nicht verbunden
TS_STATUS=$(sudo tailscale status 2>&1 || true)
if echo "$TS_STATUS" | grep -q "Logged out\|stopped\|NeedsLogin"; then
    echo ""
    echo "  Tailscale muss einmalig angemeldet werden."
    echo "  Ein Login-Link wird gleich angezeigt — im Browser oeffnen."
    echo ""
    sudo tailscale up
fi

TS_IP=$(tailscale ip -4 2>/dev/null || echo "nicht verfuegbar")
echo "  [✓] Tailscale IP: $TS_IP"

# ── 4. SSH absichern ────────────────────────────────────

echo "  [4/4] SSH konfigurieren..."

# SSH aktivieren falls nicht aktiv
if ! systemctl is-active --quiet ssh; then
    sudo systemctl enable ssh
    sudo systemctl start ssh
    echo "  [✓] SSH aktiviert"
else
    echo "  [✓] SSH bereits aktiv"
fi

# ── Fertig ──────────────────────────────────────────────

LOCAL_IP=$(hostname -I | awk '{print $1}')
HOSTNAME=$(hostname)

echo ""
echo "  ════════════════════════════════════════════════"
echo "  WOL Relay ist bereit!"
echo "  ════════════════════════════════════════════════"
echo ""
echo "  Hostname:      $HOSTNAME"
echo "  Lokale IP:     $LOCAL_IP"
echo "  Tailscale IP:  $TS_IP"
echo ""
echo "  ── Naechste Schritte ──────────────────────────"
echo ""
echo "  1. SSH-Key vom NEXUS Brain kopieren:"
echo ""
echo "     Auf dem Brain ausfuehren:"
echo "     ssh-copy-id -i ~/.ssh/pi_manager_rsa $(whoami)@$TS_IP"
echo ""
echo "  2. Testen ob WOL funktioniert:"
echo ""
echo "     ssh -i ~/.ssh/pi_manager_rsa $(whoami)@$TS_IP wakeonlan AA:BB:CC:DD:EE:FF"
echo "     (MAC-Adresse des Ziel-PCs einsetzen)"
echo ""
echo "  3. In NEXUS config/devices.yaml eintragen:"
echo ""
echo "     pis:"
echo "       - id: relay_friend"
echo "         name: \"WOL Relay (Freund)\""
echo "         plugin: pi_manager"
echo "         hostname: $TS_IP"
echo "         ssh_user: $(whoami)"
echo "         ssh_key: \"~/.pi-manager/keys/id_rsa\""
echo "         role: relay"
echo ""
echo "  4. PC des Freundes mit wol_relay registrieren:"
echo ""
echo "     computers:"
echo "       - id: friends_pc"
echo "         name: \"Freund PC\""
echo "         plugin: pc_control"
echo "         mac_address: \"AA:BB:CC:DD:EE:FF\""
echo "         ip: <tailscale-ip-des-pcs>"
echo "         os: windows"
echo "         wol_relay: relay_friend"
echo ""
echo "  ════════════════════════════════════════════════"
echo ""
