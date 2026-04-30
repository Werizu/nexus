# NEXUS

Self-hosted Smart Home System — runs on a Raspberry Pi, controls lights, plugs, PCs, and more from a single dashboard. Multi-user support, remote access via Tailscale, voice control with Alexa.

## Architecture

```
                          ┌─────────────────────────────────┐
                          │         Tailscale Mesh VPN       │
                          │    (secure access from anywhere) │
                          └──────────┬──────────────────────┘
                                     │
┌──────────────┐     MQTT      ┌─────┴────────┐     HTTP      ┌──────────────┐
│  NEXUS Agent │◄─────────────►│  NEXUS Brain  │◄─────────────►│  Dashboard   │
│  (Win / Mac) │               │  (FastAPI)    │               │  (React PWA) │
└──────────────┘               └──────┬────────┘               └──────────────┘
                                      │
              ┌───────────┬───────────┼───────────┬───────────┐
              │           │           │           │           │
         Hue/IKEA     Tasmota     Pi Manager   Alexa      Jarvis
         Lights       Plugs       SSH Metrics  Skill      Bridge
```

**Brain** — FastAPI backend on a Raspberry Pi. Manages devices via plugins, runs scenes, serves the REST API. JWT-based authentication with multi-user support.

**Agent** — Python service on Windows and macOS PCs. Reports system metrics (CPU/RAM/GPU/disk/network), accepts remote commands (shutdown, restart, launch programs), sends alerts via MQTT.

**Dashboard** — React PWA with real-time WebSocket updates. Device control, scene management, Pi monitoring, alerts, room management, and user settings. Fully customizable — all devices, rooms, and scenes are editable from the UI.

**MQTT** — Mosquitto broker. All communication between Brain, Agents, and plugins runs over MQTT.

**Tailscale** — Mesh VPN for secure remote access. All devices communicate via Tailscale IPs, allowing full control from anywhere without port forwarding.

## Features

- **Device Control** — Philips Hue, IKEA Tradfri, Tasmota smart plugs, PCs (WOL + Agent), Raspberry Pis
- **Scene Automation** — YAML-based multi-device scenes with delays, conditions, and wait-for-online logic
- **PC Agent (Windows)** — Remote shutdown/restart/sleep/lock, system monitoring, process management, GPU metrics, alerts
- **Mac Agent** — Open apps/URLs, RDP connections, SSH terminals, volume/brightness control, dark mode, screenshots
- **Pi Manager** — SSH-based metrics (CPU, RAM, temp, disk, uptime) from all Pis in the network
- **Alexa Integration** — Custom skill endpoint for voice-triggered scenes and device control
- **Real-time Dashboard** — Live device status, scene/device/room editors, Pi monitor, alerts panel, logs
- **Energy Monitoring** — Power consumption tracking via Tasmota plugs
- **Multi-User Auth** — JWT-based login, user management, admin/user roles, password management
- **Remote Access** — Tailscale mesh VPN — control your home from anywhere (university, travel, etc.)
- **Room Management** — Organize devices into rooms with custom icons, controllable as groups

## Requirements

- Raspberry Pi (3B+ or newer) with Raspbian/Debian
- Docker & Docker Compose
- Python 3.10+ (on managed PCs for the Agent)
- Tailscale (optional, for remote access)

## Installation

### 1. Brain (Raspberry Pi)

```bash
# Clone the repo
git clone https://github.com/Werizu/nexus.git
cd nexus

# Configure your devices
cp config/secrets.yaml.example config/secrets.yaml
nano config/devices.yaml    # Add your devices (lights, plugs, PCs, Pis)
nano config/secrets.yaml    # Add API keys (Hue bridge key, etc.)
nano config/nexus.yaml      # Set MQTT broker IP, system settings

# Build and start
sudo docker compose up -d
```

The Brain starts three containers:
- `nexus-brain` — FastAPI backend on port 8000
- `nexus-mqtt` — Mosquitto broker on port 1883
- `nexus-web` — Nginx serving the dashboard on port 80

