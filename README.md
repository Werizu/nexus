# NEXUS

Self-hosted Smart Home System — runs on a Raspberry Pi, controls lights, plugs, PCs, and more from a single dashboard. Multi-user support, remote access via Tailscale, voice control with Alexa.

## Architecture

```
                          ┌─────────────────────────────────┐
                          │      Tailscale Mesh VPN         │
                          │  (secure access from anywhere)  │
                          └──────────┬──────────────────────┘
                                     │
┌──────────────┐     MQTT      ┌─────┴─────────┐     HTTP      ┌─────────────┐
│  NEXUS Agent │◄─────────────►│  NEXUS Brain  │◄─────────────►│  Dashboard  │
│  (Win / Mac) │               │  (FastAPI)    │               │  (React PWA)│
└──────────────┘               └──────┬────────┘               └─────────────┘
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

Reihenfolge ist wichtig — jeder Schritt baut auf dem vorherigen auf. Bereits erledigte Schritte überspringen.

### 1. Brain (Raspberry Pi)

Der Brain ist das Herzstück — er muss zuerst laufen.

```bash
# Repo klonen
git clone https://github.com/Werizu/nexus.git
cd nexus

# Config anpassen
cp config/secrets.yaml.example config/secrets.yaml
nano config/devices.yaml    # Geräte eintragen (Lichter, Plugs, PCs, Pis)
nano config/secrets.yaml    # API-Keys (Hue Bridge Key, etc.)
nano config/nexus.yaml      # MQTT Broker IP, System-Einstellungen

# Bauen und starten
sudo docker compose up -d
```

Es starten drei Container:
- `nexus-brain` — FastAPI Backend auf Port 8000
- `nexus-mqtt` — Mosquitto Broker auf Port 1883
- `nexus-web` — Nginx Dashboard auf Port 80

### 2. Tailscale (Fernzugriff)

Tailscale wird **vor** den Agents installiert, weil die Agents die Tailscale-IP des Brain brauchen.

```bash
# Auf dem Brain-Pi
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Tailscale IP notieren — wird für alles Weitere gebraucht
tailscale ip -4
```

`config/nexus.yaml` und `config/devices.yaml` auf Tailscale-IPs umstellen. Danach Brain neustarten:

```bash
sudo docker compose restart nexus-brain
```

Tailscale auch auf allen anderen Geräten installieren (PCs, MacBooks, Handys), die auf das Dashboard zugreifen sollen.

> **Ohne Tailscale** funktioniert alles nur im lokalen Netzwerk — Agents können dann die lokale IP des Brain nutzen.

### 3. Dashboard & Account-Einrichtung

Dashboard im Browser öffnen: `http://<tailscale-ip>` (oder `http://<lokale-ip>` ohne Tailscale).

Beim ersten Start wird ein Admin-Account erstellt:

- **Username:** `admin`
- **Password:** `nexus`

**Passwort sofort ändern** über das Zahnrad-Icon oben rechts.

> **Wichtig:** Accounts müssen existieren **bevor** Agents installiert werden, weil der Agent bei der Installation nach NEXUS-Login-Daten fragt und sich damit beim Brain registriert.

**Neuen User anlegen** (z.B. für einen Freund):

1. Zahnrad-Icon oben rechts → **Benutzerverwaltung**
2. **+ Neuer Benutzer**: Username, Anzeigename, Passwort, Rolle (`user` oder `admin`)
3. Login-Daten dem Freund mitteilen — er braucht sie bei der Agent-Installation

### 4. Windows PC einrichten

Reihenfolge auf dem PC: Tailscale → WOL → Agent.

**4a) Tailscale installieren:**

1. [tailscale.com/download](https://tailscale.com/download) → Windows Installer
2. Installieren und anmelden
3. **Run unattended** aktivieren (Tailscale-Einstellungen) — damit Tailscale nach Neustart automatisch verbindet
4. Tailscale-IP notieren: Rechtsklick auf Tailscale-Icon → *My IP address*

**4b) Wake-on-LAN einrichten:**

Damit der PC über das Dashboard aus dem ausgeschalteten Zustand geweckt werden kann.

**BIOS/UEFI:**
1. PC neustarten → ins BIOS (`DEL`, `F2` oder `F12`)
2. **Wake on LAN** / **Wake on PCI(E)**: **Enabled**
3. **ErP Ready** / **Deep Sleep**: **Disabled**
4. Speichern und neustarten

