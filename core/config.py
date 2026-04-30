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

    # --- Mutators ---
    def save_devices(self):
        with open(self.config_dir / "devices.yaml", "w") as f:
            yaml.dump({"devices": self._devices.get("devices", {})}, f,
                      default_flow_style=False, allow_unicode=True, sort_keys=False)

    def add_device(self, category: str, device: dict):
        devices = self._devices.setdefault("devices", {})
        devices.setdefault(category, []).append(device)
        self.save_devices()

    def update_device(self, device_id: str, updates: dict):
        for category in self.devices.values():
            for i, dev in enumerate(category):
                if dev["id"] == device_id:
                    category[i] = {**dev, **updates, "id": device_id}
                    self.save_devices()
                    return category[i]
        return None

    def delete_device(self, device_id: str) -> bool:
        for category in self.devices.values():
            for dev in category:
                if dev["id"] == device_id:
                    category.remove(dev)
                    self.save_devices()
                    return True
        return False

    def save_rooms(self):
        with open(self.config_dir / "rooms.yaml", "w") as f:
            yaml.dump({"rooms": self._rooms.get("rooms", {})}, f,
                      default_flow_style=False, allow_unicode=True, sort_keys=False)

    def add_room(self, room_id: str, room: dict):
        rooms = self._rooms.setdefault("rooms", {})
        rooms[room_id] = room
        self.save_rooms()

    def update_room(self, room_id: str, updates: dict):
        rooms = self._rooms.get("rooms", {})
        if room_id not in rooms:
            return None
        rooms[room_id] = {**rooms[room_id], **updates}
        self.save_rooms()
        return rooms[room_id]

    def delete_room(self, room_id: str) -> bool:
        rooms = self._rooms.get("rooms", {})
        if room_id in rooms:
            del rooms[room_id]
            self.save_rooms()
            return True
        return False
