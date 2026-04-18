"""NEXUS configuration loader — reads all YAML configs."""

import os
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).parent.parent / "config"


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


class NexusConfig:
    def __init__(self, config_dir: Path = CONFIG_DIR):
        self.config_dir = config_dir
        self._system = load_yaml(config_dir / "nexus.yaml")
        self._devices = load_yaml(config_dir / "devices.yaml")
        self._rooms = load_yaml(config_dir / "rooms.yaml")
        self._secrets = self._load_secrets()

    def _load_secrets(self) -> dict:
        secrets_path = self.config_dir / "secrets.yaml"
        if secrets_path.exists():
            return load_yaml(secrets_path)
        return {}

    # --- System ---
    @property
    def host(self) -> str:
        return self._system["system"]["host"]

    @property
    def port(self) -> int:
        return self._system["system"]["port"]

    @property
    def log_level(self) -> str:
        return self._system["system"]["log_level"]

    # --- MQTT ---
    @property
    def mqtt_broker(self) -> str:
        return os.environ.get("MQTT_BROKER", self._system["mqtt"]["broker"])

    @property
    def mqtt_port(self) -> int:
        return self._system["mqtt"]["port"]

    @property
    def mqtt_client_id(self) -> str:
        return self._system["mqtt"]["client_id"]

    @property
    def mqtt_topic_prefix(self) -> str:
        return self._system["mqtt"]["topic_prefix"]

    # --- Database ---
    @property
    def db_path(self) -> str:
        return self._system["database"]["path"]

    # --- Auth ---
    @property
    def auth_enabled(self) -> bool:
        return self._system["auth"]["enabled"]

    @property
    def bearer_token(self) -> str | None:
        return self._secrets.get("auth", {}).get("bearer_token")

    # --- Devices ---
    @property
    def devices(self) -> dict:
        return self._devices.get("devices", {})

    def get_device(self, device_id: str) -> dict | None:
        for category in self.devices.values():
            for device in category:
                if device["id"] == device_id:
                    return device
        return None

    # --- Rooms ---
    @property
    def rooms(self) -> dict:
        return self._rooms.get("rooms", {})

    # --- Plugins ---
    @property
    def plugin_dir(self) -> str:
        return self._system["plugins"]["directory"]

    @property
    def scenes_dir(self) -> str:
        return self._system["scenes"]["directory"]

    def secret(self, *keys: str) -> Any:
        """Get a nested secret value: config.secret('hue', 'api_key')"""
        val = self._secrets
        for k in keys:
            if not isinstance(val, dict):
                return None
            val = val.get(k)
        return val