**Windows Netzwerkadapter:**
1. **Geräte-Manager** (`devmgmt.msc`) → **Netzwerkadapter** → Rechtsklick Ethernet-Adapter → **Eigenschaften**
2. Tab **Erweitert**:
   - *Wake on Magic Packet*: **Enabled**
   - *Wake on Pattern Match*: **Enabled**
   - *Energy Efficient Ethernet*: **Disabled** (falls vorhanden)
3. Tab **Energieverwaltung**:
   - ☑ *Gerät kann den Computer aus dem Ruhezustand aktivieren*
   - ☑ *Nur Magic Packet kann den Computer aus dem Ruhezustand aktivieren*

**Windows Energieoptionen:**
- **Einstellungen → System → Netzbetrieb → Schnellstart**: **Aus** (blockiert WOL bei Herunterfahren)

> **Wichtig:** WOL funktioniert nur über **Ethernet** (Kabel), nicht über WLAN.

**4c) Remotedesktop aktivieren:**

**Einstellungen → System → Remotedesktop → An**

**4d) NEXUS Agent installieren:**

> **Voraussetzung:** Ein NEXUS-Account muss bereits existieren (siehe [Schritt 3](#3-dashboard--account-einrichtung)).

In einer **erhöhten PowerShell** (Rechtsklick → Als Administrator):

```powershell
irm https://werizu.github.io/nexus/install.ps1 | iex
```

Das Script fragt nach:
1. **Brain IP** — Tailscale-IP des Brain Pi (aus Schritt 2)
2. **NEXUS Username** — dein NEXUS-Benutzername
3. **NEXUS Passwort** — dein NEXUS-Passwort

Der Agent meldet sich beim Brain an, **registriert den PC automatisch als Gerät** (mit richtigem Owner), und startet als Windows-Service. Das Gerät erscheint sofort im Dashboard.

> Kein manuelles Bearbeiten von `devices.yaml` nötig — die Registrierung läuft komplett automatisch.

**4e) Neustart und prüfen:**

PC neustarten. Prüfen:
- Tailscale verbindet automatisch (Icon grün)
- Agent läuft: `Get-Service NexusAgent`
- Dashboard zeigt den PC als online

**Agent-Funktionen:** System-Metriken (CPU, RAM, GPU, Disk, Netzwerk), Remote Shutdown/Restart/Sleep/Lock, Prozessverwaltung, Alerts bei Schwellwerten.

### 5. macOS Agent (optional)

Nur nötig wenn das MacBook auch über NEXUS gesteuert werden soll (Apps öffnen, RDP, etc.).

> **Voraussetzung:** Tailscale installiert + NEXUS-Account existiert (siehe [Schritt 3](#3-dashboard--account-einrichtung)).

**Zuerst Tailscale installieren** ([tailscale.com/download](https://tailscale.com/download) → macOS), dann:

```bash
curl -fsSL https://werizu.github.io/nexus/install-mac.sh | bash
```

Das Script fragt nach:
1. **Brain IP** — Tailscale-IP des Brain Pi
2. **NEXUS Username** — dein NEXUS-Benutzername
3. **NEXUS Passwort** — dein NEXUS-Passwort

Der Agent registriert sich automatisch beim Brain, das Gerät erscheint im Dashboard. Installiert sich als LaunchAgent und startet automatisch beim Login.

**Agent-Funktionen:** Apps/URLs öffnen, RDP-Verbindungen (Windows App), SSH-Terminals, Lautstärke, Helligkeit, Dark Mode, Screenshots, System-Metriken.

### 6. Zweiten Benutzer einrichten (Komplett-Anleitung)

Komplette Anleitung um einen Freund einzurichten — von Null. Er hat ein MacBook ohne alles, einen Desktop-PC ohne alles, und bekommt einen Raspberry Pi als WOL-Relay. Ziel: Er kann seinen PC von überall (Uni, unterwegs) über das NEXUS-Dashboard aufwecken und per RDP steuern.

> **Voraussetzung:** NEXUS Brain läuft bereits auf deinem Pi mit Tailscale. Falls nicht, zuerst [Schritt 1: Brain](#1-brain-raspberry-pi) und [Schritt 5: Tailscale](#5-tailscale-remote-access) abschließen.

#### Übersicht

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

| Gerät | Standort | Rolle | Muss 24/7 laufen? |
|---|---|---|---|
| NEXUS Brain (dein Pi) | Bei dir | Backend, Dashboard | Ja |
| Relay-Pi (z.B. Pi Zero W) | Beim Freund | WOL-Relay | Ja (~0.5W) |
| Freund PC | Beim Freund | Wird ferngesteuert | Nein (wird per WOL geweckt) |
| Freund MacBook | Mobil | Dashboard + RDP Client | Nein |

---

#### Vorbereitung (von zuhause aus)

Bevor du zum Freund fährst — diese Schritte kannst du vorher erledigen:

**Tailscale-Einladung senden:**

1. Öffne [Tailscale Admin Console](https://login.tailscale.com/admin/users)
2. **Users → Invite users**
3. E-Mail deines Freundes eingeben, Einladung senden
4. Dein Freund soll die Einladung **annehmen und einen Tailscale-Account erstellen** (er muss noch nichts installieren)

> **Tailscale Free** erlaubt bis zu 3 Benutzer und 100 Geräte.

**NEXUS-Account anlegen:**

> **Dieser Schritt muss vor der Agent-Installation passieren** — der Agent braucht Login-Daten bei der Einrichtung.

1. Dashboard öffnen: `http://<tailscale-ip-des-brain>`
2. Als Admin einloggen
3. **Zahnrad-Icon** (oben rechts) → **Benutzerverwaltung**
4. **+ Neuer Benutzer**: Benutzername, Anzeigename, temporäres Passwort, Rolle `user`
5. Login-Daten aufschreiben — dein Freund braucht sie bei der Agent-Installation

**Relay-Pi vorbereiten:**

1. [Raspberry Pi Imager](https://www.raspberrypi.com/software/) herunterladen
2. **Raspberry Pi OS Lite (64-bit)** auswählen (kein Desktop nötig)
3. Vor dem Schreiben auf das Zahnrad klicken:
   - **SSH aktivieren** (Passwort-Authentifizierung)
   - **Benutzername + Passwort** setzen (z.B. `marlon` / eigenes Passwort)
   - **WLAN konfigurieren** (WLAN des Freundes, damit man beim ersten Boot per SSH draufkommt)
4. SD-Karte flashen — mitnehmen

---

#### Beim Freund: Schritt 1 — Relay-Pi aufsetzen

Der Pi wird als Erstes eingerichtet, weil er am längsten braucht (Updates, Tailscale).

> **Wichtig:** Der Relay-Pi **muss per LAN-Kabel** am selben Router/Switch wie der PC angeschlossen sein. WOL funktioniert nicht über WLAN.

1. SD-Karte einlegen, **LAN-Kabel an den Router**, Strom anschließen
2. Warten bis hochgefahren (~1-2 Minuten)
3. IP herausfinden (im Router unter "Verbundene Geräte" oder per `ping raspberrypi.local`)
4. Per SSH verbinden und Setup-Script ausführen:

```bash
ssh marlon@<lokale-ip-des-pi>
curl -fsSL https://werizu.github.io/nexus/setup-relay.sh | bash
```

Das Script installiert `wakeonlan` + Tailscale und zeigt einen Login-Link. Diesen im Browser öffnen und mit **deinem** Tailscale-Account anmelden (der Pi gehört zu deinem Netzwerk).

**Tailscale-IP des Relay-Pi notieren** — wird in Schritt 4 gebraucht.

> Während der Pi Updates installiert, kannst du parallel mit Schritt 2 (PC) weitermachen.

---

#### Beim Freund: Schritt 2 — Desktop-PC einrichten

**2a) Wake-on-LAN im BIOS aktivieren:**

1. PC neustarten → ins BIOS (`DEL`, `F2` oder `F12`)
2. **Wake on LAN** / **Wake on PCI(E)**: **Enabled**
3. **ErP Ready** / **Deep Sleep**: **Disabled**
4. Speichern und neustarten

**2b) Wake-on-LAN in Windows aktivieren:**

1. **Geräte-Manager** (`devmgmt.msc`) → **Netzwerkadapter** → Rechtsklick Ethernet-Adapter → **Eigenschaften**
2. Tab **Erweitert**:
   - *Wake on Magic Packet*: **Enabled**
   - *Wake on Pattern Match*: **Enabled**
   - *Energy Efficient Ethernet*: **Disabled** (falls vorhanden)
3. Tab **Energieverwaltung**:
   - ☑ *Gerät kann den Computer aus dem Ruhezustand aktivieren*
   - ☑ *Nur Magic Packet kann den Computer aus dem Ruhezustand aktivieren*
4. **Einstellungen → System → Netzbetrieb → Schnellstart**: **Aus**

**2c) MAC-Adresse notieren:**

```powershell
getmac /v
```

MAC-Adresse des **Ethernet-Adapters** aufschreiben (Format `AA-BB-CC-DD-EE-FF`).

> WOL funktioniert nur über **Ethernet** (Kabel), nicht über WLAN.

**2d) Tailscale installieren:**

1. [tailscale.com/download](https://tailscale.com/download) → Windows Installer herunterladen und installieren
2. Mit dem **Account deines Freundes** anmelden (er hat die Einladung in der Vorbereitung angenommen)
3. Tailscale-Einstellungen: **Run unattended** aktivieren
4. **Tailscale-IP notieren**: Rechtsklick auf Tailscale-Icon → *My IP address*

**2e) Remotedesktop aktivieren:**

**Einstellungen → System → Remotedesktop → An**

**2f) NEXUS Agent installieren:**

Jetzt ist Tailscale aktiv und du kennst die Brain-IP. In einer **erhöhten PowerShell** (Rechtsklick → Als Administrator):

```powershell
irm https://werizu.github.io/nexus/install.ps1 | iex
```

Das Script fragt nach:
1. **Brain IP** — Tailscale-IP des Brain Pi
2. **NEXUS Username** — der Account, den du in der Vorbereitung angelegt hast
3. **NEXUS Passwort** — das temporäre Passwort

Der Agent registriert sich automatisch beim Brain. Das Gerät erscheint im Dashboard und gehört dem eingeloggten User — nur er sieht es, Admins sehen alles.

**2g) Neustart und prüfen:**

PC einmal neu starten. Prüfen ob:
- Tailscale automatisch verbindet (Icon grün)
- NEXUS Agent läuft: `Get-Service NexusAgent`
- PC erscheint im Dashboard des Freundes

---

#### Beim Freund: Schritt 3 — MacBook einrichten

**3a) Tailscale installieren:**

1. [tailscale.com/download](https://tailscale.com/download) → macOS herunterladen und installieren
2. Mit dem **Account deines Freundes** anmelden

**3b) Windows App installieren (für RDP):**

1. App Store → **Windows App** (von Microsoft) installieren
2. Neue Verbindung hinzufügen:
   - IP: **Tailscale-IP des PCs** (aus Schritt 2d)
   - Benutzer: Windows-Login des PCs
3. Verbindung speichern

**3c) NEXUS Mac Agent installieren (optional):**

