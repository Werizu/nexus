"""Pi Manager Plugin — monitor and control Raspberry Pis via SSH."""

import asyncio
import logging
from pathlib import Path

from plugins.base_plugin import BasePlugin

logger = logging.getLogger("nexus.plugin.pi_manager")


class PiManagerPlugin(BasePlugin):
    name = "pi_manager"
    version = "1.0.0"
    device_type = "pi"

    def __init__(self):
        super().__init__()

    async def initialize(self, config: dict) -> bool:
        logger.info("Pi Manager plugin initialized")
        return True

    def _resolve_key(self, key: str) -> str | None:
        expanded = Path(key).expanduser()
        if expanded.exists():
            return str(expanded)
        fallback = Path("/root/.ssh/pi_manager_rsa")
        if fallback.exists():
            return str(fallback)
        return None

    def _ssh_args(self, device: dict) -> list[str]:
        user = device.get("ssh_user", "marlon")
        hostname = device.get("hostname", "")
        key = device.get("ssh_key", "")

        args = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5"]
        if key:
            resolved = self._resolve_key(key)
            if resolved:
                args += ["-i", resolved]
        args.append(f"{user}@{hostname}")
        return args

    async def get_state(self, device_id: str) -> dict:
        device = self.get_device_config(device_id)
        if not device:
            return {"online": False}

        hostname = device.get("hostname", "")
        try:
            metrics = await self._get_metrics(device)
            return {
                "online": True,
                "hostname": hostname,
                "role": device.get("role", ""),
                **metrics,
            }
        except Exception as e:
            logger.error(f"Failed to get Pi metrics for {device_id}: {e}")
            return {"online": False, "hostname": hostname, "error": str(e)}

    async def _get_metrics(self, device: dict) -> dict:
        cmd = (
            "echo CPU:$(top -bn1 | grep 'Cpu(s)' | awk '{print $2}');"
            "echo RAM:$(free | awk '/Mem:/{printf \"%.1f\", $3/$2*100}');"
            "echo TEMP:$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{printf \"%.1f\", $1/1000}');"
            "echo UPTIME:$(awk '{print int($1)}' /proc/uptime);"
            "echo DISK:$(df / | awk 'NR==2{printf \"%.1f\", $5}')"
        )

        args = self._ssh_args(device) + [cmd]
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
        output = stdout.decode()

        metrics = {}
        for line in output.strip().split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                try:
                    metrics[key.lower().strip()] = float(val.strip())
                except ValueError:
                    metrics[key.lower().strip()] = val.strip()

        return metrics

    async def execute(self, device_id: str, command: str, params: dict) -> bool:
        device = self.get_device_config(device_id)
        if not device:
            return False

        match command:
            case "start_vnc":
                return await self._ssh_cmd(device, "vncserver :1 -geometry 1920x1080 -depth 24 2>/dev/null || true")
            case "stop_vnc":
                return await self._ssh_cmd(device, "vncserver -kill :1 2>/dev/null || true")
            case "reboot":
                return await self._ssh_cmd(device, "sudo reboot")
            case "shutdown":
                return await self._ssh_cmd(device, "sudo shutdown -h now")
            case "ssh_run":
                return await self._ssh_cmd(device, params.get("script", ""))
            case _:
                logger.warning(f"Unknown Pi command: {command}")
                return False

    async def _ssh_cmd(self, device: dict, command: str) -> bool:
        try:
            args = self._ssh_args(device) + [command]
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.communicate(), timeout=30)
            return proc.returncode == 0
        except Exception as e:
            hostname = device.get("hostname", "?")
            logger.error(f"SSH to {hostname} failed: {e}")
            return False

    async def get_capabilities(self) -> list[str]:
        return ["status_check", "ssh_command", "vnc_control", "system_metrics"]
