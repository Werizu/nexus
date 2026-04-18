"""Alexa Bridge Plugin — primary voice control via Custom Alexa Skill.

The Alexa Custom Skill sends requests to NEXUS via the REST API.
This plugin provides context and handles Alexa-specific routing.
"""

import logging

from plugins.base_plugin import BasePlugin

logger = logging.getLogger("nexus.plugin.alexa_bridge")


class AlexaBridgePlugin(BasePlugin):
    name = "alexa_bridge"
    version = "1.0.0"
    device_type = "assistant"

    def __init__(self):
        super().__init__()

    async def initialize(self, config: dict) -> bool:
        logger.info("Alexa Bridge plugin initialized (primary voice channel)")
        return True

    async def get_state(self, device_id: str) -> dict:
        return {"online": True, "role": "primary"}

    async def execute(self, device_id: str, command: str, params: dict) -> bool:
        match command:
            case "scene_trigger":
                scene = params.get("scene", "")
                logger.info(f"Alexa triggered scene: {scene}")
                return True
            case "device_control":
                device = params.get("device", "")
                action = params.get("action", "")
                logger.info(f"Alexa device control: {device} → {action}")
                return True
            case _:
                return False

    async def get_capabilities(self) -> list[str]:
        return ["scene_trigger", "device_control", "status_query"]

    async def build_context(self, state_store) -> dict:
        """Build context for Alexa response cards — what's currently active."""
        devices = await state_store.get_all_devices()
        active = [d for d in devices if d.get("state", {}).get("on")]
        return {
            "active_devices": [d["name"] for d in active],
            "active_count": len(active),
            "total_devices": len(devices),
        }
