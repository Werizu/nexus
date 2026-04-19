"""NEXUS Scene Engine — loads and executes YAML-defined automation scenes."""

import asyncio
import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING

import yaml
from jinja2 import Template

if TYPE_CHECKING:
    from core.config import NexusConfig
    from core.plugin_manager import PluginManager
    from core.state_store import StateStore

logger = logging.getLogger("nexus.scenes")


class SceneEngine:
    def __init__(self, config: "NexusConfig", plugin_manager: "PluginManager", state_store: "StateStore"):
        self.config = config
        self.plugin_manager = plugin_manager
        self.state_store = state_store
        self.scenes: dict[str, dict] = {}
        self._scenes_dir = Path(__file__).parent.parent / config.scenes_dir

    async def load_scenes(self):
        """Load all scene YAML files from the scenes directory."""
        if not self._scenes_dir.exists():
            logger.warning(f"Scenes directory not found: {self._scenes_dir}")
            return

        for scene_file in self._scenes_dir.glob("*.yaml"):
            try:
                with open(scene_file) as f:
                    scene = yaml.safe_load(f)
                if scene and "name" in scene:
                    self.scenes[scene["name"]] = scene
                    logger.info(f"Loaded scene: {scene['name']} ({scene.get('display_name', '')})")
            except Exception as e:
                logger.error(f"Failed to load scene {scene_file}: {e}")

        logger.info(f"Loaded {len(self.scenes)} scenes")

    @staticmethod
    def _mask_actions(actions: list) -> list:
        masked = []
        for a in actions:
            ac = dict(a)
            if "password" in ac:
                ac["password"] = "••••••"
            masked.append(ac)
        return masked

    def list_scenes(self) -> list[dict]:
        return [
            {
                "name": s["name"],
                "display_name": s.get("display_name", s["name"]),
                "icon": s.get("icon", ""),
                "color": s.get("color", "#FFFFFF"),
                "triggers": s.get("triggers", []),
                "actions": self._mask_actions(s.get("actions", [])),
            }
            for s in self.scenes.values()
        ]

    def get_scene_full(self, name: str) -> dict | None:
        scene = self.scenes.get(name)
        if not scene:
            return None
        result = dict(scene)
        result["actions"] = self._mask_actions(result.get("actions", []))
        return result

    async def save_scene(self, scene_data: dict) -> dict:
        name = scene_data.get("name", "")
        if not name:
            return {"error": "Scene name is required"}

        existing = self.scenes.get(name, {})
        old_actions = existing.get("actions", [])
        for action in scene_data.get("actions", []):
            if action.get("password") == "••••••":
                for old in old_actions:
                    if old.get("action") == action.get("action") and old.get("device") == action.get("device"):
                        action["password"] = old.get("password", "")
                        break

        scene_file = self._scenes_dir / f"{name}.yaml"
        with open(scene_file, "w") as f:
            yaml.dump(scene_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        self.scenes[name] = scene_data
        logger.info(f"Saved scene: {name}")
        return {"status": "ok", "scene": name}

    async def delete_scene(self, name: str) -> dict:
        if name not in self.scenes:
            return {"error": f"Scene '{name}' not found"}

        scene_file = self._scenes_dir / f"{name}.yaml"
        if scene_file.exists():
            scene_file.unlink()

        del self.scenes[name]
        logger.info(f"Deleted scene: {name}")
        return {"status": "ok", "scene": name}

    def get_scene(self, name: str) -> dict | None:
        return self.scenes.get(name)

    async def execute(self, scene_name: str, params: dict | None = None) -> dict:
        """Execute a scene by name. Runs all actions sequentially."""
        scene = self.scenes.get(scene_name)
        if not scene:
            return {"error": f"Scene '{scene_name}' not found"}

        # Check conditions
        if not self._check_conditions(scene.get("conditions", [])):
            return {"status": "skipped", "reason": "Conditions not met"}

        actions = scene.get("actions", [])
        results = []

        await self.state_store.add_log("info", f"Scene '{scene_name}' started", data={"params": params or {}})

        for i, action in enumerate(actions):
            try:
                result = await self._execute_action(action, params or {})
                results.append({"step": i + 1, "action": action.get("action"), "result": result})
                logger.info(f"Scene {scene_name} step {i+1}: {action.get('action')} → {result}")
            except Exception as e:
                error = f"Step {i+1} failed: {e}"
                results.append({"step": i + 1, "action": action.get("action"), "error": str(e)})
                logger.error(f"Scene {scene_name}: {error}")
                # Continue with remaining actions unless it's critical

        await self.state_store.add_log("info", f"Scene '{scene_name}' completed", data={"results": results})
        return {"status": "completed", "steps": results}

    async def _execute_action(self, action: dict, params: dict) -> str:
        """Execute a single scene action."""
        action_type = action.get("action", "")
        device_id = action.get("device", "")

        # Resolve template variables in text fields
        text = action.get("text", "")
        if text and "{{" in text:
            text = await self._resolve_template(text, action.get("variables", {}))

        match action_type.split("."):
            case ["light", cmd]:
                return await self._action_device(device_id, cmd, action)
            case ["plug", cmd]:
                return await self._action_device(device_id, cmd, action)
            case ["pc", cmd]:
                return await self._action_pc(device_id, cmd, action)
            case ["pi", cmd]:
                return await self._action_device(device_id, cmd, action)
            case ["mac", cmd]:
                return await self._action_mac(cmd, action)
            case ["jarvis", "speak"]:
                return await self._action_speak(text)
            case ["wait"]:
                seconds = action.get("seconds", 1)
                await asyncio.sleep(seconds)
                return f"Waited {seconds}s"
            case _:
                return f"Unknown action: {action_type}"

    async def _action_device(self, device_id: str, command: str, action: dict) -> str:
        """Execute a command on a device via its plugin."""
        plugin = self.plugin_manager.get_plugin_for_device(device_id)
        if not plugin:
            return f"No plugin for device '{device_id}'"

        # Build params from action fields
        params = {k: v for k, v in action.items() if k not in ("action", "device")}

        success = await plugin.execute(device_id, command, params)
        return "ok" if success else "failed"

    async def _action_pc(self, device_id: str, command: str, action: dict) -> str:
        """PC-specific actions with wait support."""
        plugin = self.plugin_manager.get_plugin_for_device(device_id)
        if not plugin:
            return f"No plugin for device '{device_id}'"

        if command == "wake":
            success = await plugin.execute(device_id, "wake", {})
            if not success:
                return "WOL failed"

            if action.get("wait_until_online"):
                timeout = action.get("timeout", 60)
                return await self._wait_for_online(device_id, plugin, timeout)
            return "WOL sent"

        if command == "ssh_run":
            script = action.get("script", "")
            return await self._action_device(device_id, "ssh_run", {"script": script})

        return await self._action_device(device_id, command, action)

    async def _wait_for_online(self, device_id: str, plugin: Any, timeout: int) -> str:
        """Wait until a device comes online."""
        elapsed = 0
        interval = 5
        while elapsed < timeout:
            await asyncio.sleep(interval)
            elapsed += interval
            state = await plugin.get_state(device_id)
            if state.get("online"):
                return f"Online after {elapsed}s"
        return f"Timeout after {timeout}s"

    async def _action_mac(self, command: str, action: dict) -> str:
        """Mac-specific actions (VNC connect etc.)."""
        if command == "connect_vnc":
            host = action.get("host", "")
            return f"VNC connect to {host} (requires local execution)"
        return f"Unknown mac command: {command}"

    async def _action_speak(self, text: str) -> str:
        """Send text to Jarvis/Alexa for speech."""
        from core.mqtt_client import MQTTClient
        # This will be called through the plugin manager's mqtt client
        logger.info(f"Speak: {text}")
        return f"Speak: {text}"

    async def _resolve_template(self, text: str, variables: dict) -> str:
        """Resolve Jinja2 template variables in text."""
        context = {}
        for var_name, source in variables.items():
            parts = source.split(".")
            if len(parts) >= 2:
                # e.g., "pi.brain.last_status" → get state of device 'brain'
                device_id = parts[1] if len(parts) > 1 else parts[0]
                state = await self.state_store.get_device(device_id)
                if state:
                    context[var_name] = state.get("state", {})
                else:
                    context[var_name] = "unknown"

        try:
            return Template(text).render(**context)
        except Exception:
            return text

    def _check_conditions(self, conditions: list[dict]) -> bool:
        """Check if all conditions for a scene are met."""
        import datetime

        for cond in conditions:
            if "time_between" in cond:
                start_str, end_str = cond["time_between"]
                now = datetime.datetime.now().time()
                start = datetime.time.fromisoformat(start_str)
                end = datetime.time.fromisoformat(end_str)

                if start <= end:
                    if not (start <= now <= end):
                        return False
                else:
                    # Wraps midnight (e.g., 07:00 to 02:00)
                    if not (now >= start or now <= end):
                        return False

        return True