Falls das MacBook auch über NEXUS gesteuert werden soll:

```bash
curl -fsSL https://werizu.github.io/nexus/install-mac.sh | bash
```

Fragt nach Brain-IP + NEXUS-Login. Agent registriert sich automatisch.

> Ohne Agent braucht das MacBook nur Tailscale, Windows App und den Browser.

**3d) Dashboard testen:**

1. Browser öffnen: `http://<tailscale-ip-des-brain>`
2. Mit dem NEXUS-Account einloggen (aus der Vorbereitung)
3. Dashboard sollte laden und die Geräte des Freundes anzeigen (nicht deine — jeder User sieht nur seine eigenen)

---

#### Zuhause: Schritt 4 — Relay-Pi in NEXUS registrieren

Der PC des Freundes hat sich in Schritt 2f **automatisch registriert** (über den Agent). Nur der Relay-Pi muss manuell eingetragen werden.

**4a) SSH-Key zum Relay-Pi kopieren:**

```bash
ssh-copy-id -i ~/.ssh/pi_manager_rsa marlon@<relay-tailscale-ip>
```

Testen:
```bash
ssh -i ~/.ssh/pi_manager_rsa marlon@<relay-tailscale-ip> "echo OK"
```

**4b) Relay-Pi registrieren:**

In `config/devices.yaml`:

