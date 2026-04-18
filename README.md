# NEXUS

Self-hosted Smart Home System — runs on a Raspberry Pi, controls lights, plugs, PCs, and more from a single dashboard.

## Architecture

```
┌──────────────┐     MQTT      ┌──────────────┐
│  NEXUS Agent │◄─────────────►│  NEXUS Brain │
│  (Windows PC)│               │  (FastAPI)   │
└──────────────┘               └──────┬───────┘
                                      │
              ┌───────────┬───────────┼───────────┬───────────┐
              │           │           │           │           │
         Hue/IKEA     Tasmota     Pi Manager   Alexa      Jarvis
         Lights       Plugs       SSH Metrics  Skill      Bridge
```

**Brain** — FastAPI backend on a Raspberry Pi. Manages devices via plugins, runs scenes, serves the API.

**Agent** — Python service on managed PCs. Reports system metrics (CPU/RAM/GPU/disk/network), accepts remote commands (shutdown, restart, launch programs), sends alerts.

**Dashboard** — React PWA with real-time WebSocket updates. Device control, scene management, Pi monitoring, alerts.

**MQTT** — Mosquitto broker. All communication between Brain, Agent, and plugins runs over MQTT.

## Features

- **Device Control** — Philips Hue, IKEA Tradfri, Tasmota smart plugs, PCs (WOL + Agent), Raspberry Pis
- **Scene Automation** — YAML-based multi-device scenes, triggerable via API, dashboard, or Alexa
- **PC Agent** — Remote shutdown/restart/sleep/lock, system monitoring, process management, alerts with configurable thresholds
- **Pi Manager** — SSH-based metrics collection from all Pis in the network
- **Alexa Integration** — Direct skill endpoint, voice-triggered scenes and device control
- **Real-time Dashboard** — Live device status, scene editor, Pi monitor, alerts panel, logs
- **Energy Monitoring** — Power consumption tracking via Tasmota plugs

## Requirements

- Raspberry Pi (3B+ or newer) with Raspbian/Debian
- Docker & Docker Compose
- Python 3.10+ (on managed PCs for the Agent)

## Installation

### 1. Brain (Raspberry Pi)

```bash
# Clone the repo
git clone https://github.com/Werizu/nexus.git
cd nexus

# Copy and edit config
cp config/nexus.yaml.example config/nexus.yaml
# Edit config/devices.yaml with your devices
# Edit config/secrets.yaml with API keys (Hue, etc.)

# Build and start
sudo docker compose up -d
```

The Brain starts three containers:
- `nexus-brain` — FastAPI on port 8000
- `nexus-mqtt` — Mosquitto on port 1883
- `nexus-web` — Nginx serving the dashboard on port 80

### 2. Dashboard (Frontend)

The dashboard is pre-built in `web/dist/` and served by nginx. To rebuild after changes:

```bash
cd web
npm install
npm run build
# Restart nginx container
sudo docker compose restart nexus-web
```

Open `http://<pi-ip>` in your browser.

### 3. Agent (Windows PC)

Run in an **elevated PowerShell**:

```powershell
irm https://werizu.github.io/nexus/install.ps1 | iex
```

Or with a custom Brain IP:

```powershell
$env:NEXUS_BRAIN="192.168.178.100"; irm https://werizu.github.io/nexus/install.ps1 | iex
```

The agent installs as a Windows service (`NexusAgent`) and auto-connects to the Brain.

### 4. Agent (macOS)

Run in **Terminal**:

```bash
curl -fsSL https://werizu.github.io/nexus/install-mac.sh | bash
```

Or with a custom Brain IP:

```bash
NEXUS_BRAIN="192.168.178.100" curl -fsSL https://werizu.github.io/nexus/install-mac.sh | bash
```

The agent installs as a LaunchAgent and auto-starts on login. Commands: open apps/URLs, SSH terminals, RDP connect, notifications, volume, brightness, dark mode, screenshots, system monitoring.

## Configuration

### devices.yaml

```yaml
computers:
  - id: main_pc
    name: Desktop PC
    plugin: pc_control
    mac: "AA:BB:CC:DD:EE:FF"
    ip: 192.168.178.100

lights:
  - id: office_light
    name: Büro Licht
    plugin: hue_lights
    light_id: 1

plugs:
  - id: monitor_strip
    name: Monitor Steckdose
    plugin: tasmota
    ip: 192.168.178.50
```

### Scenes (scenes/*.yaml)

```yaml
name: dev_mode
icon: "💻"
color: "#00D4FF"
actions:
  - device: office_light
    command: "on"
    params:
      brightness: 100
  - device: main_pc
    command: wake
  - delay: 3
  - device: monitor_strip
    command: "on"
```

### Agent Alerts (agent/config.yaml)

```yaml
alerts:
  cpu: 90        # CPU usage %
  ram: 90        # RAM usage %
  disk: 90       # Disk usage %
  gpu_temp: 85   # GPU temperature °C
  gpu_load: 95   # GPU load %
  cooldown: 300  # Seconds between repeated alerts
```

## Maintenance

### Updating

```bash
cd ~/nexus
git pull
sudo docker compose build nexus-brain --no-cache
sudo docker compose up -d
```

For frontend changes, rebuild first:

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

The important data lives in:
- `config/` — device config, secrets, rooms
- `scenes/` — automation scenes
- `data/nexus.db` — device state and logs (SQLite)

```bash
tar czf nexus-backup-$(date +%F).tar.gz config/ scenes/ data/
```

## API

Base URL: `http://<pi-ip>:8000/api/v1`

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | System health + plugin status |
| `/devices` | GET | All devices with state |
| `/devices/{id}/command` | POST | Send command to device |
| `/scenes` | GET | List scenes |
| `/scenes/{name}/trigger` | POST | Trigger a scene |
| `/scenes` | POST | Create scene |
| `/scenes/{name}` | PUT/DELETE | Update/delete scene |
| `/pis` | GET | Pi metrics |
| `/alerts` | GET | Alert history |
| `/alerts/{id}/ack` | POST | Acknowledge alert |
| `/logs` | GET | System logs |
| `/alexa` | POST | Alexa skill endpoint |

## Project Structure

```
nexus/
├── agent/          # Windows PC Agent (Python service)
├── agent-mac/      # macOS Agent (Python + LaunchAgent)
├── alexa-skill/    # Alexa interaction model
├── config/         # System configuration
├── core/           # FastAPI backend
├── plugins/        # Device plugins (Hue, IKEA, Tasmota, ...)
├── scenes/         # YAML automation scenes
├── web/            # React + Vite dashboard
├── docs/           # GitHub Pages site
├── Dockerfile
└── docker-compose.yaml
```

## License

Private project by [Werizu](https://github.com/Werizu).
