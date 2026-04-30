"""NEXUS Mac Agent — runs on macOS, connects to Brain via MQTT."""

import json
import logging
import os
import platform
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import psutil
import paho.mqtt.client as mqtt
import requests
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "nexus-agent-mac.log"),
    ],
)
logger = logging.getLogger("nexus-agent-mac")

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


def save_config(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)


def _get_mac_address() -> str:
    mac = uuid.getnode()
    return ":".join(f"{(mac >> (8 * i)) & 0xFF:02X}" for i in reversed(range(6)))


def register_with_brain(brain_url: str, username: str, password: str) -> dict:
    """Authenticate with Brain and register this device. Returns device_id and token."""
    login_resp = requests.post(
        f"{brain_url}/api/v1/auth/login",
        json={"username": username, "password": password},
        timeout=10,
    )
    login_resp.raise_for_status()
    token = login_resp.json()["token"]

    reg_resp = requests.post(
        f"{brain_url}/api/v1/agent/register",
        json={
            "hostname": platform.node(),
            "mac_address": _get_mac_address(),
            "os": "macos",
            "name": platform.node(),
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    reg_resp.raise_for_status()
    data = reg_resp.json()
    data["token"] = token
    return data


class NexusMacAgent:
    def __init__(self, config: dict):
        mqtt_conf = config.get("mqtt", {})
        agent_conf = config.get("agent", {})
        alerts_conf = config.get("alerts", {})

        self.broker = mqtt_conf.get("broker", "100.122.236.58")
        self.port = mqtt_conf.get("port", 1883)
        self.client_id = mqtt_conf.get("client_id", f"nexus-agent-{platform.node()}")
        self.device_id = agent_conf.get("device_id", "")
        self.device_name = agent_conf.get("name", platform.node())
        self.report_interval = agent_conf.get("report_interval", 10)

        self._alert_thresholds = {
            "cpu": alerts_conf.get("cpu", 90),
            "ram": alerts_conf.get("ram", 90),
            "disk": alerts_conf.get("disk", 90),
        }
        self._alert_cooldowns: dict[str, float] = {}
        self._alert_cooldown_secs = alerts_conf.get("cooldown", 300)
        self._net_prev: dict | None = None
        self._net_prev_time: float = 0

        self._running = False
        self._client: mqtt.Client | None = None
        self._topic_base = f"nexus/agent/{self.device_id}"
        self._cmd_topic = f"{self._topic_base}/cmd"
        self._state_topic = f"{self._topic_base}/state"
        self._response_topic = f"{self._topic_base}/response"
        self._alert_topic = f"{self._topic_base}/alert"

    # ─── Lifecycle ───────────────────────────────────────

    def start(self):
        logger.info(f"NEXUS Mac Agent starting (device: {self.device_id}, broker: {self.broker}:{self.port})")
        self._running = True

        self._client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        self._client.will_set(
            self._state_topic,
            json.dumps({"online": False, "device_id": self.device_id}),
            retain=True,
        )

        self._connect()

        report_thread = threading.Thread(target=self._report_loop, daemon=True)
        report_thread.start()

        self._client.loop_forever()

    def stop(self):
        logger.info("NEXUS Mac Agent stopping...")
        self._running = False
        if self._client:
            self._publish_state(online=False)
            self._client.disconnect()

    def _connect(self):
        while self._running:
            try:
                self._client.connect(self.broker, self.port, keepalive=30)
                return
            except Exception as e:
                logger.warning(f"Connection failed: {e}, retrying in 5s...")
                time.sleep(5)

    # ─── MQTT Callbacks ─────────────────────────────────

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        logger.info(f"Connected to MQTT broker ({reason_code})")
        client.subscribe(self._cmd_topic)
        self._publish_state(online=True)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        if self._running:
            logger.warning(f"Disconnected ({reason_code}), will reconnect...")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {"raw": msg.payload.decode()}

        command = payload.get("command", "")
        params = payload.get("params", {})
        request_id = payload.get("request_id", "")

        logger.info(f"Command received: {command} (params: {params})")

        try:
            result = self._handle_command(command, params)
            response = {"status": "ok", "command": command, "result": result}
        except Exception as e:
            logger.error(f"Command failed: {e}")
            response = {"status": "error", "command": command, "error": str(e)}

        if request_id:
            response["request_id"] = request_id

        self._client.publish(self._response_topic, json.dumps(response))

    # ─── Command Router ─────────────────────────────────

    def _handle_command(self, command: str, params: dict) -> dict | str:
        match command:
            case "status":
                return self._get_system_info()
            case "run":
                return self._run_command(params.get("cmd", ""))
            case "open":
                return self._open(params.get("target", ""))
            case "open_app":
                return self._open_app(params.get("app", ""), params.get("args", []))
            case "open_url":
                return self._open_url(params.get("url", ""))
            case "scene_watch":
                return self._open_scene_watch(params.get("scene", ""))
            case "rdp_connect":
                return self._open_rdp()
            case "ssh_terminal":
                return self._ssh_terminal(params.get("host", ""), params.get("user", "marlon"))
            case "notify":
                return self._show_notification(params.get("title", "NEXUS"), params.get("message", ""))
            case "volume":
                return self._set_volume(params.get("level", 50))
            case "mute":
                return self._toggle_mute()
            case "brightness":
                return self._set_brightness(params.get("level", 50))
            case "sleep":
                return self._system_sleep()
            case "lock":
                return self._lock_screen()
            case "screenshot":
                return self._take_screenshot()
            case "clipboard":
                return self._get_clipboard()
            case "say":
                return self._say(params.get("text", ""))
            case "dark_mode":
                return self._toggle_dark_mode(params.get("enabled", True))
            case "dnd":
                return self._toggle_dnd(params.get("enabled", True))
            case "processes":
                return self._list_processes(params.get("limit", 10))
            case "kill":
                return self._kill_process(params.get("pid", 0), params.get("name", ""))
            case "ping":
                return "pong"
            case _:
                return f"Unknown command: {command}"

    # ─── System Info ─────────────────────────────────────

    def _get_system_info(self) -> dict:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        boot_time = psutil.boot_time()
        uptime = time.time() - boot_time

        info = {
            "online": True,
            "os": "macos",
            "os_version": platform.mac_ver()[0],
            "hostname": platform.node(),
            "cpu": cpu_percent,
            "cpu_cores": psutil.cpu_count(),
            "cpu_freq": round(psutil.cpu_freq().current) if psutil.cpu_freq() else 0,
            "ram": round(mem.percent, 1),
            "ram_total_gb": round(mem.total / (1024**3), 1),
            "ram_used_gb": round(mem.used / (1024**3), 1),
            "disk": round(disk.percent, 1),
            "disk_total_gb": round(disk.total / (1024**3), 1),
            "disk_used_gb": round(disk.used / (1024**3), 1),
            "uptime": round(uptime),
            "battery": self._get_battery(),
            "network": self._get_network_stats(),
        }

        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        info["temp"] = round(entries[0].current, 1)
                        break
        except (AttributeError, Exception):
            pass

        return info

    def _get_battery(self) -> dict | None:
        battery = psutil.sensors_battery()
        if battery:
            return {
                "percent": battery.percent,
                "plugged": battery.power_plugged,
                "secs_left": battery.secsleft if battery.secsleft > 0 else None,
            }
        return None

    def _get_network_stats(self) -> dict:
        counters = psutil.net_io_counters()
        now = time.time()
        result = {
            "bytes_sent": counters.bytes_sent,
            "bytes_recv": counters.bytes_recv,
            "download_speed": 0.0,
            "upload_speed": 0.0,
        }
        if self._net_prev and (now - self._net_prev_time) > 0:
            dt = now - self._net_prev_time
            result["download_speed"] = round((counters.bytes_recv - self._net_prev["bytes_recv"]) / dt / 1024 / 1024, 2)
            result["upload_speed"] = round((counters.bytes_sent - self._net_prev["bytes_sent"]) / dt / 1024 / 1024, 2)
        self._net_prev = {"bytes_sent": counters.bytes_sent, "bytes_recv": counters.bytes_recv}
        self._net_prev_time = now

        try:
            conns = psutil.net_connections(kind="inet")
            result["active_connections"] = len([c for c in conns if c.status == "ESTABLISHED"])
        except (psutil.AccessDenied, Exception):
            result["active_connections"] = 0

        return result

    # ─── macOS Commands ──────────────────────────────────

    def _open(self, target: str) -> str:
        if not target:
            raise ValueError("No target specified")
        subprocess.Popen(["open", target])
        return f"Opened: {target}"

    def _open_app(self, app: str, args: list) -> str:
        if not app:
            raise ValueError("No app specified")
        cmd = ["open", "-a", app]
        if args:
            cmd += ["--args"] + args
        subprocess.Popen(cmd)
        return f"Opened app: {app}"

    def _open_url(self, url: str) -> str:
        if not url:
            raise ValueError("No URL specified")
        subprocess.Popen(["open", url])
        return f"Opened URL: {url}"

    def _open_scene_watch(self, scene: str) -> str:
        if not scene:
            raise ValueError("No scene specified")
        watch_script = Path(__file__).parent / "scene_watch.py"
        if not watch_script.exists():
            raise FileNotFoundError("scene_watch.py not found")
        python = Path(__file__).parent / "venv" / "bin" / "python"
        cmd = f"{python} {watch_script} --watch --auto-close {scene}"
        script = f'''
        tell application "Terminal"
            activate
            set newTab to do script "{cmd}"
            set theWindow to window 1
            repeat
                delay 2
                try
                    if not busy of newTab then exit repeat
                on error
                    exit repeat
                end try
            end repeat
            delay 1
            close theWindow saving no
        end tell
        '''
        subprocess.Popen(["osascript", "-e", script])
        return f"Scene watch opened for: {scene}"

    def _open_rdp(self) -> str:
        subprocess.Popen(["open", "-a", "Windows App"])
        return "Windows App opened"

    def _ssh_terminal(self, host: str, user: str, key: str = "") -> str:
        if not host:
            raise ValueError("No host specified")
        key_path = key or "~/.ssh/pi_manager_rsa"
        ssh_cmd = f"ssh -i {key_path} -o StrictHostKeyChecking=no {user}@{host}"
        script = f'''
        tell application "Terminal"
            activate
            do script "{ssh_cmd}"
        end tell
        '''
        subprocess.Popen(["osascript", "-e", script])
        return f"SSH terminal to {user}@{host}"

    def _show_notification(self, title: str, message: str) -> str:
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], capture_output=True)
        return "Notification shown"

    def _set_volume(self, level: int) -> str:
        subprocess.run(["osascript", "-e", f"set volume output volume {level}"], capture_output=True)
        return f"Volume set to {level}%"

    def _toggle_mute(self) -> str:
        subprocess.run(["osascript", "-e", "set volume output muted (not (output muted of (get volume settings)))"], capture_output=True)
        return "Mute toggled"

    def _set_brightness(self, level: int) -> str:
        brightness = level / 100.0
        subprocess.run(["brightness", str(brightness)], capture_output=True)
        return f"Brightness set to {level}%"

    def _system_sleep(self) -> str:
        subprocess.Popen(["pmset", "sleepnow"])
        return "Entering sleep mode"

    def _lock_screen(self) -> str:
        subprocess.Popen([
            "osascript", "-e",
            'tell application "System Events" to keystroke "q" using {command down, control down}'
        ])
        return "Screen locked"

    def _take_screenshot(self) -> str:
        path = Path(__file__).parent / "screenshot.png"
        subprocess.run(["screencapture", "-x", str(path)], capture_output=True)
        return f"Screenshot saved to {path}"

    def _get_clipboard(self) -> str:
        result = subprocess.run(["pbpaste"], capture_output=True, text=True)
        return result.stdout[:4096]

    def _say(self, text: str) -> str:
        if not text:
            raise ValueError("No text specified")
        subprocess.Popen(["say", text])
        return f"Speaking: {text}"

    def _toggle_dark_mode(self, enabled: bool) -> str:
        mode = "true" if enabled else "false"
        script = f'''
        tell application "System Events"
            tell appearance preferences
                set dark mode to {mode}
            end tell
        end tell
        '''
        subprocess.run(["osascript", "-e", script], capture_output=True)
        return f"Dark mode {'enabled' if enabled else 'disabled'}"

    def _toggle_dnd(self, enabled: bool) -> str:
        if enabled:
            subprocess.run(["shortcuts", "run", "Turn On Focus"], capture_output=True)
        else:
            subprocess.run(["shortcuts", "run", "Turn Off Focus"], capture_output=True)
        return f"DND {'enabled' if enabled else 'disabled'}"

    def _run_command(self, cmd: str) -> dict:
        if not cmd:
            raise ValueError("No command specified")
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30
            )
            return {
                "stdout": result.stdout[:4096],
                "stderr": result.stderr[:1024],
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out after 30s"}

    def _list_processes(self, limit: int) -> list:
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        procs.sort(key=lambda x: x.get("cpu_percent", 0) or 0, reverse=True)
        return procs[:limit]

    def _kill_process(self, pid: int, name: str) -> str:
        if pid:
            p = psutil.Process(pid)
            p.terminate()
            return f"Terminated PID {pid} ({p.name()})"
        if name:
            killed = 0
            for p in psutil.process_iter(["name"]):
                if p.info["name"] and name.lower() in p.info["name"].lower():
                    p.terminate()
                    killed += 1
            return f"Terminated {killed} processes matching '{name}'"
        raise ValueError("Specify pid or name")

    # ─── Alerts ──────────────────────────────────────────

    def _check_alerts(self, state: dict):
        now = time.time()
        alerts = []

        checks = [
            ("cpu", state.get("cpu", 0), self._alert_thresholds["cpu"], "CPU bei {val}%"),
            ("ram", state.get("ram", 0), self._alert_thresholds["ram"], "RAM bei {val}%"),
            ("disk", state.get("disk", 0), self._alert_thresholds["disk"], "Disk bei {val}%"),
        ]

        for key, val, threshold, msg_tpl in checks:
            if val >= threshold:
                last = self._alert_cooldowns.get(key, 0)
                if now - last >= self._alert_cooldown_secs:
                    self._alert_cooldowns[key] = now
                    alerts.append({
                        "type": key,
                        "value": val,
                        "threshold": threshold,
                        "message": msg_tpl.format(val=val),
                        "severity": "critical" if val >= threshold + 5 else "warning",
                        "timestamp": now,
                    })

        for alert in alerts:
            logger.warning(f"ALERT: {alert['message']}")
            if self._client and self._client.is_connected():
                self._client.publish(self._alert_topic, json.dumps(alert))

    # ─── State Publishing ────────────────────────────────

    def _publish_state(self, online: bool = True):
        if not self._client or not self._client.is_connected():
            return
        if online:
            state = self._get_system_info()
        else:
            state = {"online": False, "device_id": self.device_id}
        self._client.publish(self._state_topic, json.dumps(state), retain=True)

    def _report_loop(self):
        while self._running:
            time.sleep(self.report_interval)
            if self._running and self._client and self._client.is_connected():
                try:
                    state = self._get_system_info()
                    self._client.publish(self._state_topic, json.dumps(state), retain=True)
                    self._check_alerts(state)
                except Exception as e:
                    logger.debug(f"Report failed: {e}")


def main():
    config = load_config()

    if not config.get("agent", {}).get("device_id"):
        brain_ip = config.get("mqtt", {}).get("broker", "")
        auth = config.get("auth", {})
        username = auth.get("username", "")
        password = auth.get("password", "")

        if not brain_ip or not username or not password:
            logger.error("Missing config: mqtt.broker, auth.username, auth.password required for first start")
            sys.exit(1)

        brain_url = f"http://{brain_ip}:8000"
        logger.info(f"Registering with Brain at {brain_url} as '{username}'...")

        try:
            result = register_with_brain(brain_url, username, password)
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            sys.exit(1)

        device_id = result["device_id"]
        config.setdefault("agent", {})["device_id"] = device_id
        config["agent"]["name"] = platform.node()
        config.setdefault("mqtt", {})["client_id"] = f"nexus-agent-{device_id}"
        config["auth"]["token"] = result["token"]
        save_config(config)
        logger.info(f"Registered as '{device_id}' — config saved")

    agent = NexusMacAgent(config)

    def handle_signal(sig, frame):
        agent.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    agent.start()


if __name__ == "__main__":
    main()