```yaml
pis:
  - id: relay_friend
    name: "WOL Relay (Freund)"
    plugin: pi_manager
    hostname: 100.x.x.x          # Tailscale IP des Relay-Pi
    ssh_user: marlon
    ssh_key: "~/.pi-manager/keys/id_rsa"
    role: relay
```

Brain neustarten: `sudo docker compose restart nexus-brain`

**4c) WOL-Relay dem PC zuweisen:**

Den automatisch registrierten PC des Freundes mit dem Relay verknüpfen — im Dashboard unter **Geräte** den PC bearbeiten und `wol_relay: relay_friend` hinzufügen. Oder in `config/devices.yaml` den Eintrag ergänzen:

```yaml
computers:
  - id: <username>_<hostname>     # wurde automatisch vergeben
    wol_relay: relay_friend       # WOL über den Relay-Pi senden
    mac_address: "AA:BB:CC:DD:EE:FF"  # MAC-Adresse aus Schritt 2c
```

Das `wol_relay` Feld sagt dem Brain: "Sende WOL nicht lokal, sondern per SSH über den Relay-Pi."

---

#### Schritt 5 — Komplett-Test

Jetzt alles zusammen testen:

1. **PC des Freundes herunterfahren** (oder er fährt ihn selbst runter)
2. **Am MacBook des Freundes** (oder deinem Rechner):
   - `http://<tailscale-ip-des-brain>` öffnen
   - Einloggen → "Freund PC" → **Wake** klicken
