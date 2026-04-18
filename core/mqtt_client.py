"""NEXUS MQTT Client — connects to Mosquitto broker for device communication."""

import asyncio
import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import NexusConfig
    from core.state_store import StateStore
    from core.websocket_server import WebSocketManager

logger = logging.getLogger("nexus.mqtt")


class MQTTClient:
    def __init__(self, config: "NexusConfig", state_store: "StateStore", ws_manager: "WebSocketManager"):
        self.config = config
        self.state_store = state_store
        self.ws_manager = ws_manager
        self.connected = False
        self._client = None
        self._task: asyncio.Task | None = None
        self._handlers: dict[str, list] = {}

    def subscribe(self, topic_pattern: str, handler):
        """Register a handler for an MQTT topic pattern."""
        if topic_pattern not in self._handlers:
            self._handlers[topic_pattern] = []
        self._handlers[topic_pattern].append(handler)

    async def publish(self, topic: str, payload: dict):
        """Publish a message to an MQTT topic."""
        if not self.connected or not self._client:
            logger.warning(f"MQTT not connected, cannot publish to {topic}")
            return
        try:
            import aiomqtt
            await self._client.publish(topic, json.dumps(payload))
            logger.debug(f"Published to {topic}")
        except Exception as e:
            logger.error(f"MQTT publish error: {e}")

    async def start(self):
        """Start MQTT connection in background task."""
        self._task = asyncio.create_task(self._connect_loop())

    async def _connect_loop(self):
        """Continuously try to connect to MQTT broker."""
        import aiomqtt

        while True:
            try:
                async with aiomqtt.Client(
                    self.config.mqtt_broker,
                    port=self.config.mqtt_port,
                    identifier=self.config.mqtt_client_id,
                ) as client:
                    self._client = client
                    self.connected = True
                    logger.info(f"Connected to MQTT broker at {self.config.mqtt_broker}:{self.config.mqtt_port}")

                    # Subscribe to all registered topics
                    prefix = self.config.mqtt_topic_prefix
                    await client.subscribe(f"{prefix}/#")
                    logger.info(f"Subscribed to {prefix}/#")

                    async for message in client.messages:
                        await self._handle_message(str(message.topic), message.payload)

            except Exception as e:
                self.connected = False
                self._client = None
                logger.warning(f"MQTT connection failed: {e}. Retrying in 5s...")
                await asyncio.sleep(5)

    async def _handle_message(self, topic: str, payload: bytes):
        """Route incoming MQTT messages to registered handlers."""
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = {"raw": payload.decode("utf-8", errors="replace")}

        logger.debug(f"MQTT received: {topic} → {data}")

        for pattern, handlers in self._handlers.items():
            if self._topic_matches(pattern, topic):
                for handler in handlers:
                    try:
                        await handler(topic, data)
                    except Exception as e:
                        logger.error(f"MQTT handler error for {topic}: {e}")

    @staticmethod
    def _topic_matches(pattern: str, topic: str) -> bool:
        """Check if a topic matches a pattern with + and # wildcards."""
        pattern_parts = pattern.split("/")
        topic_parts = topic.split("/")

        for i, part in enumerate(pattern_parts):
            if part == "#":
                return True
            if i >= len(topic_parts):
                return False
            if part != "+" and part != topic_parts[i]:
                return False

        return len(pattern_parts) == len(topic_parts)

    async def stop(self):
        self.connected = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("MQTT client stopped")
