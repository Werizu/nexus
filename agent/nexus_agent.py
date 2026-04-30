"""NEXUS Agent — runs on managed PCs, connects to Brain via MQTT."""

import json
import logging
import os
import platform
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
import paho.mqtt.client as mqtt
import yaml

try:
    import GPUtil
    HAS_GPU = True
except ImportError:
    HAS_GPU = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "nexus-agent.log"),
    ],
)
logger = logging.getLogger("nexus-agent")

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


class NexusAgent:
    def __init__(self, config: dict):
        mqtt_conf = config.get("mqtt", {})
        agent_conf = config.get("agent", {})
        alerts_conf = config.get("alerts", {})

        self.broker = mqtt_conf.get("broker", "100.122.236.58")
        self.port = mqtt_conf.get("port", 1883)
        self.client_id = mqtt_conf.get("client_id", "nexus-agent-pc")
        self.device_id = agent_conf.get("device_id", "main_pc")
        self.device_name = agent_conf.get("name", platform.node())
        self.report_interval = agent_conf.get("report_interval", 10)

        self._alert_thresholds = {
            "cpu": alerts_conf.get("cpu", 90),
            "ram": alerts_conf.get("ram", 90),
            "disk": alerts_conf.get("disk", 90),
            "gpu_temp": alerts_conf.get("gpu_temp", 85),
            "gpu_load": alerts_conf.get("gpu_load", 95),
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

    def start(self):
        logger.info(f"NEXUS Agent starting (device: {self.device_id}, broker: {self.broker}:{self.port})")
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
        logger.info("NEXUS Agent stopping...")
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

    def _handle_command(self, command: str, params: dict) -> dict | str:
        match command:
            case "shutdown":
                threading.Thread(target=self._delayed_shutdown, args=(3,), daemon=True).start()
                return "Shutting down in 3 seconds"
            case "restart":
                threading.Thread(target=self._delayed_restart, args=(3,), daemon=True).start()
                return "Restarting in 3 seconds"
            case "sleep":
                self._system_sleep()
                return "Entering sleep mode"
            case "lock":
                self._lock_screen()
                return "Screen locked"
            case "status":
                return self._get_system_info()
            case "run":
                return self._run_command(params.get("cmd", ""))
            case "launch":
                return self._launch_program(params.get("program", ""), params.get("args", []))
            case "screenshot":
                return self._take_screenshot()
            case "processes":
                return self._list_processes(params.get("limit", 10))
            case "kill":
                return self._kill_process(params.get("pid", 0), params.get("name", ""))
            case "volume":
                return self._set_volume(params.get("level", 50))
            case "notify":
                return self._show_notification(params.get("title", "NEXUS"), params.get("message", ""))
            case "ping":
                return "pong"
            case _:
                return f"Unknown command: {command}"

    def _get_system_info(self) -> dict:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        boot_time = psutil.boot_time()
        uptime = time.time() - boot_time

        info = {
            "online": True,
            "os": platform.system().lower(),
            "os_version": platform.version(),
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
        }

        if HAS_GPU:
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    info["gpu"] = {
                        "name": gpu.name,
                        "load": round(gpu.load * 100, 1),
                        "memory_used_mb": round(gpu.memoryUsed),
                        "memory_total_mb": round(gpu.memoryTotal),
                        "temperature": gpu.temperature,
                    }
            except Exception:
                pass

        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    if entries:
                        info["temp"] = round(entries[0].current, 1)
                        break
        except (AttributeError, Exception):
            pass

        info["network"] = self._get_network_stats()

        return info

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

    def _check_alerts(self, state: dict):
        now = time.time()
        alerts = []

        checks = [
            ("cpu", state.get("cpu", 0), self._alert_thresholds["cpu"], "CPU bei {val}%"),
            ("ram", state.get("ram", 0), self._alert_thresholds["ram"], "RAM bei {val}%"),
            ("disk", state.get("disk", 0), self._alert_thresholds["disk"], "Disk bei {val}%"),
        ]

        gpu = state.get("gpu")
        if gpu:
            checks.append(("gpu_temp", gpu.get("temperature", 0), self._alert_thresholds["gpu_temp"], "GPU Temperatur bei {val}°C"))
            checks.append(("gpu_load", gpu.get("load", 0), self._alert_thresholds["gpu_load"], "GPU Auslastung bei {val}%"))

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

    def _get_battery(self) -> dict | None:
        battery = psutil.sensors_battery()
        if battery:
            return {
                "percent": battery.percent,
                "plugged": battery.power_plugged,
                "secs_left": battery.secsleft if battery.secsleft > 0 else None,
            }
        return None

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

    def _launch_program(self, program: str, args: list) -> str:
        if not program:
            raise ValueError("No program specified")
        try:
            import uuid
            task_name = f"NexusLaunch_{uuid.uuid4().hex[:8]}"
            cmd_line = program if not args else f'{program} {" ".join(args)}'
            subprocess.run(
                f'schtasks /create /tn "{task_name}" /tr "{cmd_line}" /sc once /st 00:00 /f /IT /rl highest',
                shell=True, capture_output=True,
            )
            subprocess.run(f'schtasks /run /tn "{task_name}"', shell=True, capture_output=True)
            time.sleep(1)
            subprocess.run(f'schtasks /delete /tn "{task_name}" /f', shell=True, capture_output=True)
            return f"Launched: {program}"
        except Exception as e:
            raise RuntimeError(f"Failed to launch {program}: {e}")

    def _take_screenshot(self) -> str:
        try:
            import mss
            with mss.mss() as sct:
                path = Path(__file__).parent / "screenshot.png"
                sct.shot(output=str(path))
                return f"Screenshot saved to {path}"
        except ImportError:
            return "mss not installed — run: pip install mss"

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

    def _set_volume(self, level: int) -> str:
        if platform.system() == "Windows":
            try:
                from ctypes import cast, POINTER
                from comtypes import CLSCTX_ALL
                from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
                devices = AudioUtilities.GetSpeakers()
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = cast(interface, POINTER(IAudioEndpointVolume))
                volume.SetMasterVolumeLevelScalar(level / 100, None)
                return f"Volume set to {level}%"
            except ImportError:
                return "pycaw not installed — run: pip install pycaw"
        return "Volume control not supported on this OS"

    def _show_notification(self, title: str, message: str) -> str:
        if platform.system() == "Windows":
            try:
                from win10toast import ToastNotifier
                toaster = ToastNotifier()
                toaster.show_toast(title, message, duration=5, threaded=True)
                return "Notification shown"
            except ImportError:
                return "win10toast not installed — run: pip install win10toast"
        return "Notifications not supported on this OS"

    def _delayed_shutdown(self, delay: int):
        time.sleep(delay)
        self._publish_state(online=False)
        time.sleep(0.5)
        if platform.system() == "Windows":
            os.system("shutdown /s /hybrid /t 0")
        else:
            os.system("sudo shutdown -h now")

    def _delayed_restart(self, delay: int):
        time.sleep(delay)
        self._publish_state(online=False)
        time.sleep(0.5)
        if platform.system() == "Windows":
            os.system("shutdown /r /t 0")
        else:
            os.system("sudo reboot")

    def _system_sleep(self):
        if platform.system() == "Windows":
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")

    def _lock_screen(self):
        if platform.system() == "Windows":
            os.system("rundll32.exe user32.dll,LockWorkStation")

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
    agent = NexusAgent(config)

    def handle_signal(sig, frame):
        agent.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    agent.start()


if __name__ == "__main__":
    main()
