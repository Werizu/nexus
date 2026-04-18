"""NEXUS Scheduler — time-based scene triggers."""

import asyncio
import logging
from datetime import datetime, time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.scene_engine import SceneEngine

logger = logging.getLogger("nexus.scheduler")


class Scheduler:
    def __init__(self, scene_engine: "SceneEngine"):
        self.scene_engine = scene_engine
        self._task: asyncio.Task | None = None
        self._schedules: list[dict] = []

    async def start(self):
        """Start the scheduler loop."""
        self._load_schedules()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Scheduler started with {len(self._schedules)} scheduled triggers")

    def _load_schedules(self):
        """Extract time-based triggers from all loaded scenes."""
        self._schedules = []
        for scene_name, scene in self.scene_engine.scenes.items():
            for trigger in scene.get("triggers", []):
                if trigger.get("type") == "schedule":
                    self._schedules.append({
                        "scene": scene_name,
                        "time": trigger.get("time"),
                        "days": trigger.get("days", ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]),
                        "last_run": None,
                    })

    async def _run_loop(self):
        """Check every 30 seconds if any scheduled scene should trigger."""
        while True:
            now = datetime.now()
            current_time = now.strftime("%H:%M")
            current_day = now.strftime("%a").lower()

            for schedule in self._schedules:
                if (schedule["time"] == current_time
                        and current_day in schedule["days"]
                        and schedule["last_run"] != current_time):
                    schedule["last_run"] = current_time
                    scene_name = schedule["scene"]
                    logger.info(f"Scheduled trigger: {scene_name} at {current_time}")
                    asyncio.create_task(self.scene_engine.execute(scene_name))

            await asyncio.sleep(30)

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