3. **Was passiert:**
   - Brain erkennt `wol_relay: relay_friend`
   - Brain verbindet sich per SSH zum Relay-Pi
   - Relay-Pi sendet WOL-Broadcast ins lokale Netz
   - PC wacht auf → Tailscale startet → Agent meldet sich
   - Dashboard zeigt PC als "online"
4. **RDP verbinden:** Windows App öffnen → gespeicherte Verbindung klicken

#### Fehlerbehebung

| Problem | Ursache | Lösung |
|---|---|---|
| PC wacht nicht auf | WOL nicht im BIOS aktiviert | Schritt 2a prüfen |
| PC wacht nicht auf | Relay-Pi nicht per LAN-Kabel | Relay-Pi per Ethernet anschließen |
| PC wacht nicht auf | Schnellstart aktiv | Schritt 2b: Schnellstart deaktivieren |
| Dashboard nicht erreichbar | Tailscale nicht verbunden | Tailscale-App öffnen, Status prüfen |
| "WOL relay device not found" | Relay-Pi nicht registriert | Schritt 4b prüfen, Brain neustarten |
| Agent meldet sich nicht | Agent-Service nicht gestartet | `Get-Service NexusAgent` prüfen |
| RDP verbindet nicht | Remotedesktop nicht aktiviert | Schritt 2e prüfen |

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

Die Config wird bei der Installation automatisch erstellt. Beim ersten Start registriert sich der Agent beim Brain und ergänzt `device_id` und `token` selbst.

```yaml
mqtt:
  broker: "100.122.236.58"       # Brain Tailscale-IP (bei Installation angegeben)
  port: 1883
  client_id: "nexus-agent-marlon_desktop"  # wird automatisch gesetzt

auth:
  username: "marlon"             # NEXUS-Login (bei Installation angegeben)
  password: "..."                # NEXUS-Passwort
  token: "eyJ..."               # JWT-Token (wird automatisch gesetzt)

agent:
  device_id: "marlon_desktop"    # wird automatisch vom Brain vergeben
  name: "Desktop"                # Hostname des PCs
  report_interval: 10

alerts:
  cpu: 90        # CPU usage %
  ram: 90        # RAM usage %
  disk: 90       # Disk usage %
  gpu_temp: 85   # GPU temperature °C
  gpu_load: 95   # GPU load %
  cooldown: 300  # Seconds between repeated alerts
```

> **device_id** wird automatisch aus `username_hostname` generiert (z.B. `marlon_desktop`, `freund_gaming_pc`). So ist garantiert eindeutig welches Gerät welchem User gehört.

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

**PCs und Macs** werden automatisch registriert wenn der NEXUS Agent installiert wird. Der Agent fragt nach NEXUS-Login-Daten und registriert das Gerät beim Brain mit dem richtigen Owner. Kein manuelles Konfigurieren nötig.

**Andere Geräte** (Lichter, Plugs, Pis, Kameras) manuell hinzufügen:

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

NEXUS supports multiple users with role-based access and device ownership:

| Role | Permissions |
|---|---|
| **admin** | Full access — sieht alle Geräte, verwaltet User, Scenes, Rooms |
| **user** | Sieht nur eigene Geräte + geteilte Geräte (owner = NULL) |

### Device Ownership

Jedes Gerät hat einen Owner. Wenn ein Agent sich registriert, wird der eingeloggte User automatisch als Owner gesetzt. Admins sehen alle Geräte, normale User nur ihre eigenen.

- Agent-Installation → User loggt sich ein → Gerät bekommt `owner = username`
- Manuell erstellte Geräte gehören dem User, der sie anlegt
- Geräte ohne Owner (`owner = NULL`) sind für alle sichtbar

### User Management

Admins can manage users via the settings panel (gear icon → Benutzerverwaltung):
- Create new users with username, display name, password, and role
- Promote/demote users between admin and user roles
- Delete users

> **Workflow:** Zuerst Account anlegen → dann Agent installieren. Der Agent braucht die NEXUS-Login-Daten bei der Einrichtung.

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
| `/agent/register` | POST | User | Auto-register a device (used by agents on first start) |

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
