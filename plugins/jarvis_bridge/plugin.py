"""Jarvis Bridge Plugin — secondary/text-based voice control channel."""

import logging

import httpx

from plugins.base_plugin import BasePlugin

logger = logging.getLogger("nexus.plugin.jarvis_bridge")


class JarvisBridgePlugin(BasePlugin):
    name = "jarvis_bridge"
    version = "1.0.0"
    device_type = "assistant"

    def __init__(self):
        super().__init__()
        self._http = httpx.AsyncClient(timeout=10.0)

    async def initialize(self, config: dict) -> bool:
        logger.info("Jarvis Bridge plugin initialized (secondary voice channel)")
        return True

    async def get_state(self, device_id: str) -> dict:
        return {"online": True, "role": "secondary"}

    async def execute(self, device_id: str, command: str, params: dict) -> bool:
        match command:
            case "speak":
                text = params.get("text", "")
                logger.info(f"Jarvis speak: {text}")
                # In production: send to Jarvis TTS endpoint
                return True
            case _:
                return False

    async def get_capabilities(self) -> list[str]:
        return ["speak", "command", "context_query"]

    async def on_mqtt_message(self, topic: str, payload: dict):
        if "speak" in topic:
            text = payload.get("text", "")
            logger.info(f"MQTT speak request: {text}")
