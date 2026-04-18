"""Philips Hue Plugin — controls Hue lights and plugs via the Bridge HTTP API."""

import logging

import httpx

from plugins.base_plugin import BasePlugin

logger = logging.getLogger("nexus.plugin.hue")


class HuePlugin(BasePlugin):
    name = "hue_lights"
    version = "1.0.0"
    device_type = "light"

    def __init__(self):
        super().__init__()
        self._http = httpx.AsyncClient(timeout=5.0)
        self._bridge_ip: str = ""
        self._api_key: str = ""
        self._light_ids: dict[str, str] = {}

    async def initialize(self, config: dict) -> bool:
        secrets = config.get("_secrets", {})
        self._api_key = secrets.get("api_key", "")
        self._bridge_ip = secrets.get("bridge_ip", "")

        if self._api_key and self._bridge_ip:
            logger.info(f"Hue plugin initialized (bridge: {self._bridge_ip})")
        else:
            logger.warning("Hue plugin: no API key or bridge IP configured in secrets.yaml")
        return True

    def register_device(self, device_id: str, device_config: dict):
        super().register_device(device_id, device_config)
        if not self._bridge_ip and device_config.get("bridge_ip"):
            self._bridge_ip = device_config["bridge_ip"]
        if device_config.get("hue_id"):
            self._light_ids[device_id] = device_config["hue_id"]

    @property
    def _base_url(self) -> str:
        return f"http://{self._bridge_ip}/api/{self._api_key}"

    async def get_state(self, device_id: str) -> dict:
        device = self.get_device_config(device_id)
        if not device:
            return {"error": "Device not registered"}

        hue_id = self._light_ids.get(device_id)
        if not hue_id:
            return {"on": False, "online": False, "error": "No hue_id configured"}

        if not self._api_key:
            return {"on": False, "online": False, "error": "No API key"}

        try:
            resp = await self._http.get(f"{self._base_url}/lights/{hue_id}")
            data = resp.json()
            state = data.get("state", {})
            return {
                "on": state.get("on", False),
                "brightness": round(state.get("bri", 0) / 254 * 100),
                "color_temp": state.get("ct", 0),
                "reachable": state.get("reachable", False),
                "online": state.get("reachable", False),
            }
        except Exception as e:
            logger.error(f"Failed to get Hue state for {device_id}: {e}")
            return {"on": False, "online": False, "error": str(e)}

    async def execute(self, device_id: str, command: str, params: dict) -> bool:
        hue_id = self._light_ids.get(device_id)
        if not hue_id:
            logger.error(f"No Hue light ID for {device_id}")
            return False

        body = self._build_state(command, params)
        if body is None:
            return False

        try:
            resp = await self._http.put(f"{self._base_url}/lights/{hue_id}/state", json=body)
            result = resp.json()
            success = any("success" in r for r in result) if isinstance(result, list) else False
            if success:
                logger.info(f"Hue {device_id} ({hue_id}): {command}")
            else:
                logger.warning(f"Hue {device_id} ({hue_id}): {command} failed: {result}")
            return success
        except Exception as e:
            logger.error(f"Hue execute failed for {device_id}: {e}")
            return False

    def _build_state(self, command: str, params: dict) -> dict | None:
        match command:
            case "on":
                return {"on": True}
            case "off":
                return {"on": False}
            case "brightness":
                level = params.get("level", 100)
                return {"on": True, "bri": round(level / 100 * 254)}
            case "color_temp":
                ct = params.get("ct", 326)
                return {"on": True, "ct": ct}
            case "focus":
                return {"on": True, "bri": 178, "ct": 250}
            case "relax":
                return {"on": True, "bri": 144, "ct": 447}
            case "scene":
                scene = params.get("scene", "focus")
                return self._build_state(scene, {})
            case _:
                return {"on": True}

    async def get_capabilities(self) -> list[str]:
        return ["on_off", "brightness", "color_temp"]
