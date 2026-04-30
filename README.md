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

#### Schritt 1: Tailscale-Zugang

Dein Freund braucht Zugang zu deinem Tailscale-Netzwerk, damit er das Dashboard (auf dem Pi) und seinen eigenen PC erreichen kann.

1. Öffne [Tailscale Admin Console](https://login.tailscale.com/admin/users)
2. Gehe zu **Users → Invite users**
3. Gib die E-Mail deines Freundes ein und sende die Einladung
4. Dein Freund installiert Tailscale auf **beiden** Geräten:
   - Seinem **Mac/Laptop** (von dem er zugreift)
   - Seinem **Windows-PC** (der ferngesteuert werden soll)
5. Er meldet sich auf beiden mit der Einladung an — beide sind jetzt im Tailnet

> **Tailscale Free** erlaubt bis zu 3 Benutzer und 100 Geräte — mehr als genug.

#### Schritt 2: PC des Freundes vorbereiten

Auf dem **Windows-PC deines Freundes**:

1. **Tailscale installieren** und mit der Einladung anmelden
2. **Remotedesktop aktivieren**: Einstellungen → System → Remotedesktop → An
3. **NEXUS Agent installieren** (elevated PowerShell):
   ```powershell
   $env:NEXUS_BRAIN="<tailscale-ip-des-pi>"; irm https://werizu.github.io/nexus/install.ps1 | iex
   ```
   Dabei eine eigene `device_id` vergeben (z.B. `friends_pc`)
4. **Tailscale IP notieren**: `tailscale ip -4` → z.B. `100.x.x.x`

#### Schritt 3: PC im NEXUS-Dashboard registrieren

1. Melde dich als Admin im Dashboard an
2. Gehe zu **Geräte → + Neues Gerät**
3. Kategorie: **Computer**, Plugin: **pc_control**
4. Trage ein:
   - Name: z.B. "Freund PC"
   - Device ID: `friends_pc` (muss zur Agent-Config passen)
   - IP: Tailscale-IP des PCs
   - MAC-Adresse: für Wake-on-LAN
   - OS: `windows`
5. Speichern

#### Schritt 4: NEXUS-Account für den Freund anlegen

1. Dashboard → **Zahnrad-Icon** (oben rechts) → **Benutzerverwaltung**
2. **+ Neuer Benutzer** → Benutzername, Passwort, Rolle (`user`)
3. Zugangsdaten dem Freund mitteilen

Dein Freund kann sich jetzt unter `http://<tailscale-ip-des-pi>` einloggen und seinen eigenen PC starten, steuern und per RDP verbinden.

#### Zusammenfassung

| Was | Wo |
|---|---|
| Tailscale einladen | [admin.tailscale.com](https://login.tailscale.com/admin/users) → Invite |
| Agent auf Freund-PC | PowerShell Installer mit eigener device_id |
| PC registrieren | Dashboard → Geräte → + Neues Gerät |
| NEXUS-Account anlegen | Dashboard → Zahnrad → + Neuer Benutzer |
| Dashboard-Zugang | `http://<tailscale-ip-des-pi>` im Browser |

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
