"""NEXUS Brain — FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from core.config import NexusConfig
from core.state_store import StateStore
from core.plugin_manager import PluginManager
from core.scene_engine import SceneEngine
from core.mqtt_client import MQTTClient
from core.websocket_server import WebSocketManager

logger = logging.getLogger("nexus")

# Global instances
config = NexusConfig()
state_store = StateStore(config.db_path)
ws_manager = WebSocketManager()
mqtt_client = MQTTClient(config, state_store, ws_manager)
plugin_manager = PluginManager(config, mqtt_client, state_store)
scene_engine = SceneEngine(config, plugin_manager, state_store)


def verify_auth(request: Request):
    if not config.auth_enabled:
        return
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if token != config.bearer_token:
        raise HTTPException(status_code=401, detail="Unauthorized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.basicConfig(level=config.log_level.upper())
    logger.info("NEXUS Brain starting up...")

    data_dir = Path(config.db_path).parent
    data_dir.mkdir(parents=True, exist_ok=True)

    await state_store.initialize()
    await plugin_manager.discover_and_load()
    await scene_engine.load_scenes()

    # MQTT runs in background — don't block if broker is unavailable
    await mqtt_client.start()

    # Wire up MQTT agent messages to pc_control plugin
    _setup_agent_mqtt()

    # Initial state refresh for all devices
    asyncio.create_task(refresh_all_device_states())
    # Periodic state refresh every 30 seconds
    _refresh_task = asyncio.create_task(periodic_state_refresh())

    logger.info("NEXUS Brain ready.")
    yield

    # Shutdown
    logger.info("NEXUS Brain shutting down...")
    _refresh_task.cancel()
    await mqtt_client.stop()
    await state_store.close()


def _setup_agent_mqtt():
    """Subscribe to MQTT agent topics and route to pc_control plugin."""
    pc_plugin = plugin_manager.plugins.get("pc_control")
    if not pc_plugin:
        return
    pc_plugin.set_mqtt_client(mqtt_client)

    async def on_agent_state(topic: str, data: dict):
        parts = topic.split("/")
        if len(parts) >= 4:
            device_id = parts[2]
            pc_plugin.handle_agent_state(device_id, data)
            await state_store.update_device(device_id, data)
            await ws_manager.broadcast({"event": "device_update", "device_id": device_id, "state": data})

    async def on_agent_response(topic: str, data: dict):
        parts = topic.split("/")
        if len(parts) >= 4:
            device_id = parts[2]
            pc_plugin.handle_agent_response(device_id, data)

    async def on_agent_alert(topic: str, data: dict):
        parts = topic.split("/")
        if len(parts) >= 4:
            device_id = parts[2]
            await state_store.add_alert(device_id, data)
            await state_store.add_log("warning", data.get("message", "Alert"), device=device_id, data=data)
            await ws_manager.broadcast({"event": "alert", "device_id": device_id, "alert": data})
            logger.warning(f"Alert from {device_id}: {data.get('message')}")

    mqtt_client.subscribe("nexus/agent/+/state", on_agent_state)
    mqtt_client.subscribe("nexus/agent/+/response", on_agent_response)
    mqtt_client.subscribe("nexus/agent/+/alert", on_agent_alert)
    logger.info("Agent MQTT handlers registered")


async def refresh_all_device_states():
    """Fetch current state for all devices that have a plugin."""
    for device_id, plugin_name in plugin_manager._device_plugin_map.items():
        plugin = plugin_manager.plugins.get(plugin_name)
        if plugin:
            try:
                device_state = await plugin.get_state(device_id)
                await state_store.update_device(device_id, device_state)
            except Exception as e:
                logger.debug(f"State refresh failed for {device_id}: {e}")
    logger.info(f"Device states refreshed ({len(plugin_manager._device_plugin_map)} devices)")


async def periodic_state_refresh():
    """Refresh all device states every 30 seconds."""
    while True:
        await asyncio.sleep(30)
        try:
            await refresh_all_device_states()
        except Exception as e:
            logger.error(f"Periodic state refresh error: {e}")


app = FastAPI(
    title="NEXUS",
    description="Smart Home & Automation System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount WebSocket
ws_manager.mount(app)


# ─── Health ───────────────────────────────────────────────
@app.get("/api/v1/health")
async def health():
    plugin_status = {
        name: await p.health_check() for name, p in plugin_manager.plugins.items()
    }
    return {
        "status": "ok",
        "mqtt_connected": mqtt_client.connected,
        "plugins": plugin_status,
        "devices_registered": state_store.device_count,
    }


# ─── Devices ──────────────────────────────────────────────
@app.get("/api/v1/devices", dependencies=[Depends(verify_auth)])
async def list_devices():
    return await state_store.get_all_devices()


@app.get("/api/v1/devices/{device_id}", dependencies=[Depends(verify_auth)])
async def get_device(device_id: str):
    device = await state_store.get_device(device_id)
    if not device:
        raise HTTPException(404, "Device not found")
    return device


@app.post("/api/v1/devices/{device_id}/command", dependencies=[Depends(verify_auth)])
async def device_command(device_id: str, body: dict):
    command = body.get("command")
    params = body.get("params", {})
    if not command:
        raise HTTPException(400, "Missing 'command' field")

    plugin = plugin_manager.get_plugin_for_device(device_id)
    if not plugin:
        raise HTTPException(404, f"No plugin found for device '{device_id}'")

    success = await plugin.execute(device_id, command, params)
    if not success:
        raise HTTPException(500, "Command execution failed")

    state = await plugin.get_state(device_id)
    await state_store.update_device(device_id, state)
    await ws_manager.broadcast({"event": "device_update", "device_id": device_id, "state": state})
    return {"status": "ok", "device_id": device_id, "state": state}


# ─── Scenes ──────────────────────────────────────────────
@app.get("/api/v1/scenes", dependencies=[Depends(verify_auth)])
async def list_scenes():
    return scene_engine.list_scenes()


@app.get("/api/v1/scenes/{scene_name}", dependencies=[Depends(verify_auth)])
async def get_scene(scene_name: str):
    scene = scene_engine.get_scene_full(scene_name)
    if not scene:
        raise HTTPException(404, f"Scene '{scene_name}' not found")
    return scene


@app.post("/api/v1/scenes", dependencies=[Depends(verify_auth)])
async def create_scene(body: dict):
    result = await scene_engine.save_scene(body)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.put("/api/v1/scenes/{scene_name}", dependencies=[Depends(verify_auth)])
async def update_scene(scene_name: str, body: dict):
    body["name"] = scene_name
    result = await scene_engine.save_scene(body)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@app.delete("/api/v1/scenes/{scene_name}", dependencies=[Depends(verify_auth)])
async def delete_scene(scene_name: str):
    result = await scene_engine.delete_scene(scene_name)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.post("/api/v1/scenes/{scene_name}/trigger", dependencies=[Depends(verify_auth)])
async def trigger_scene(scene_name: str, body: dict | None = None):
    scene = scene_engine.get_scene(scene_name)
    if not scene:
        raise HTTPException(404, f"Scene '{scene_name}' not found")

    await ws_manager.broadcast({"event": "scene_start", "scene": scene_name})
    result = await scene_engine.execute(scene_name, params=body or {})
    await ws_manager.broadcast({"event": "scene_complete", "scene": scene_name, "result": result})
    return {"status": "ok", "scene": scene_name, "result": result}


# ─── Rooms ───────────────────────────────────────────────
@app.get("/api/v1/rooms", dependencies=[Depends(verify_auth)])
async def list_rooms():
    rooms_data = {}
    for room_id, room in config.rooms.items():
        device_states = []
        for did in room.get("devices", []):
            dev = await state_store.get_device(did)
            if dev:
                device_states.append(dev)
        rooms_data[room_id] = {**room, "device_states": device_states}
    return rooms_data


@app.post("/api/v1/rooms/{room_name}/scene", dependencies=[Depends(verify_auth)])
async def room_scene(room_name: str, body: dict):
    scene_name = body.get("scene")
    if not scene_name:
        raise HTTPException(400, "Missing 'scene' field")
    # Find devices in room and apply scene
    room = config.rooms.get(room_name)
    if not room:
        raise HTTPException(404, f"Room '{room_name}' not found")
    for device_id in room.get("devices", []):
        plugin = plugin_manager.get_plugin_for_device(device_id)
        if plugin:
            await plugin.execute(device_id, scene_name, {})
    return {"status": "ok", "room": room_name, "scene": scene_name}


# ─── Pis ─────────────────────────────────────────────────
@app.get("/api/v1/pis", dependencies=[Depends(verify_auth)])
async def list_pis():
    pi_plugin = plugin_manager.plugins.get("pi_manager")
    if not pi_plugin:
        return []
    pis = []
    for pi_conf in config.devices.get("pis", []):
        state = await pi_plugin.get_state(pi_conf["id"])
        pis.append({**pi_conf, "state": state})
    return pis


# ─── Energy ──────────────────────────────────────────────
@app.get("/api/v1/plugs/{device_id}/energy", dependencies=[Depends(verify_auth)])
async def plug_energy(device_id: str):
    plugin = plugin_manager.get_plugin_for_device(device_id)
    if not plugin:
        raise HTTPException(404, "Device not found")
    state = await plugin.get_state(device_id)
    return {"device_id": device_id, "energy": state.get("energy", {})}


# ─── Alexa Skill Endpoint ────────────────────────────────

# Scene name mapping: spoken name → NEXUS scene name
ALEXA_SCENE_MAP = {
    "programmier modus": "dev_mode",
    "programmieren": "dev_mode",
    "dev mode": "dev_mode",
    "wir programmieren was": "dev_mode",
    "guten morgen": "morning",
    "morgen routine": "morning",
    "filmabend": "movie_mode",
    "film abend": "movie_mode",
    "gute nacht": "sleep",
    "schlaf modus": "sleep",
    "tschüss": "leave_home",
    "ich gehe": "leave_home",
    "alles aus": "all_off",
}

# Device name mapping: spoken name → NEXUS device ID
ALEXA_DEVICE_MAP = {
    "desktop pc": "main_pc",
    "pc": "main_pc",
    "computer": "main_pc",
    "rechner": "main_pc",
    "schreibtisch licht": "office_desk",
    "büro licht": "office_desk",
    "monitor steckerleiste": "monitor_strip",
    "monitor steckdose": "monitor_strip",
    "wohnzimmer strip": "living_strip",
    "led strip": "living_strip",
}


def alexa_response(speech: str, should_end: bool = True) -> dict:
    return {
        "version": "1.0",
        "response": {
            "outputSpeech": {"type": "PlainText", "text": speech},
            "shouldEndSession": should_end,
        },
    }


@app.post("/api/v1/alexa")
async def alexa_endpoint(request: Request):
    """Direct Alexa Skill endpoint — no Lambda needed."""
    try:
        event = await request.json()
        request_type = event.get("request", {}).get("type", "")

        if request_type == "LaunchRequest":
            return alexa_response("NEXUS bereit. Was soll ich tun?", should_end=False)

        if request_type == "IntentRequest":
            intent = event["request"]["intent"]
            intent_name = intent["name"]

            # --- TriggerSceneIntent ---
            if intent_name == "TriggerSceneIntent":
                slot = intent.get("slots", {}).get("scene", {})
                spoken = (slot.get("value") or "").lower().strip()
                scene_id = ALEXA_SCENE_MAP.get(spoken)
                if not scene_id:
                    return alexa_response(f"Ich kenne die Szene {spoken} nicht.")
                scene = scene_engine.get_scene(scene_id)
                if not scene:
                    return alexa_response(f"Szene {spoken} nicht gefunden.")
                await scene_engine.execute(scene_id)
                return alexa_response(f"Szene {spoken} wurde gestartet.")

            # --- DeviceOnIntent ---
            if intent_name == "DeviceOnIntent":
                slot = intent.get("slots", {}).get("device", {})
                spoken = (slot.get("value") or "").lower().strip()
                device_id = ALEXA_DEVICE_MAP.get(spoken)
                if not device_id:
                    return alexa_response(f"Ich kenne das Gerät {spoken} nicht.")
                plugin = plugin_manager.get_plugin_for_device(device_id)
                if plugin:
                    await plugin.execute(device_id, "on", {})
                return alexa_response(f"{spoken} wurde eingeschaltet.")

            # --- DeviceOffIntent ---
            if intent_name == "DeviceOffIntent":
                slot = intent.get("slots", {}).get("device", {})
                spoken = (slot.get("value") or "").lower().strip()
                device_id = ALEXA_DEVICE_MAP.get(spoken)
                if not device_id:
                    return alexa_response(f"Ich kenne das Gerät {spoken} nicht.")
                plugin = plugin_manager.get_plugin_for_device(device_id)
                if plugin:
                    await plugin.execute(device_id, "off", {})
                return alexa_response(f"{spoken} wurde ausgeschaltet.")

            # --- WakeComputerIntent ---
            if intent_name == "WakeComputerIntent":
                plugin = plugin_manager.get_plugin_for_device("main_pc")
                if plugin:
                    await plugin.execute("main_pc", "wake", {})
                return alexa_response("PC wird hochgefahren.")

            # --- StatusIntent ---
            if intent_name == "StatusIntent":
                devices = await state_store.get_all_devices()
                online = [d for d in devices if d.get("state", {}).get("online")]
                mqtt = "verbunden" if mqtt_client.connected else "nicht verbunden"
                speech = (
                    f"NEXUS läuft. {len(online)} von {len(devices)} Geräten sind online. "
                    f"MQTT ist {mqtt}."
                )
                return alexa_response(speech)

            # --- EnergyIntent ---
            if intent_name == "EnergyIntent":
                devices = await state_store.get_all_devices()
                total_watts = 0
                total_kwh = 0
                for d in devices:
                    energy = d.get("state", {}).get("energy", {})
                    total_watts += energy.get("power_w", 0)
                    total_kwh += energy.get("today_kwh", 0)
                if total_watts == 0 and total_kwh == 0:
                    return alexa_response("Aktuell sind keine Energiedaten verfügbar.")
                return alexa_response(
                    f"Aktueller Verbrauch: {total_watts:.0f} Watt. "
                    f"Heute insgesamt: {total_kwh:.1f} Kilowattstunden."
                )

            # --- AllOffIntent ---
            if intent_name == "AllOffIntent":
                await scene_engine.execute("all_off")
                return alexa_response("Alles wurde ausgeschaltet.")

            # --- Built-in Intents ---
            if intent_name == "AMAZON.HelpIntent":
                return alexa_response(
                    "Du kannst Szenen starten, Geräte steuern oder den Status abfragen. "
                    "Sage zum Beispiel: Programmier Modus, oder: PC hochfahren.",
                    should_end=False,
                )
            if intent_name in ("AMAZON.StopIntent", "AMAZON.CancelIntent"):
                return alexa_response("Bis später.")

            return alexa_response("Das habe ich nicht verstanden.")

        if request_type == "SessionEndedRequest":
            return alexa_response("")

        return alexa_response("Etwas ist schiefgelaufen.")

    except Exception as e:
        logger.error(f"Alexa endpoint error: {e}")
        return alexa_response("Es gab einen Fehler bei der Verarbeitung.")


# ─── Jarvis / Alexa ──────────────────────────────────────
@app.post("/api/v1/jarvis/speak", dependencies=[Depends(verify_auth)])
async def jarvis_speak(body: dict):
    text = body.get("text", "")
    await mqtt_client.publish("nexus/jarvis/speak", {"text": text})
    return {"status": "ok", "text": text}


@app.post("/api/v1/jarvis/command", dependencies=[Depends(verify_auth)])
async def jarvis_command(body: dict):
    command_text = body.get("text", "")
    # Parse command and route to appropriate action
    return {"status": "ok", "received": command_text}


# ─── Alerts ──────────────────────────────────────────────
@app.get("/api/v1/alerts", dependencies=[Depends(verify_auth)])
async def list_alerts(device: str | None = None, limit: int = 50, unacked: bool = False):
    return await state_store.get_alerts(device_id=device, limit=limit, unacked_only=unacked)


@app.post("/api/v1/alerts/{alert_id}/ack", dependencies=[Depends(verify_auth)])
async def ack_alert(alert_id: int):
    await state_store.acknowledge_alert(alert_id)
    return {"status": "ok"}


@app.post("/api/v1/alerts/ack-all", dependencies=[Depends(verify_auth)])
async def ack_all_alerts():
    await state_store.acknowledge_all_alerts()
    return {"status": "ok"}


# ─── Logs ────────────────────────────────────────────────
@app.get("/api/v1/logs", dependencies=[Depends(verify_auth)])
async def get_logs(level: str = "info", device: str | None = None, limit: int = 100):
    logs = await state_store.get_logs(level=level, device=device, limit=limit)
    return logs
