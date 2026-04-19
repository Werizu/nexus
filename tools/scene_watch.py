#!/usr/bin/env python3
"""NEXUS Scene Watch — Live scene execution progress with brew-style spinners."""

import argparse
import asyncio
import json
import sys
import time
import urllib.request
import urllib.error

try:
    import websockets
except ImportError:
    print("Fehler: 'websockets' nicht installiert. Nutze die NEXUS venv:")
    print("  source /Users/marlonheck/Desktop/nexus/.venv/bin/activate")
    sys.exit(1)

# ─── Config ──────────────────────────────────────────────
BRAIN_URL = "http://192.168.178.202:8000"
WS_URL = "ws://192.168.178.202:8000/ws/realtime"
API_BASE = f"{BRAIN_URL}/api/v1"

# ─── ANSI Colors ─────────────────────────────────────────
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"
CLEAR_LINE = "\033[2K\r"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

SPINNER_CHARS = ["◐", "◓", "◑", "◒"]

# ─── Action name translations ───────────────────────────
ACTION_LABELS = {
    "plug.on": "Steckdose ein",
    "plug.off": "Steckdose aus",
    "light.on": "Licht ein",
    "light.off": "Licht aus",
    "light.focus": "Licht Focus-Modus",
    "light.relax": "Licht Relax-Modus",
    "light.bright": "Licht hell",
    "light.dim": "Licht gedimmt",
    "light.set": "Licht einstellen",
    "pc.wake": "PC aufwecken",
    "pc.shutdown": "PC herunterfahren",
    "pc.sleep": "PC Standby",
    "pc.rdp_connect": "Remote Desktop",
    "pc.ssh_run": "SSH Befehl",
    "pc.open_url": "URL oeffnen",
    "mac.connect_vnc": "VNC verbinden",
    "pi.reboot": "Pi neustarten",
    "pi.shutdown": "Pi herunterfahren",
    "jarvis.speak": "Jarvis spricht",
    "wait": "Warte",
}


def action_label(action: dict) -> str:
    """Generate a human-readable German label for a scene action."""
    act = action.get("action", "")
    device = action.get("device", "")

    base = ACTION_LABELS.get(act, act)

    if act == "wait":
        secs = action.get("seconds", 0)
        unit = "Sekunde" if secs == 1 else "Sekunden"
        return f"Warte {secs} {unit}"

    if act == "pc.wake" and action.get("wait_until_online"):
        timeout = action.get("timeout", 60)
        return f"{base} ({device}) \u2014 Warte bis online ({timeout}s timeout)"

    if act == "pc.rdp_connect":
        host = action.get("host", "")
        return f"{base} ({device})" + (f" \u2192 {host}" if host else "")

    if act == "pc.open_url":
        url = action.get("url", "")
        return f"{base} ({device})" + (f" \u2192 {url}" if url else "")

    if device:
        return f"{base} ({device})"

    return base


def group_consecutive_actions(actions: list[dict]) -> list[dict]:
    """Group consecutive identical actions (e.g., multiple light.focus) into one display line."""
    grouped = []
    i = 0
    while i < len(actions):
        act = actions[i]
        act_type = act.get("action", "")

        # Check for consecutive same-type actions
        j = i + 1
        while j < len(actions) and actions[j].get("action") == act_type:
            j += 1

        count = j - i
        if count > 1 and act_type != "wait":
            devices = [actions[k].get("device", "") for k in range(i, j)]
            base = ACTION_LABELS.get(act_type, act_type)
            label = f"{base} ({', '.join(devices)})"
            grouped.append({
                "_label": label,
                "_step_indices": list(range(i, j)),
                "_count": count,
            })
        else:
            grouped.append({
                **act,
                "_label": action_label(act),
                "_step_indices": [i],
                "_count": 1,
            })
        i = j

    return grouped


# ─── API helpers ─────────────────────────────────────────
def api_get(path: str) -> dict:
    """GET request to NEXUS Brain API."""
    req = urllib.request.Request(f"{API_BASE}{path}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"\n{RED}Fehler:{RESET} Brain nicht erreichbar: {e}")
        sys.exit(1)


def api_post(path: str, body: dict | None = None) -> dict:
    """POST request to NEXUS Brain API."""
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"\n{RED}Fehler:{RESET} API-Aufruf fehlgeschlagen: {e}")
        sys.exit(1)


