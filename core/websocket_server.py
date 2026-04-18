"""NEXUS WebSocket Manager — realtime updates to dashboard and clients."""

import json
import logging
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

logger = logging.getLogger("nexus.ws")


class WebSocketManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    def mount(self, app: FastAPI):
        @app.websocket("/ws/realtime")
        async def websocket_endpoint(ws: WebSocket):
            await self.connect(ws)
            try:
                while True:
                    # Keep connection alive, handle incoming messages
                    data = await ws.receive_text()
                    try:
                        msg = json.loads(data)
                        logger.debug(f"WS received: {msg}")
                    except json.JSONDecodeError:
                        pass
            except WebSocketDisconnect:
                self.disconnect(ws)

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)
        logger.info(f"WebSocket client connected ({len(self.active_connections)} total)")

    def disconnect(self, ws: WebSocket):
        if ws in self.active_connections:
            self.active_connections.remove(ws)
        logger.info(f"WebSocket client disconnected ({len(self.active_connections)} total)")

    async def broadcast(self, data: dict[str, Any]):
        """Send event to all connected WebSocket clients."""
        message = json.dumps(data)
        disconnected = []
        for ws in self.active_connections:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)
