"""NEXUS State Store — SQLite-backed device state and log storage."""

import json
import logging
import time
from pathlib import Path

import aiosqlite

logger = logging.getLogger("nexus.state")


class StateStore:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db: aiosqlite.Connection | None = None
        self.device_count = 0

    async def initialize(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = await aiosqlite.connect(str(self.db_path))
        self.db.row_factory = aiosqlite.Row

        await self.db.executescript("""
            CREATE TABLE IF NOT EXISTS device_state (
                device_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                plugin TEXT NOT NULL,
                room TEXT,
                state TEXT DEFAULT '{}',
                last_seen REAL,
                config TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                level TEXT NOT NULL DEFAULT 'info',
                device TEXT,
                message TEXT NOT NULL,
                data TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                device_id TEXT NOT NULL,
                type TEXT NOT NULL,
                value REAL,
                threshold REAL,
                message TEXT NOT NULL,
                severity TEXT DEFAULT 'warning',
                acknowledged INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_logs_device ON logs(device);
            CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_alerts_device ON alerts(device_id);
        """)
        await self.db.commit()

        cursor = await self.db.execute("SELECT COUNT(*) FROM device_state")
        row = await cursor.fetchone()
        self.device_count = row[0]
        logger.info(f"State store initialized with {self.device_count} devices")

    async def register_device(self, device_id: str, category: str, name: str,
                              plugin: str, room: str | None, device_config: dict):
        await self.db.execute(
            """INSERT INTO device_state (device_id, category, name, plugin, room, config, last_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(device_id) DO UPDATE SET
                 name=excluded.name, plugin=excluded.plugin,
                 room=excluded.room, config=excluded.config""",
            (device_id, category, name, plugin, room, json.dumps(device_config), time.time())
        )
        await self.db.commit()
        cursor = await self.db.execute("SELECT COUNT(*) FROM device_state")
        row = await cursor.fetchone()
        self.device_count = row[0]

    async def update_device(self, device_id: str, state: dict):
        await self.db.execute(
            "UPDATE device_state SET state = ?, last_seen = ? WHERE device_id = ?",
            (json.dumps(state), time.time(), device_id)
        )
        await self.db.commit()

    async def get_device(self, device_id: str) -> dict | None:
        cursor = await self.db.execute("SELECT * FROM device_state WHERE device_id = ?", (device_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_device(row)

    async def get_all_devices(self) -> list[dict]:
        cursor = await self.db.execute("SELECT * FROM device_state ORDER BY category, name")
        rows = await cursor.fetchall()
        return [self._row_to_device(r) for r in rows]

    def _row_to_device(self, row) -> dict:
        return {
            "device_id": row["device_id"],
            "category": row["category"],
            "name": row["name"],
            "plugin": row["plugin"],
            "room": row["room"],
            "state": json.loads(row["state"]),
            "last_seen": row["last_seen"],
            "config": json.loads(row["config"]),
        }

    # ─── Logs ───
    async def add_log(self, level: str, message: str, device: str | None = None, data: dict | None = None):
        await self.db.execute(
            "INSERT INTO logs (timestamp, level, device, message, data) VALUES (?, ?, ?, ?, ?)",
            (time.time(), level, device, message, json.dumps(data or {}))
        )
        await self.db.commit()

    async def get_logs(self, level: str = "info", device: str | None = None, limit: int = 100) -> list[dict]:
        levels = {"debug": 0, "info": 1, "warning": 2, "error": 3}
        min_level = levels.get(level, 1)
        allowed = [l for l, v in levels.items() if v >= min_level]
        placeholders = ",".join("?" for _ in allowed)

        query = f"SELECT * FROM logs WHERE level IN ({placeholders})"
        params: list = list(allowed)

        if device:
            query += " AND device = ?"
            params.append(device)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = await self.db.execute(query, params)
        rows = await cursor.fetchall()
        return [
            {
                "id": r["id"],
                "timestamp": r["timestamp"],
                "level": r["level"],
                "device": r["device"],
                "message": r["message"],
                "data": json.loads(r["data"]),
            }
            for r in rows
        ]

    # ─── Alerts ───
    async def add_alert(self, device_id: str, alert: dict):
        await self.db.execute(
            "INSERT INTO alerts (timestamp, device_id, type, value, threshold, message, severity) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (alert.get("timestamp", time.time()), device_id, alert["type"],
             alert.get("value"), alert.get("threshold"), alert["message"],
             alert.get("severity", "warning"))
        )
        await self.db.commit()

    async def get_alerts(self, device_id: str | None = None, limit: int = 50, unacked_only: bool = False) -> list[dict]:
        query = "SELECT * FROM alerts WHERE 1=1"
        params: list = []
        if device_id:
            query += " AND device_id = ?"
            params.append(device_id)
        if unacked_only:
            query += " AND acknowledged = 0"
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        cursor = await self.db.execute(query, params)
        rows = await cursor.fetchall()
        return [
            {
                "id": r["id"], "timestamp": r["timestamp"], "device_id": r["device_id"],
                "type": r["type"], "value": r["value"], "threshold": r["threshold"],
                "message": r["message"], "severity": r["severity"], "acknowledged": bool(r["acknowledged"]),
            }
            for r in rows
        ]

    async def acknowledge_alert(self, alert_id: int):
        await self.db.execute("UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))
        await self.db.commit()

    async def acknowledge_all_alerts(self):
        await self.db.execute("UPDATE alerts SET acknowledged = 1 WHERE acknowledged = 0")
        await self.db.commit()

    async def close(self):
        if self.db:
            await self.db.close()
