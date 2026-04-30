"""NEXUS Plugin Manager — auto-discovers and loads plugins from the plugins directory."""

import importlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from plugins.base_plugin import BasePlugin

if TYPE_CHECKING:
    from core.config import NexusConfig
    from core.mqtt_client import MQTTClient
    from core.state_store import StateStore

logger = logging.getLogger("nexus.plugins")

PLUGINS_DIR = Path(__file__).parent.parent / "plugins"


class PluginManager:
    def __init__(self, config: "NexusConfig", mqtt_client: "MQTTClient", state_store: "StateStore"):
        self.config = config
        self.mqtt_client = mqtt_client
        self.state_store = state_store
        self.plugins: dict[str, BasePlugin] = {}
        self._device_plugin_map: dict[str, str] = {}  # device_id → plugin_name

    async def discover_and_load(self):
        """Scan plugins directory and load all valid plugins."""
        for plugin_dir in PLUGINS_DIR.iterdir():
            if not plugin_dir.is_dir() or plugin_dir.name.startswith("_"):
                continue

            plugin_yaml = plugin_dir / "plugin.yaml"
            if not plugin_yaml.exists():
                continue

            try:
                await self._load_plugin(plugin_dir, plugin_yaml)
            except Exception as e:
                logger.error(f"Failed to load plugin from {plugin_dir.name}: {e}")

        # Register devices from config
        await self._register_devices()

        # Wire cross-plugin references
        pc_plugin = self.plugins.get("pc_control")
        if pc_plugin and hasattr(pc_plugin, "set_plugin_manager"):
            pc_plugin.set_plugin_manager(self)

        logger.info(f"Loaded {len(self.plugins)} plugins, {len(self._device_plugin_map)} devices mapped")

    async def _load_plugin(self, plugin_dir: Path, plugin_yaml: Path):
        """Load a single plugin from its directory."""
        with open(plugin_yaml) as f:
            plugin_config = yaml.safe_load(f)

        plugin_name = plugin_config["name"]

        # Import the plugin module
        module_name = f"plugins.{plugin_dir.name}.plugin"
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            logger.warning(f"No plugin.py found in {plugin_dir.name}, skipping")
            return

        # Find the plugin class (subclass of BasePlugin)
        plugin_class = None
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and issubclass(attr, BasePlugin)
                    and attr is not BasePlugin):
                plugin_class = attr
                break

        if not plugin_class:
            logger.warning(f"No BasePlugin subclass found in {module_name}")
            return

        plugin = plugin_class()
        plugin.name = plugin_name
        plugin.version = plugin_config.get("version", "1.0.0")
        plugin.device_type = plugin_config.get("device_type", "unknown")

        plugin_config["_secrets"] = {
            k: self.config.secret(plugin_name.replace("_lights", ""), k)
            for k in ("api_key", "bridge_ip")
            if self.config.secret(plugin_name.replace("_lights", ""), k)
        }
        success = await plugin.initialize(plugin_config)
        if success:
            plugin._initialized = True
            self.plugins[plugin_name] = plugin

            # Register MQTT handlers
            for topic in plugin_config.get("mqtt_topics", {}).values():
                self.mqtt_client.subscribe(topic, plugin.on_mqtt_message)

            logger.info(f"Loaded plugin: {plugin_name} v{plugin.version} ({plugin.device_type})")
        else:
            logger.error(f"Plugin {plugin_name} initialization failed")

    async def _register_devices(self):
        """Map devices from config to their plugins."""
        for category, device_list in self.config.devices.items():
            for device in device_list:
                device_id = device["id"]
                plugin_name = device.get("plugin", "")

                if plugin_name in self.plugins:
                    self.plugins[plugin_name].register_device(device_id, device)
                    self._device_plugin_map[device_id] = plugin_name

                # Register in state store
                await self.state_store.register_device(
                    device_id=device_id,
                    category=category,
                    name=device.get("name", device_id),
                    plugin=plugin_name,
                    room=device.get("room"),
                    device_config=device,
                )

    async def register_single_device(self, device_id: str, device: dict, plugin_name: str):
        """Register a single device at runtime (e.g. from agent registration)."""
        if plugin_name in self.plugins:
            self.plugins[plugin_name].register_device(device_id, device)
            self._device_plugin_map[device_id] = plugin_name

    def get_plugin_for_device(self, device_id: str) -> BasePlugin | None:
        plugin_name = self._device_plugin_map.get(device_id)
        if plugin_name:
            return self.plugins.get(plugin_name)
        return None

    def get_plugin(self, name: str) -> BasePlugin | None:
        return self.plugins.get(name)