# ─── Display ─────────────────────────────────────────────
class SceneDisplay:
    def __init__(self, scene_name: str, display_name: str, grouped_actions: list[dict]):
        self.scene_name = scene_name
        self.display_name = display_name
        self.groups = grouped_actions
        self.total_groups = len(grouped_actions)

        # State for each display group: "pending" | "running" | "completed" | "failed"
        self.states = ["pending"] * self.total_groups
        self.spinner_idx = 0
        self.start_time = time.time()
        self._printed_header = False

    def _render_line(self, idx: int) -> str:
        """Render a single line for a grouped action."""
        state = self.states[idx]
        label = self.groups[idx]["_label"]

        if state == "completed":
            return f"  {GREEN}\u2713 {label}{RESET}"
        elif state == "running":
            ch = SPINNER_CHARS[self.spinner_idx % len(SPINNER_CHARS)]
            return f"  {YELLOW}{ch} {label}{RESET}"
        elif state == "failed":
            return f"  {RED}\u2717 {label}{RESET}"
        else:  # pending
            return f"  {DIM}  {label}{RESET}"

    def render(self) -> str:
        """Full render of the scene progress."""
        lines = []
        if not self._printed_header:
            lines.append("")
            lines.append(f"\U0001F680 {BOLD}Szene: {self.display_name}{RESET}")
            lines.append("")
            self._printed_header = True

        for i in range(self.total_groups):
            lines.append(self._render_line(i))

        return "\n".join(lines)

    def set_state(self, group_idx: int, state: str):
        if 0 <= group_idx < self.total_groups:
            self.states[group_idx] = state

    def step_to_group(self, step_index: int) -> int | None:
        """Map a flat step index to a display group index."""
        for gi, group in enumerate(self.groups):
            if step_index in group["_step_indices"]:
                return gi
        return None

    def advance_spinner(self):
        self.spinner_idx += 1

    def elapsed(self) -> float:
        return time.time() - self.start_time

    def all_done(self) -> bool:
        return all(s in ("completed", "failed") for s in self.states)


def draw(display: SceneDisplay):
    """Redraw the entire display (moves cursor up to overwrite)."""
    # Move up to overwrite previous render (header=3 lines + groups)
    total_lines = display.total_groups
    sys.stdout.write(f"\033[{total_lines}A")
    for i in range(display.total_groups):
        sys.stdout.write(CLEAR_LINE + display._render_line(i) + "\n")
    sys.stdout.flush()


async def watch_with_websocket(display: SceneDisplay, scene_name: str, trigger: bool):
    """Try to use WebSocket for live updates. Returns True if it worked."""
    try:
        async with websockets.connect(WS_URL, open_timeout=3) as ws:
            # Print initial display
            print(display.render())

            if trigger:
                # Trigger scene in background — the POST will block until completion,
                # but we get WS events during execution
                loop = asyncio.get_event_loop()
                trigger_task = loop.run_in_executor(
                    None, api_post, f"/scenes/{scene_name}/trigger"
                )
            else:
                trigger_task = None

            current_group = -1
            ws_got_events = False

            while not display.all_done():
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=0.15)
                    msg = json.loads(raw)
                    event = msg.get("event") or msg.get("type", "")

                    if msg.get("scene") != scene_name and scene_name not in str(msg):
                        continue

                    ws_got_events = True

                    if event in ("scene_start", "scene_started"):
                        pass  # Already showing

                    elif event in ("scene_step",):
                        step = msg.get("step", 0)
                        status = msg.get("status", "")
                        step_idx = step - 1  # 0-based

                        gi = display.step_to_group(step_idx)
                        if gi is not None:
                            if status == "running":
                                display.set_state(gi, "running")
                            elif status == "completed":
                                display.set_state(gi, "completed")
                                # Start next group if exists
                                if gi + 1 < display.total_groups:
                                    display.set_state(gi + 1, "running")
                            elif status == "failed":
                                display.set_state(gi, "failed")

                    elif event in ("scene_complete", "scene_completed"):
                        result = msg.get("result", {})
                        steps = result.get("steps", [])
                        # Mark all remaining as completed based on result
                        for step_result in steps:
                            si = step_result.get("step", 0) - 1
                            gi = display.step_to_group(si)
                            if gi is not None:
                                if "error" in step_result and step_result["error"]:
                                    display.set_state(gi, "failed")
                                else:
                                    display.set_state(gi, "completed")
                        # Fill any remaining pending as completed
                        for gi in range(display.total_groups):
                            if display.states[gi] == "pending":
                                display.set_state(gi, "completed")
                        draw(display)
                        break

                except asyncio.TimeoutError:
                    pass

                display.advance_spinner()
                draw(display)

                # Check if trigger POST returned (fallback — scene_complete might not come via WS)
                if trigger_task and trigger_task.done():
                    try:
                        result = trigger_task.result()
                        if not ws_got_events:
                            # WS gave us nothing — mark all done from API result
                            return False
                        # API returned but WS already handled it
                        steps = result.get("result", {}).get("steps", [])
                        for step_result in steps:
                            si = step_result.get("step", 0) - 1
                            gi = display.step_to_group(si)
                            if gi is not None:
                                if "error" in step_result and step_result["error"]:
                                    display.set_state(gi, "failed")
                                else:
                                    display.set_state(gi, "completed")
                        for gi in range(display.total_groups):
                            if display.states[gi] in ("pending", "running"):
                                display.set_state(gi, "completed")
                        draw(display)
                        break
                    except Exception:
                        pass

            if trigger_task and not trigger_task.done():
                await trigger_task

            return True

    except (OSError, websockets.exceptions.WebSocketException, asyncio.TimeoutError):
        return False


