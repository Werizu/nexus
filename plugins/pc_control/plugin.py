"""PC Control Plugin — Wake-on-LAN, SSH commands, status checks."""

import asyncio
import logging
import socket
from pathlib import Path

from wakeonlan import send_magic_packet

from plugins.base_plugin import BasePlugin

logger = logging.getLogger("nexus.plugin.pc_control")


class PCControlPlugin(BasePlugin):
    name = "pc_control"
    version = "1.0.0"
    device_type = "computer"

    def __init__(self):
        super().__init__()

    async def initialize(self, config: dict) -> bool:
        logger.info("PC Control plugin initialized")
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
        ip = device.get("ip", "")
        key = device.get("ssh_key", "")

        args = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5"]
        if key:
            resolved = self._resolve_key(key)
            if resolved:
                args += ["-i", resolved]
        args.append(f"{user}@{ip}")
        return args

    async def get_state(self, device_id: str) -> dict:
        device = self.get_device_config(device_id)
        if not device:
            return {"online": False, "error": "Not registered"}

        ip = device.get("ip")
        os_type = device.get("os", "linux")

        if os_type == "windows":
            port = device.get("check_port", 3389)
            online = await self._port_check(ip, port)
            if not online:
                online = await self._arp_check(ip)
        else:
            online = await self._ping(ip)

        return {"online": online, "ip": ip, "os": os_type}

    async def execute(self, device_id: str, command: str, params: dict) -> bool:
        device = self.get_device_config(device_id)
        if not device:
            return False

        match command:
            case "wake":
                return await self._wake(device)
            case "ssh_run":
                script = params.get("script", "")
                return await self._ssh_run(device, script)
            case "shutdown":
                if device.get("os") == "windows":
                    return await self._ssh_run(device, "shutdown /s /t 0")
                return await self._ssh_run(device, "sudo shutdown -h now")
            case "restart":
                if device.get("os") == "windows":
                    return await self._ssh_run(device, "shutdown /r /t 0")
                return await self._ssh_run(device, "sudo reboot")
            case _:
                logger.warning(f"Unknown PC command: {command}")
                return False

    async def _wake(self, device: dict) -> bool:
        mac = device.get("mac_address", "")
        if not mac:
            logger.error("No MAC address configured")
            return False
        try:
            send_magic_packet(mac)
            logger.info(f"WOL sent to {mac}")
            return True
        except Exception as e:
            logger.error(f"WOL failed: {e}")
            return False

    async def _ssh_run(self, device: dict, command: str) -> bool:
        try:
            args = self._ssh_args(device) + [command]
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            logger.info(f"SSH {device.get('ip')}: {command} → exit {proc.returncode}")
            if proc.returncode != 0:
                logger.warning(f"SSH stderr: {stderr.decode()}")
            return proc.returncode == 0
        except asyncio.TimeoutError:
            logger.error(f"SSH timeout for {device.get('ip')}")
            return False
        except Exception as e:
            logger.error(f"SSH failed: {e}")
            return False

    async def _ping(self, ip: str) -> bool:
        try:
            proc = await asyncio.create_subprocess_exec(
                "ping", "-c", "1", "-W", "2", ip,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=5)
            return proc.returncode == 0
        except Exception:
            return False

    async def _port_check(self, ip: str, port: int) -> bool:
        loop = asyncio.get_event_loop()
        try:
            await asyncio.wait_for(
                loop.run_in_executor(None, self._try_connect, ip, port),
                timeout=3,
            )
            return True
        except Exception:
            return False

    @staticmethod
    def _try_connect(ip: str, port: int):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            sock.connect((ip, port))
        finally:
            sock.close()

    async def _arp_check(self, ip: str) -> bool:
        # Trigger ARP resolution with a ping first
        ping = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", "1", ip,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            await asyncio.wait_for(ping.wait(), timeout=3)
        except asyncio.TimeoutError:
            pass
        try:
            proc = await asyncio.create_subprocess_exec(
                "ip", "neigh", "show", ip,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            output = stdout.decode()
            return "REACHABLE" in output or "STALE" in output or "DELAY" in output
        except Exception:
            return False

    async def get_capabilities(self) -> list[str]:
        return ["wake_on_lan", "ssh_command", "status_check", "shutdown"]
