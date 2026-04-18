"""PC Control Plugin — MQTT Agent + WOL fallback."""

import asyncio
import json
import logging
import socket
from pathlib import Path

from wakeonlan import send_magic_packet

from plugins.base_plugin import BasePlugin

logger = logging.getLogger("nexus.plugin.pc_control")


class PCControlPlugin(BasePlugin):
    name = "pc_control"
    version = "2.0.0"
    device_type = "computer"

    def __init__(self):
        super().__init__()
        self._mqtt_client = None
        self._agent_states: dict[str, dict] = {}
        self._pending_responses: dict[str, asyncio.Future] = {}

    async def initialize(self, config: dict) -> bool:
        logger.info("PC Control plugin initialized (MQTT agent mode)")
        return True

    def set_mqtt_client(self, mqtt_client):
        self._mqtt_client = mqtt_client

    def handle_agent_state(self, device_id: str, state: dict):
        self._agent_states[device_id] = state
        logger.debug(f"Agent state update for {device_id}: online={state.get('online')}")

    def handle_agent_response(self, device_id: str, response: dict):
        request_id = response.get("request_id", "")
        if request_id in self._pending_responses:
            self._pending_responses[request_id].set_result(response)

    async def get_state(self, device_id: str) -> dict:
        device = self.get_device_config(device_id)
        if not device:
            return {"online": False, "error": "Not registered"}

        agent_state = self._agent_states.get(device_id)
        if agent_state and agent_state.get("online"):
            return agent_state

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

        if command == "wake":
            return await self._wake(device)

        if self._has_agent(device_id):
            return await self._send_agent_command(device_id, command, params)

        match command:
            case "shutdown" | "restart" | "sleep" | "lock" | "run" | "launch" | "processes" | "kill":
                logger.warning(f"Agent not connected for {device_id}, cannot execute '{command}'")
                return False
            case _:
                logger.warning(f"Unknown PC command: {command}")
                return False

    def _has_agent(self, device_id: str) -> bool:
        state = self._agent_states.get(device_id, {})
        return state.get("online", False)

    async def _send_agent_command(self, device_id: str, command: str, params: dict) -> bool:
        if not self._mqtt_client:
            logger.error("No MQTT client available")
            return False

        import uuid
        request_id = str(uuid.uuid4())[:8]
        topic = f"nexus/agent/{device_id}/cmd"
        payload = {"command": command, "params": params, "request_id": request_id}

        future = asyncio.get_event_loop().create_future()
        self._pending_responses[request_id] = future

        try:
            await self._mqtt_client.publish(topic, payload)
            response = await asyncio.wait_for(future, timeout=15)
            success = response.get("status") == "ok"
            if success:
                logger.info(f"Agent {device_id}: {command} → {response.get('result', 'ok')}")
            else:
                logger.warning(f"Agent {device_id}: {command} failed → {response.get('error', '?')}")
            return success
        except asyncio.TimeoutError:
            logger.warning(f"Agent {device_id}: {command} timed out")
            return False
        finally:
            self._pending_responses.pop(request_id, None)

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
        return ["wake_on_lan", "shutdown", "restart", "sleep", "lock", "run_command",
                "launch_program", "system_info", "processes", "kill_process", "screenshot"]