async def watch_with_polling(display: SceneDisplay, scene_name: str, trigger: bool):
    """Fallback: trigger via API POST (blocking) and animate optimistically."""
    print(display.render())

    if not trigger:
        # Watch-only mode without WebSocket — poll logs
        print(f"\n{DIM}(WebSocket nicht verfuegbar, beobachte Logs...){RESET}")
        last_log_check = time.time()

        while True:
            display.advance_spinner()
            draw(display)
            await asyncio.sleep(0.12)

            # Poll logs every 2 seconds
            if time.time() - last_log_check > 2:
                last_log_check = time.time()
                try:
                    logs = api_get(f"/logs?limit=5")
                    for log in (logs if isinstance(logs, list) else []):
                        msg = log.get("message", "")
                        if f"'{scene_name}' completed" in msg or f"'{scene_name}' started" in msg:
                            # Scene completed
                            for gi in range(display.total_groups):
                                display.set_state(gi, "completed")
                            draw(display)
                            return
                except Exception:
                    pass
        return

    # Trigger mode: run POST in background thread while animating
    loop = asyncio.get_event_loop()

    # Track step progress via estimated timing
    total_steps = display.total_groups
    if total_steps > 0:
        display.set_state(0, "running")
        draw(display)

    trigger_done = asyncio.Event()
    trigger_result = {}

    def do_trigger():
        result = api_post(f"/scenes/{scene_name}/trigger")
        trigger_result.update(result)
        loop.call_soon_threadsafe(trigger_done.set)

    loop.run_in_executor(None, do_trigger)

    # Animate while waiting for the POST to return
    while not trigger_done.is_set():
        display.advance_spinner()
        draw(display)
        await asyncio.sleep(0.12)

    # POST returned — parse results and mark steps
    result = trigger_result.get("result", {})
    steps = result.get("steps", [])

    for step_result in steps:
        si = step_result.get("step", 0) - 1
        gi = display.step_to_group(si)
        if gi is not None:
            if step_result.get("error"):
                display.set_state(gi, "failed")
            else:
                display.set_state(gi, "completed")

    # Fill any remaining
    for gi in range(display.total_groups):
        if display.states[gi] in ("pending", "running"):
            display.set_state(gi, "completed")

    draw(display)


async def run(scene_name: str, trigger: bool):
    # Fetch scene definition
    scene = api_get(f"/scenes/{scene_name}")
    if "detail" in scene:
        print(f"{RED}Fehler:{RESET} Szene '{scene_name}' nicht gefunden.")
        sys.exit(1)

    display_name = scene.get("display_name", scene.get("name", scene_name))
    actions = scene.get("actions", [])

    if not actions:
        print(f"{YELLOW}Szene '{display_name}' hat keine Aktionen.{RESET}")
        return

    grouped = group_consecutive_actions(actions)
    display = SceneDisplay(scene_name, display_name, grouped)

    sys.stdout.write(HIDE_CURSOR)
    try:
        if trigger:
            # Try WebSocket first, fall back to polling
            ws_ok = await watch_with_websocket(display, scene_name, trigger=True)
            if not ws_ok:
                # Reset display for polling fallback
                display = SceneDisplay(scene_name, display_name, grouped)
                await watch_with_polling(display, scene_name, trigger=True)
        else:
            # Watch mode — WebSocket only path makes sense, poll as fallback
            ws_ok = await watch_with_websocket(display, scene_name, trigger=False)
            if not ws_ok:
                display = SceneDisplay(scene_name, display_name, grouped)
                await watch_with_polling(display, scene_name, trigger=False)

        # Summary
        elapsed = display.elapsed()
        failed = display.states.count("failed")
        completed = display.states.count("completed")

        print()
        if failed:
            print(f"{RED}\u2717 {failed} Fehler{RESET} | {completed} ok | {elapsed:.1f}s")
        else:
            print(f"{GREEN}\u2713 Fertig{RESET} in {elapsed:.1f}s")

    finally:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(
        description="NEXUS Scene Watch - Live-Fortschritt fuer Szenen",
        usage="%(prog)s [--watch] SCENE_NAME",
    )
    parser.add_argument("scene", help="Name der Szene (z.B. dev_mode)")
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Nur beobachten, Szene nicht ausloesen",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Brain-Host ueberschreiben (z.B. localhost:8000)",
    )

    args = parser.parse_args()

    if args.host:
        global BRAIN_URL, WS_URL, API_BASE
        BRAIN_URL = f"http://{args.host}"
        WS_URL = f"ws://{args.host}/ws/realtime"
        API_BASE = f"{BRAIN_URL}/api/v1"

    trigger = not args.watch

    try:
        asyncio.run(run(args.scene, trigger))
    except KeyboardInterrupt:
        sys.stdout.write(SHOW_CURSOR)
        print(f"\n{DIM}Abgebrochen.{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
