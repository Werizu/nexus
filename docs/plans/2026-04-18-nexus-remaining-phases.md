# NEXUS Remaining Phases Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete all remaining NEXUS features from the architecture plan — Dashboard launch, MQTT setup, Docker deployment, Vite proxy, and dashboard polish.

**Architecture:** The backend (FastAPI) is functional with working plugins (PC Control, Pi Manager). The React dashboard has all components built but has never been launched. MQTT/Mosquitto needs to run on the Pi via Docker. The frontend connects to the backend via Vite proxy in dev and via Docker networking in production.

**Tech Stack:** Python 3.12, FastAPI, SQLite, MQTT (Mosquitto), React 19, Vite 8, Tailwind CSS 4, lucide-react, recharts, Docker Compose

---

## Task 1: Launch Dashboard and verify it works

The React dashboard has components (DeviceCard, SceneCard, PiMonitor, Header, StatusBadge) and hooks (useDevices, useScenes, useHealth, usePis, useWebSocket) already built. It has never been tested. We need to configure Vite proxy for the API and launch it.

**Files:**
- Modify: `web/vite.config.js` — add API proxy to backend
- Modify: `web/index.html` — fix title

**Step 1: Check current Vite config**

Read `web/vite.config.js` for current state.

**Step 2: Add API proxy to Vite config**

The frontend fetches from `/api/v1/...` — Vite needs to proxy these to `http://localhost:8000`:

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
})
```

**Step 3: Fix page title**

In `web/index.html`, change `<title>web</title>` to `<title>NEXUS</title>`.

**Step 4: Start backend**

```bash
cd /Users/marlonheck/Desktop/nexus
source .venv/bin/activate
uvicorn core.main:app --host 0.0.0.0 --port 8000 &
```

**Step 5: Install frontend deps and start**

```bash
cd /Users/marlonheck/Desktop/nexus/web
npm install
npm run dev
```

**Step 6: Verify in browser**

Open `http://localhost:3000` — should show:
- Header with NEXUS logo, device count, plugin count
- Szenen section with 6 scene cards
- Geräte section with 8 device cards
- Pi Status section with 3 Pi cards showing live metrics
- Tab navigation (Dashboard, Geräte, Szenen, Pi Monitor)

**Step 7: Test scene trigger**

Click "Programmier-Modus" scene card → should trigger and show spinner. Check backend logs for scene execution.

**Step 8: Test WOL button**

On the Desktop PC device card, click "Wake" button → should send WOL packet.

**Step 9: Commit**

```bash
git add web/vite.config.js web/index.html
git commit -m "feat: configure Vite proxy and fix dashboard title"
```

---

## Task 2: Add Logs tab to Dashboard

The backend has a `/api/v1/logs` endpoint but the dashboard doesn't show logs. Add a Logs tab with real-time log viewer.

**Files:**
- Create: `web/src/components/LogViewer.jsx`
- Modify: `web/src/hooks/useNexus.js` — add `useLogs` hook
- Modify: `web/src/App.jsx` — add Logs tab

**Step 1: Add useLogs hook**

In `web/src/hooks/useNexus.js`, add:

```javascript
export function useLogs() {
  const [logs, setLogs] = useState([])

  const refresh = useCallback(async () => {
    try {
      setLogs(await api('/logs?limit=50'))
    } catch (e) {
      console.error('Failed to load logs:', e)
    }
  }, [])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 5000)
    return () => clearInterval(interval)
  }, [refresh])

  return { logs, refresh }
}
```

**Step 2: Create LogViewer component**

```jsx
// web/src/components/LogViewer.jsx
import { AlertCircle, Info, AlertTriangle, Bug } from 'lucide-react'

const LEVEL_CONFIG = {
  error:   { icon: AlertCircle,   color: 'text-red-400',    bg: 'bg-red-500/10' },
  warning: { icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-500/10' },
  info:    { icon: Info,          color: 'text-blue-400',   bg: 'bg-blue-500/10' },
  debug:   { icon: Bug,           color: 'text-gray-400',   bg: 'bg-gray-500/10' },
}

function formatTime(ts) {
  return new Date(ts * 1000).toLocaleTimeString('de-DE', {
    hour: '2-digit', minute: '2-digit', second: '2-digit'
  })
}

export default function LogViewer({ logs }) {
  return (
    <div className="space-y-1">
      {logs.length === 0 && (
        <p className="text-gray-500 text-sm">Keine Logs vorhanden</p>
      )}
      {logs.map((log) => {
        const cfg = LEVEL_CONFIG[log.level] || LEVEL_CONFIG.info
        const Icon = cfg.icon
        return (
          <div key={log.id} className={`flex items-start gap-3 p-3 rounded-lg ${cfg.bg}`}>
            <Icon size={14} className={`mt-0.5 ${cfg.color}`} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 font-mono">{formatTime(log.timestamp)}</span>
                {log.device && (
                  <span className="text-xs text-gray-400 font-mono">[{log.device}]</span>
                )}
              </div>
              <p className="text-sm text-white mt-0.5">{log.message}</p>
            </div>
          </div>
        )
      })}
    </div>
  )
}
```

