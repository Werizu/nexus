"""Tasmota Plugin — controls Tasmota-flashed smart plugs and lights via HTTP."""

import logging

import httpx

from plugins.base_plugin import BasePlugin

logger = logging.getLogger("nexus.plugin.tasmota")


class TasmotaPlugin(BasePlugin):
    name = "tasmota"
    version = "1.0.0"
    device_type = "plug"

    def __init__(self):
        super().__init__()
        self._http = httpx.AsyncClient(timeout=5.0)

    async def initialize(self, config: dict) -> bool:
        logger.info("Tasmota plugin initialized")
        return True

    async def get_state(self, device_id: str) -> dict:
        device = self.get_device_config(device_id)
        if not device:
            return {"error": "Device not registered"}

        ip = device.get("ip")
        try:
            # Get power state
            resp = await self._http.get(f"http://{ip}/cm?cmnd=Status%200")
            data = resp.json()

            state = {
                "on": data.get("Status", {}).get("Power", 0) == 1,
                "online": True,
            }

            # Get energy data if supported
            if device.get("energy_monitoring"):
                energy = data.get("StatusSNS", {}).get("ENERGY", {})
                state["energy"] = {
                    "power_w": energy.get("Power", 0),
                    "voltage_v": energy.get("Voltage", 0),
                    "current_a": energy.get("Current", 0),
                    "today_kwh": energy.get("Today", 0),
                    "total_kwh": energy.get("Total", 0),
                }

            # Get color info for RGBW devices
            if device.get("type") == "rgbw":
                color_resp = await self._http.get(f"http://{ip}/cm?cmnd=Status%2011")
                color_data = color_resp.json()
                status_sts = color_data.get("StatusSTS", {})
                state["brightness"] = status_sts.get("Dimmer", 0)
                state["color"] = status_sts.get("Color", "")
                state["color_temp"] = status_sts.get("CT", 0)

            return state

        except Exception as e:
            logger.error(f"Failed to get state for {device_id} ({ip}): {e}")
            return {"on": False, "online": False, "error": str(e)}

    async def execute(self, device_id: str, command: str, params: dict) -> bool:
        device = self.get_device_config(device_id)
        if not device:
            return False

        ip = device.get("ip")
        tasmota_cmd = self._build_command(command, params, device)
        if not tasmota_cmd:
            logger.error(f"Unknown command '{command}' for {device_id}")
            return False

        try:
            resp = await self._http.get(f"http://{ip}/cm?cmnd={tasmota_cmd}")
            logger.info(f"Tasmota {device_id}: {tasmota_cmd} → {resp.status_code}")
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Failed to execute {command} on {device_id}: {e}")
            return False

    def _build_command(self, command: str, params: dict, device: dict) -> str | None:
        """Map NEXUS commands to Tasmota HTTP commands."""
        match command:
            case "on":
                return "Power%20On"
            case "off":
                return "Power%20Off"
            case "toggle":
                return "Power%20Toggle"
            case "brightness":
                level = params.get("level", 100)
                return f"Dimmer%20{level}"
            case "color":
                color = params.get("color", "FFFFFF")
                return f"Color%20{color}"
            case "color_temp":
                ct = params.get("ct", 326)
                return f"CT%20{ct}"
            case _:
                return None

    async def get_capabilities(self) -> list[str]:
        return ["on_off", "energy_monitoring", "brightness", "color_rgb"]

    async def on_mqtt_message(self, topic: str, payload: dict):
        # Handle Tasmota MQTT state updates
        parts = topic.split("/")
        if len(parts) >= 4 and parts[-1] == "state":
            device_name = parts[-2]
            for did, conf in self.devices.items():
                if conf.get("id") == device_name or did == device_name:
                    logger.info(f"MQTT state update for {did}: {payload}")

    async def health_check(self) -> bool:
        if not self.devices:
            return True
        # Check first device as canary
        for device_id, device in self.devices.items():
            try:
                resp = await self._http.get(f"http://{device['ip']}/cm?cmnd=Status", timeout=3)
                return resp.status_code == 200
            except Exception:
                return False
        return False
