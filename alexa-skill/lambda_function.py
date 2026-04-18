"""NEXUS Alexa Skill — Lambda function that bridges Alexa to the NEXUS API."""

import json
import os
import urllib.request
import urllib.error

NEXUS_API = os.environ.get("NEXUS_API_URL", "https://server2.tail5116e1.ts.net")

# Scene name mapping: spoken name → NEXUS scene name
SCENE_MAP = {
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
DEVICE_MAP = {
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


def nexus_request(path, method="GET", body=None):
    """Make a request to the NEXUS API."""
    url = f"{NEXUS_API}/api/v1{path}"
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"NEXUS API error: {e}")
        return None


def build_response(speech, should_end=True):
    return {
        "version": "1.0",
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": speech,
            },
            "shouldEndSession": should_end,
        },
    }


def handle_trigger_scene(intent):
    slot = intent.get("slots", {}).get("scene", {})
    spoken = (slot.get("value") or "").lower().strip()
    scene_id = SCENE_MAP.get(spoken)

    if not scene_id:
        return build_response(f"Ich kenne die Szene {spoken} nicht.")

    result = nexus_request(f"/scenes/{scene_id}/trigger", method="POST", body={})
    if result and result.get("status") == "ok":
        return build_response(f"Szene {spoken} wurde gestartet.")
    return build_response(f"Fehler beim Starten der Szene {spoken}.")


def handle_device_on(intent):
    slot = intent.get("slots", {}).get("device", {})
    spoken = (slot.get("value") or "").lower().strip()
    device_id = DEVICE_MAP.get(spoken)

    if not device_id:
        return build_response(f"Ich kenne das Gerät {spoken} nicht.")

    result = nexus_request(f"/devices/{device_id}/command", method="POST", body={"command": "on"})
    if result and result.get("status") == "ok":
        return build_response(f"{spoken} wurde eingeschaltet.")
    return build_response(f"Fehler beim Einschalten von {spoken}.")


def handle_device_off(intent):
    slot = intent.get("slots", {}).get("device", {})
    spoken = (slot.get("value") or "").lower().strip()
    device_id = DEVICE_MAP.get(spoken)

    if not device_id:
        return build_response(f"Ich kenne das Gerät {spoken} nicht.")

    result = nexus_request(f"/devices/{device_id}/command", method="POST", body={"command": "off"})
    if result and result.get("status") == "ok":
        return build_response(f"{spoken} wurde ausgeschaltet.")
    return build_response(f"Fehler beim Ausschalten von {spoken}.")


def handle_wake_computer(intent):
    result = nexus_request("/devices/main_pc/command", method="POST", body={"command": "wake"})
    if result and result.get("status") == "ok":
        return build_response("PC wird hochgefahren.")
    return build_response("Fehler beim Aufwecken des PCs.")


def handle_status(intent):
    health = nexus_request("/health")
    if not health:
        return build_response("NEXUS ist nicht erreichbar.")

    devices = nexus_request("/devices") or []
    online = [d for d in devices if d.get("state", {}).get("online")]
    total = len(devices)

    mqtt = "verbunden" if health.get("mqtt_connected") else "nicht verbunden"
    speech = (
        f"NEXUS läuft. {len(online)} von {total} Geräten sind online. "
        f"MQTT ist {mqtt}."
    )
    return build_response(speech)


def handle_energy(intent):
    # Aggregate energy from all plugs with energy monitoring
    devices = nexus_request("/devices") or []
    total_watts = 0
    total_kwh = 0

    for d in devices:
        energy = d.get("state", {}).get("energy", {})
        total_watts += energy.get("power_w", 0)
        total_kwh += energy.get("today_kwh", 0)

    if total_watts == 0 and total_kwh == 0:
        return build_response("Aktuell sind keine Energiedaten verfügbar.")

    speech = f"Aktueller Verbrauch: {total_watts:.0f} Watt. Heute insgesamt: {total_kwh:.1f} Kilowattstunden."
    return build_response(speech)


def handle_all_off(intent):
    result = nexus_request("/scenes/all_off/trigger", method="POST", body={})
    if result and result.get("status") == "ok":
        return build_response("Alles wurde ausgeschaltet.")
    return build_response("Fehler beim Ausschalten.")


def lambda_handler(event, context):
    """Main Lambda entry point for Alexa skill."""
    try:
        request_type = event.get("request", {}).get("type", "")

        if request_type == "LaunchRequest":
            return build_response("NEXUS bereit. Was soll ich tun?", should_end=False)

        if request_type == "IntentRequest":
            intent = event["request"]["intent"]
            intent_name = intent["name"]

            handlers = {
                "TriggerSceneIntent": handle_trigger_scene,
                "DeviceOnIntent": handle_device_on,
                "DeviceOffIntent": handle_device_off,
                "WakeComputerIntent": handle_wake_computer,
                "StatusIntent": handle_status,
                "EnergyIntent": handle_energy,
                "AllOffIntent": handle_all_off,
                "AMAZON.HelpIntent": lambda _: build_response(
                    "Du kannst Szenen starten, Geräte steuern oder den Status abfragen. "
                    "Sage zum Beispiel: Programmier Modus, oder: PC hochfahren.",
                    should_end=False,
                ),
                "AMAZON.StopIntent": lambda _: build_response("Bis später."),
                "AMAZON.CancelIntent": lambda _: build_response("Abgebrochen."),
            }

            handler = handlers.get(intent_name)
            if handler:
                return handler(intent)

            return build_response("Das habe ich nicht verstanden.")

        if request_type == "SessionEndedRequest":
            return build_response("")

        return build_response("Etwas ist schiefgelaufen.")

    except Exception as e:
        print(f"Lambda error: {e}")
        return build_response("Es gab einen Fehler bei der Verarbeitung.")