### 2. Dashboard

Open `http://<pi-ip>` in your browser. On first launch, a default admin user is created:

- **Username:** `admin`
- **Password:** `nexus`

**Change your password immediately** via the settings icon (gear icon, top right).

### 3. Agent (Windows PC)

Run in an **elevated PowerShell**:

```powershell
irm https://werizu.github.io/nexus/install.ps1 | iex
```

Or with a custom Brain IP:

```powershell
$env:NEXUS_BRAIN="100.122.236.58"; irm https://werizu.github.io/nexus/install.ps1 | iex
```

The agent installs as a Windows service (`NexusAgent`) and auto-connects to the Brain via MQTT.

**Agent capabilities:**
- System metrics (CPU, RAM, GPU, disk, network)
- Remote commands (shutdown, restart, sleep, lock)
- Process management (list, kill)
- Alert thresholds (CPU, RAM, disk, GPU temp)
- Wake-on-LAN support

#### Wake-on-LAN einrichten

Damit der PC über das Dashboard aus dem Schlaf oder ausgeschaltetem Zustand geweckt werden kann, muss WOL im BIOS und in Windows aktiviert sein.

**1. BIOS/UEFI:**
1. PC neustarten und ins BIOS gehen (meist `DEL`, `F2` oder `F12` beim Hochfahren)
2. Suche nach **Wake on LAN**, **Wake on PCI(E)**, **Power On By PCI-E** oder **ErP Ready**
3. Wake on LAN: **Enabled**
4. ErP Ready / Deep Sleep: **Disabled** (sonst wird der Netzwerkadapter komplett stromlos)
5. Speichern und neustarten

**2. Windows Netzwerkadapter:**
1. **Geräte-Manager** öffnen (`devmgmt.msc`)
2. **Netzwerkadapter** → Rechtsklick auf den Ethernet-Adapter → **Eigenschaften**
3. Tab **Erweitert**:
   - *Wake on Magic Packet*: **Enabled**
   - *Wake on Pattern Match*: **Enabled**
   - *Energy Efficient Ethernet*: **Disabled** (falls vorhanden)
4. Tab **Energieverwaltung**:
   - ☑ *Computer kann das Gerät ausschalten, um Energie zu sparen*
   - ☑ *Gerät kann den Computer aus dem Ruhezustand aktivieren*
   - ☑ *Nur Magic Packet kann den Computer aus dem Ruhezustand aktivieren*

**3. Windows Energieoptionen:**
1. **Einstellungen → System → Netzbetrieb → Schnellstart**: **Aus** (Schnellstart verhindert WOL bei vollständigem Herunterfahren)
2. Alternativ: PC per `Ruhezustand` oder `Energie sparen` statt `Herunterfahren` ausschalten — WOL funktioniert damit zuverlässiger

**4. MAC-Adresse herausfinden:**
```powershell
getmac /v
```
Die MAC-Adresse des Ethernet-Adapters (Format `AA-BB-CC-DD-EE-FF`) wird in `config/devices.yaml` als `mac_address` eingetragen.

> **Wichtig:** WOL funktioniert nur über **Ethernet** (Kabel), nicht über WLAN. Der PC muss per LAN-Kabel angeschlossen sein.

### 4. Agent (macOS)

Run in **Terminal**:

```bash
curl -fsSL https://werizu.github.io/nexus/install-mac.sh | bash
```

Or with a custom Brain IP:

```bash
NEXUS_BRAIN="100.122.236.58" curl -fsSL https://werizu.github.io/nexus/install-mac.sh | bash
```

The agent installs as a LaunchAgent and auto-starts on login.

**Agent capabilities:**
- System metrics (CPU, RAM, disk, network)
- Open apps, URLs, SSH terminals
- RDP connections (via Windows App)
- Volume and brightness control
- Dark mode toggle
- Screenshots
- Notifications

### 5. Tailscale (Remote Access)