**Step 3: Add Logs tab to App.jsx**

Add import for `LogViewer` and `useLogs`. Add `{ id: 'logs', label: 'Logs' }` to tabs array. Add the logs tab render block after the Pi Monitor tab.

**Step 4: Verify in browser**

Navigate to Logs tab — should show log entries from scene triggers and device commands.

**Step 5: Commit**

```bash
git add web/src/components/LogViewer.jsx web/src/hooks/useNexus.js web/src/App.jsx
git commit -m "feat: add Logs tab to dashboard"
```

---

## Task 3: Install and start Mosquitto on Pi via Docker

MQTT is needed for Tasmota devices and real-time device communication. Install Docker on the Pi if not present, copy the mosquitto config, and start Mosquitto.

**Step 1: Check if Docker is installed on Pi**

```bash
ssh -i ~/.ssh/pi_manager_rsa marlon@192.168.178.202 "docker --version 2>/dev/null || echo NOT_INSTALLED"
```

**Step 2: Install Docker if needed**

If not installed:
```bash
ssh -i ~/.ssh/pi_manager_rsa marlon@192.168.178.202 "curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker marlon"
```

**Step 3: Create mosquitto directory and config on Pi**

```bash
ssh -i ~/.ssh/pi_manager_rsa marlon@192.168.178.202 "mkdir -p ~/nexus/config"
scp -i ~/.ssh/pi_manager_rsa /Users/marlonheck/Desktop/nexus/config/mosquitto.conf marlon@192.168.178.202:~/nexus/config/
```

**Step 4: Start Mosquitto container on Pi**

```bash
ssh -i ~/.ssh/pi_manager_rsa marlon@192.168.178.202 "
docker run -d --name nexus-mqtt --restart unless-stopped \
  -p 1883:1883 -p 9001:9001 \
  -v ~/nexus/config/mosquitto.conf:/mosquitto/config/mosquitto.conf \
  eclipse-mosquitto:2
"
```

**Step 5: Verify MQTT broker is running**

```bash
ssh -i ~/.ssh/pi_manager_rsa marlon@192.168.178.202 "docker ps | grep mosquitto"
```

**Step 6: Update nexus.yaml to point to Pi broker**

Change `broker: "localhost"` to `broker: "192.168.178.202"` in `config/nexus.yaml` for local development.

**Step 7: Restart NEXUS and verify MQTT connects**

Restart the backend and check logs — should show "Connected to MQTT broker" instead of "Connection refused".

**Step 8: Commit**

```bash
git add config/nexus.yaml
git commit -m "feat: configure MQTT broker on Pi"
```

---

## Task 4: Deploy NEXUS backend on Pi via Docker

Move the backend from local Mac to the Pi where it belongs as the central hub.

**Step 1: Copy the NEXUS project to the Pi**

```bash
rsync -avz --exclude '.venv' --exclude 'web/node_modules' --exclude '.git' --exclude 'data' \
  -e "ssh -i ~/.ssh/pi_manager_rsa" \
  /Users/marlonheck/Desktop/nexus/ marlon@192.168.178.202:~/nexus/
```

**Step 2: Copy SSH key to Pi for plugin SSH access**

The Pi Manager and PC Control plugins need SSH access from inside the container:
```bash
scp -i ~/.ssh/pi_manager_rsa ~/.ssh/pi_manager_rsa marlon@192.168.178.202:~/nexus/pi_manager_rsa
```

**Step 3: Update Dockerfile to include SSH key**

Add to Dockerfile before CMD:
```dockerfile
COPY pi_manager_rsa /root/.ssh/pi_manager_rsa
RUN chmod 600 /root/.ssh/pi_manager_rsa
```

And update `devices.yaml` SSH key paths for containerized deployment:
```yaml
ssh_key: "/root/.ssh/pi_manager_rsa"
```

Note: For production, use Docker secrets or bind-mount the key instead.

**Step 4: Update docker-compose.yaml for Pi deployment**

