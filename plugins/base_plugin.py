"""NEXUS Base Plugin — abstract interface all plugins must implement."""

from abc import ABC, abstractmethod
from typing import Any


class BasePlugin(ABC):
    """Base class for all NEXUS device plugins.

    Every plugin must implement initialize, get_state, execute, and get_capabilities.
    Optional overrides: on_mqtt_message, health_check, get_dashboard_widget.
    """

    name: str = ""
    version: str = "1.0.0"
    device_type: str = ""  # 'light' | 'plug' | 'computer' | 'sensor' | 'pi'

    def __init__(self):
        self.devices: dict[str, dict] = {}  # device_id → device config
        self._initialized = False

    @abstractmethod
    async def initialize(self, config: dict) -> bool:
        """Initialize the plugin with its configuration. Return True on success."""
        ...

    @abstractmethod
    async def get_state(self, device_id: str) -> dict:
        """Get current state of a device. Returns dict with device-specific state."""
        ...

    @abstractmethod
    async def execute(self, device_id: str, command: str, params: dict) -> bool:
        """Execute a command on a device. Return True on success."""
        ...

    @abstractmethod
    async def get_capabilities(self) -> list[str]:
        """Return list of supported capabilities (e.g., 'on_off', 'brightness')."""
        ...

    async def on_mqtt_message(self, topic: str, payload: dict):
        """Handle incoming MQTT messages for this plugin's topics."""
        pass

    async def health_check(self) -> bool:
        """Check if the plugin and its devices are reachable."""
        return self._initialized

    def get_dashboard_widget(self) -> dict:
        """Return widget configuration for the dashboard."""
        return {
            "type": self.device_type,
            "name": self.name,
            "devices": list(self.devices.keys()),
        }

    def register_device(self, device_id: str, device_config: dict):
        """Register a device with this plugin."""
        self.devices[device_id] = device_config

    def get_device_config(self, device_id: str) -> dict | None:
        return self.devices.get(device_id)