Install [Tailscale](https://tailscale.com) on all devices (Pi, PCs, phones) for secure remote access without port forwarding.

```bash
# On the Pi
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Note your Tailscale IP (100.x.x.x)
tailscale ip -4
```

Update `config/nexus.yaml` and `config/devices.yaml` to use Tailscale IPs. The dashboard is then accessible from anywhere via `http://<tailscale-ip>`.

### 6. Anderen Benutzer einrichten (Multi-User)

NEXUS unterstützt mehrere Benutzer — z.B. ein Freund, der seinen eigenen PC von unterwegs per RDP steuern will.

#### Das Problem: WOL über Tailscale

Wake-on-LAN funktioniert nur im lokalen Netzwerk (Layer 2 Broadcast). Wenn der PC deines Freundes bei ihm zuhause steht und ausgeschaltet ist, läuft kein Tailscale — der Brain kann ihn nicht direkt aufwecken.

**Lösung: WOL-Relay über einen Raspberry Pi**

Ein kleiner Pi (Zero W reicht) steht im Netzwerk deines Freundes, läuft 24/7, hat Tailscale, und leitet WOL-Pakete ins lokale Netz weiter.

```
Freund an der Uni                  Freundes Netzwerk zuhause
┌──────────┐                      ┌────────────┐     LAN      ┌──────────┐
│ MacBook  │───── Tailscale ─────►│ Relay Pi   │──── WOL ────►│ Freund   │
│ Dashboard│                      │ (Pi Zero W)│   Broadcast   │ PC (aus) │
└──────────┘                      └────────────┘               └──────────┘
       │                                │
       │         Tailscale              │
       └────────────────────────────────┘
                    │
              ┌─────┴──────┐
              │ NEXUS Brain │
              │ (dein Pi)   │
              └────────────┘
```

#### Schritt 1: Relay-Pi vorbereiten

**Hardware:** Raspberry Pi Zero W, Zero 2 W, 3B, oder neuer — alles was Netzwerk hat reicht. Verbrauch: ~0.5-1W (Pi Zero W).

**Voraussetzung:** Raspberry Pi OS Lite (headless) ist installiert, SSH ist aktiviert, und der Pi ist per **Ethernet (LAN-Kabel)** am selben Router/Switch wie der PC angeschlossen.

> **Wichtig:** WOL-Broadcasts funktionieren nicht über WLAN. Der Relay-Pi muss per Kabel im selben Netzwerk wie der Ziel-PC sein.

**Setup — ein Befehl auf dem Relay-Pi:**

```bash
curl -fsSL https://werizu.github.io/nexus/setup-relay.sh | bash
```

Das Script installiert automatisch Tailscale + `wakeonlan`, prüft die Ethernet-Verbindung, und zeigt am Ende alle nächsten Schritte mit den richtigen IPs an.

**Danach auf dem NEXUS Brain — SSH-Key kopieren:**

```bash
ssh-copy-id -i ~/.ssh/pi_manager_rsa <user>@<relay-tailscale-ip>
```

#### Schritt 2: Tailscale-Zugang für den Freund

1. Öffne [Tailscale Admin Console](https://login.tailscale.com/admin/users)
2. **Users → Invite users** → E-Mail des Freundes eingeben
3. Freund installiert Tailscale auf seinem **Mac/Laptop** und meldet sich an

> **Tailscale Free** erlaubt bis zu 3 Benutzer und 100 Geräte.

#### Schritt 3: PC und Relay-Pi registrieren

Den **Relay-Pi** in `config/devices.yaml` als Pi registrieren:

```yaml
pis:
  - id: relay_friend
    name: "Relay Pi (Freund)"
    plugin: pi_manager
    hostname: 100.x.x.x          # Tailscale IP des Relay-Pi
    ssh_user: marlon
    ssh_key: "~/.pi-manager/keys/id_rsa"
    role: relay
```

Den **PC des Freundes** mit `wol_relay` Feld registrieren:

```yaml
computers:
  - id: friends_pc
    name: "Freund PC"
    plugin: pc_control
    mac_address: "AA:BB:CC:DD:EE:FF"
    ip: 100.x.x.x                # Tailscale IP des PCs
    os: windows
    check_port: 3389
    wol_relay: relay_friend       # WOL wird über diesen Pi gesendet
```

Das `wol_relay` Feld sagt dem Brain: "Wenn dieser PC geweckt werden soll, sende das WOL-Paket nicht lokal, sondern per SSH über den angegebenen Pi."

Alternativ können Geräte auch über das Dashboard registriert werden (Geräte → + Neues Gerät).

#### Schritt 4: Windows-PC vorbereiten

Auf dem **Windows-PC des Freundes**:

1. **Tailscale installieren** und mit der Einladung anmelden
2. **Wake-on-LAN aktivieren** (siehe [WOL einrichten](#wake-on-lan-einrichten) weiter oben)
3. **Remotedesktop aktivieren**: Einstellungen → System → Remotedesktop → An
4. **NEXUS Agent installieren** (elevated PowerShell):
   ```powershell
   $env:NEXUS_BRAIN="<tailscale-ip-des-brain>"; irm https://werizu.github.io/nexus/install.ps1 | iex
   ```
   Device ID: `friends_pc` (muss zur Config passen)

#### Schritt 5: NEXUS-Account anlegen

1. Dashboard → **Zahnrad-Icon** → **Benutzerverwaltung**
2. **+ Neuer Benutzer** → Benutzername, Passwort, Rolle (`user`)
3. Zugangsdaten dem Freund mitteilen

#### Ablauf für den Freund

1. `http://<tailscale-ip-des-brain>` im Browser öffnen
2. Mit seinem Account einloggen
3. Auf "Freund PC" → **Wake** klicken
   - Brain sendet SSH-Befehl an Relay-Pi
   - Relay-Pi sendet WOL-Broadcast ins lokale Netz
   - PC wacht auf, Tailscale startet automatisch
4. Per RDP verbinden (Windows App auf dem Mac)

#### Zusammenfassung

| Gerät | Standort | Rolle | Muss 24/7 laufen? |
|---|---|---|---|
| NEXUS Brain (dein Pi) | Bei dir | Backend, Dashboard | Ja |
| Relay-Pi (z.B. Pi Zero W) | Beim Freund | WOL-Relay | Ja (~0.5W) |
| Freund PC | Beim Freund | Wird ferngesteuert | Nein (wird per WOL geweckt) |
| Freund MacBook | Mobil | Dashboard + RDP Client | Nein |

| Was | Wo / Wie |
|---|---|
| Tailscale einladen | [admin.tailscale.com](https://login.tailscale.com/admin/users) → Invite |
| Relay-Pi einrichten | Tailscale + `wakeonlan` installieren, per LAN anschließen |
| PC + Relay registrieren | `config/devices.yaml` mit `wol_relay` Feld |
| Agent auf Freund-PC | PowerShell Installer mit `device_id: friends_pc` |
| NEXUS-Account | Dashboard → Zahnrad → + Neuer Benutzer |

## Configuration

### devices.yaml

```yaml
devices:
  computers:
    - id: main_pc
      name: Desktop PC
      plugin: pc_control
      mac_address: "AA:BB:CC:DD:EE:FF"
      ip: 100.123.253.88           # Tailscale IP
      os: windows
      check_port: 3389

    - id: main_mac
      name: MacBook
      plugin: pc_control
      os: macos

  pis:
    - id: brain
      name: NEXUS Brain
      plugin: pi_manager
      hostname: 100.122.236.58
      ssh_user: marlon
      ssh_key: "~/.pi-manager/keys/id_rsa"
      role: primary

  lights:
    - id: light_1
      name: Wohnzimmer Licht
      plugin: hue_lights
      bridge_ip: 192.168.178.48    # Hue Bridge stays on local IP
      hue_id: "3"

  plugs:
    - id: plug_pc
      name: PC Steckdose
      plugin: hue_lights
      bridge_ip: 192.168.178.48
      hue_id: "8"
```

### Scenes (scenes/*.yaml)

```yaml
name: dev_mode
display_name: "Programmier-Modus"
icon: code
color: "#00D4FF"
triggers:
  alexa:
    - "Programmier-Modus"
    - "wir programmieren was"
conditions:
  time_range: "07:00-02:00"
actions:
  - device: plug_pc
    command: "on"
  - delay: 10
  - device: main_pc
    command: wake
    wait_for_online: true
    timeout: 90
  - delay: 15
  - device: main_mac
    command: rdp_connect
  - device: main_mac
    command: open_url
    params:
      url: "http://100.122.236.58"
```

Scenes support:
- **Delays** between actions
- **Conditions** (time ranges)
- **Wait-for-online** with timeout (e.g., wait until PC boots)
- **Alexa triggers** (voice phrases)
- **Scheduled triggers** (cron-style)

### Agent Config (agent/config.yaml)

```yaml
mqtt:
  broker: "100.122.236.58"
  port: 1883
  client_id: "nexus-agent-pc"

agent:
  device_id: "main_pc"
  name: "Desktop PC"
  report_interval: 10

alerts:
  cpu: 90        # CPU usage %
  ram: 90        # RAM usage %
  disk: 90       # Disk usage %
  gpu_temp: 85   # GPU temperature °C
  gpu_load: 95   # GPU load %
  cooldown: 300  # Seconds between repeated alerts
```

## Dashboard

### Tabs

| Tab | Description |
|---|---|
| **Dashboard** | Overview — scenes, all devices, Pi status, active alerts |
| **Geräte** | Device management — add, edit, delete devices by category |
| **Szenen** | Scene management — create, edit, delete automation scenes |
| **Räume** | Room management — organize devices into rooms with icons |
| **Pi Monitor** | Raspberry Pi metrics — CPU, RAM, temperature, disk, uptime |
| **Alerts** | Alert history — acknowledge individual or all alerts |
| **Logs** | System log viewer |

### Settings (gear icon)

- **Profile** — change display name
- **Password** — change password
- **User Management** (admin only) — create users, assign roles (admin/user), delete users

### Adding Devices

1. Go to **Geräte** tab
2. Click **+ Neues Gerät**
3. Select category (Computer, Pi, Lights, Plugs, Cameras, Speakers)
4. Fill in device-specific config (IP, MAC, Hue ID, etc.)
5. Save — device appears immediately

### Creating Scenes

1. Go to **Szenen** tab
2. Click **+ Neue Szene**
3. Name the scene, pick an icon and color
4. Add actions: select device, command, and parameters
5. Save — scene is triggerable from dashboard, API, or Alexa

### Managing Rooms

1. Go to **Räume** tab
2. Click **+ Neuer Raum**
3. Name the room, pick an icon
4. Assign devices by clicking on them
5. Save — room appears with grouped device controls

## Multi-User System

NEXUS supports multiple users with role-based access:

| Role | Permissions |
|---|---|
| **admin** | Full access — manage devices, scenes, rooms, users |
| **user** | Control devices, trigger scenes, view status |

### User Management

Admins can manage users via the settings panel (gear icon → Benutzerverwaltung):
- Create new users with username, display name, password, and role
- Promote/demote users between admin and user roles
- Delete users

### API Authentication

All API endpoints (except `/api/v1/health` and `/api/v1/alexa`) require a JWT token:

```bash
# Login
curl -X POST http://<ip>/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"nexus"}'

# Use the token
curl http://<ip>/api/v1/devices \
  -H 'Authorization: Bearer <token>'
```

Tokens are valid for 30 days.

## API Reference

Base URL: `http://<pi-ip>/api/v1`

### Authentication

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/auth/login` | POST | — | Login, returns JWT token |
| `/auth/register` | POST | Admin | Create new user |
| `/auth/me` | GET | User | Current user info |
| `/auth/password` | PUT | User | Change own password |
| `/auth/users` | GET | Admin | List all users |
| `/auth/users/{username}` | PUT | Admin | Update user (role, display name) |
| `/auth/users/{username}` | DELETE | Admin | Delete user |

### Devices

| Endpoint | Method | Description |
|---|---|---|
| `/devices` | GET | All devices with current state |
| `/devices` | POST | Register a new device |
| `/devices/{id}` | GET | Single device details |
| `/devices/{id}` | PUT | Update device config |
| `/devices/{id}` | DELETE | Remove device |
| `/devices/{id}/command` | POST | Send command (`{"command": "on", "params": {}}`) |

### Scenes

| Endpoint | Method | Description |
|---|---|---|
| `/scenes` | GET | List all scenes |
| `/scenes` | POST | Create scene |
| `/scenes/{name}` | GET | Scene details |
| `/scenes/{name}` | PUT | Update scene |
| `/scenes/{name}` | DELETE | Delete scene |
| `/scenes/{name}/trigger` | POST | Execute scene |

### Rooms

| Endpoint | Method | Description |
|---|---|---|
| `/rooms` | GET | All rooms with assigned devices |
| `/rooms` | POST | Create room |
| `/rooms/{id}` | PUT | Update room |
| `/rooms/{id}` | DELETE | Delete room |

### System

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | System health + plugin status (no auth) |
| `/pis` | GET | Pi metrics (CPU, RAM, temp, disk) |
| `/alerts` | GET | Alert history |
| `/alerts/{id}/ack` | POST | Acknowledge alert |
| `/alerts/ack-all` | POST | Acknowledge all alerts |
| `/logs` | GET | System logs |
| `/alexa` | POST | Alexa skill endpoint (no auth) |

### WebSocket

Connect to `ws://<pi-ip>/ws/realtime` for real-time events:

```json
{"event": "device_update", "device_id": "main_pc", "state": {...}}
{"event": "scene_complete", "scene": "dev_mode"}
{"event": "alert", "device_id": "main_pc", "type": "cpu", "value": 95}
```

## Plugins

| Plugin | Type | Devices | Protocol |
|---|---|---|---|
| `hue_lights` | light | Philips Hue, IKEA (via Hue Bridge) | HTTP API |
| `ikea_lights` | light | IKEA Tradfri (direct) | CoAP |
| `tasmota` | plug | Tasmota-flashed smart plugs | HTTP + MQTT |
| `pc_control` | computer | Windows/macOS PCs | MQTT Agent + WOL |
| `pi_manager` | pi | Raspberry Pis | SSH |
| `alexa_bridge` | assistant | Amazon Alexa | HTTP Skill API |
| `jarvis_bridge` | assistant | Jarvis voice assistant | MQTT |

## Maintenance

### Updating

```bash
cd ~/nexus
git pull
sudo docker compose build nexus-brain --no-cache
sudo docker compose up -d
```

For frontend changes:

```bash
cd web && npm run build && cd ..
sudo docker compose restart nexus-web
```

### Logs

```bash
# Brain logs
sudo docker logs nexus-brain --tail 50 -f

# MQTT logs
sudo docker logs nexus-mqtt --tail 20

# Agent logs (Windows)
Get-Content "C:\Program Files\NEXUS Agent\nexus-agent.log" -Tail 20

# Agent logs (macOS)
tail -f ~/.nexus-agent/nexus-agent-mac.log
```

### Agent Service (Windows)

```powershell
Get-Service NexusAgent          # Status
Restart-Service NexusAgent      # Restart
Stop-Service NexusAgent         # Stop

# Uninstall
python "C:\Program Files\NEXUS Agent\nexus_service.py" remove
```

### Agent Service (macOS)

```bash
launchctl list | grep nexus                                          # Status
launchctl unload ~/Library/LaunchAgents/com.nexus.agent.plist        # Stop
launchctl load ~/Library/LaunchAgents/com.nexus.agent.plist          # Start

# Uninstall
launchctl unload ~/Library/LaunchAgents/com.nexus.agent.plist
rm -rf ~/.nexus-agent ~/Library/LaunchAgents/com.nexus.agent.plist
```

### Backup

```bash
tar czf nexus-backup-$(date +%F).tar.gz config/ scenes/ data/
```

Important data:
- `config/` — device config, rooms, secrets
- `scenes/` — automation scenes
- `data/nexus.db` — device state, users, logs (SQLite)

## Tech Stack

| Component | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Frontend | React 19, Vite, Tailwind CSS |
| Database | SQLite (aiosqlite) |
| Messaging | MQTT (Mosquitto) |
| Auth | JWT (PyJWT, HS256, 30-day tokens) |
| Deployment | Docker Compose, Nginx |
| VPN | Tailscale |
| Device APIs | Philips Hue REST, Tasmota HTTP, SSH (Paramiko), WOL |

## Project Structure

```
nexus/
├── agent/              # Windows PC Agent (Python service)
│   ├── nexus_agent.py      # Agent main (MQTT + monitoring)
│   ├── nexus_service.py    # Windows service wrapper
│   ├── config.yaml         # Agent config
│   └── install.ps1         # One-line installer
├── agent-mac/          # macOS Agent (LaunchAgent)
│   ├── nexus_agent_mac.py  # Agent main (MQTT + macOS commands)
│   ├── config.yaml         # Agent config
│   └── install.sh          # One-line installer
├── config/             # System configuration
│   ├── devices.yaml        # Device registry
│   ├── rooms.yaml          # Room definitions
│   ├── nexus.yaml          # System settings
│   ├── secrets.yaml        # API keys (gitignored)
│   ├── mosquitto.conf      # MQTT broker config
│   └── nginx.conf          # Web server config
├── core/               # FastAPI backend
│   ├── main.py             # API routes + auth
│   ├── config.py           # Config loader
│   ├── state_store.py      # SQLite store (devices, users, logs)
│   ├── plugin_manager.py   # Plugin discovery + lifecycle
│   ├── scene_engine.py     # Scene execution engine
│   ├── mqtt_client.py      # MQTT client
│   ├── scheduler.py        # Cron-style scheduler
│   └── websocket_server.py # Real-time WebSocket
├── plugins/            # Device plugins
│   ├── base_plugin.py      # Base class for all plugins
│   ├── hue/                # Philips Hue + IKEA (via Bridge)
│   ├── ikea/               # IKEA Tradfri (direct CoAP)
│   ├── tasmota/            # Tasmota smart plugs
│   ├── pc_control/         # PC control (WOL + MQTT Agent)
│   ├── pi_manager/         # Raspberry Pi monitoring (SSH)
│   ├── alexa_bridge/       # Alexa voice control
│   └── jarvis_bridge/      # Jarvis voice assistant
├── scenes/             # YAML automation scenes
├── web/                # React + Vite dashboard
│   ├── src/
│   │   ├── App.jsx             # Main app + routing
│   │   ├── components/
│   │   │   ├── LoginScreen.jsx     # Authentication
│   │   │   ├── Header.jsx          # Status bar + settings
│   │   │   ├── DeviceCard.jsx      # Device control card
│   │   │   ├── DeviceEditor.jsx    # Add/edit devices
│   │   │   ├── SceneCard.jsx       # Scene trigger card
│   │   │   ├── SceneEditor.jsx     # Add/edit scenes
│   │   │   ├── RoomView.jsx        # Room device groups
│   │   │   ├── RoomEditor.jsx      # Add/edit rooms
│   │   │   ├── PiMonitor.jsx       # Pi metrics display
│   │   │   ├── AlertsPanel.jsx     # Alert management
│   │   │   ├── LogViewer.jsx       # Log viewer
│   │   │   └── SettingsPanel.jsx   # User settings + admin
│   │   └── hooks/
│   │       └── useNexus.js         # API hooks + WebSocket
│   └── dist/               # Built frontend (served by nginx)
├── docs/               # GitHub Pages (install scripts)
├── Dockerfile
├── docker-compose.yaml
└── requirements.txt
```

## License

Private project by [Werizu](https://github.com/Werizu).