Update the nexus-brain service to also mount the SSH key and set the MQTT broker to the container name:
```yaml
nexus-brain:
  build: .
  container_name: nexus-brain
  restart: unless-stopped
  ports:
    - "8000:8000"
  volumes:
    - ./config:/app/config
    - ./scenes:/app/scenes
    - ./data:/app/data
    - ./pi_manager_rsa:/root/.ssh/pi_manager_rsa:ro
  depends_on:
    - mosquitto
  environment:
    - NEXUS_ENV=production
  networks:
    - nexus
```

**Step 5: Build and start on Pi**

```bash
ssh -i ~/.ssh/pi_manager_rsa marlon@192.168.178.202 "cd ~/nexus && docker compose up -d --build"
```

**Step 6: Verify deployment**

```bash
curl http://192.168.178.202:8000/api/v1/health
```

Should return `{"status": "ok", "mqtt_connected": true, ...}`

**Step 7: Update Vite proxy for Pi-hosted backend**

For local dashboard development against the Pi-hosted backend, update `web/vite.config.js` proxy target to `http://192.168.178.202:8000`.

**Step 8: Commit**

```bash
git add Dockerfile docker-compose.yaml config/nexus.yaml
git commit -m "feat: Docker deployment configuration for Pi"
```

---

## Task 5: Add Rooms tab to Dashboard

The backend has a `/api/v1/rooms` endpoint. Add a Rooms view that groups devices by room.

**Files:**
- Create: `web/src/components/RoomView.jsx`
- Modify: `web/src/hooks/useNexus.js` — add `useRooms` hook
- Modify: `web/src/App.jsx` — add Rooms tab

**Step 1: Add useRooms hook**

```javascript
export function useRooms() {
  const [rooms, setRooms] = useState({})

  useEffect(() => {
    api('/rooms').then(setRooms).catch(console.error)
  }, [])

  return { rooms }
}
```

**Step 2: Create RoomView component**

Show each room as a card with its devices listed inside. Use the room icons from `rooms.yaml` (monitor, sofa, bed).

**Step 3: Add tab and render**

Add `{ id: 'rooms', label: 'Räume' }` to tabs. Render the rooms grid.

**Step 4: Verify in browser**

Should show Büro (with office devices), Wohnzimmer, Schlafzimmer.

**Step 5: Commit**

```bash
git add web/src/components/RoomView.jsx web/src/hooks/useNexus.js web/src/App.jsx
git commit -m "feat: add Rooms tab to dashboard"
```

---

## Task 6: Hardware-dependent plugin testing (conditional)

These tasks depend on whether the user has the hardware available.

### 6a: Tasmota Plugin — if Tasmota smart plugs exist in the network

**Check:** Ask user if they have Tasmota devices. If yes:
- Add device to `devices.yaml` with IP
- Test `GET http://<tasmota-ip>/cm?cmnd=Status` to verify Tasmota HTTP API
- Test on/off via NEXUS API
- Verify energy monitoring if supported

### 6b: Hue Plugin — if Philips Hue Bridge exists

**Check:** Ask user. If yes:
- Get Hue Bridge IP and create API key
- Add to `secrets.yaml`
- Test light control

### 6c: IKEA TRADFRI Plugin — if IKEA gateway exists

**Check:** Ask user. If yes:
- Get gateway IP and security code
- Test via CoAP

---

## Task 7: Polish and production-readiness

**Files:**
- Modify: `web/index.html` — proper meta tags
- Create: `web/public/manifest.json` — PWA support for mobile
- Modify: `docker-compose.yaml` — add web build service

**Step 1: Add PWA manifest for mobile access**

```json
{
  "name": "NEXUS",
  "short_name": "NEXUS",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0a0a0f",
  "theme_color": "#00D4FF"
}
```

**Step 2: Update index.html**

Add proper title, meta tags, and manifest link.

**Step 3: Add web service to docker-compose**

Build the React app and serve via nginx in production:

```yaml
nexus-web:
  image: nginx:alpine
  container_name: nexus-web
  restart: unless-stopped
  ports:
    - "80:80"
  volumes:
    - ./web/dist:/usr/share/nginx/html:ro
    - ./config/nginx.conf:/etc/nginx/conf.d/default.conf:ro
  depends_on:
    - nexus-brain
  networks:
    - nexus
```

**Step 4: Create nginx config**

Proxy `/api` and `/ws` to nexus-brain, serve static files for everything else.

**Step 5: Commit**

```bash
git add web/public/manifest.json web/index.html docker-compose.yaml config/nginx.conf
git commit -m "feat: PWA support and production nginx setup"
```
