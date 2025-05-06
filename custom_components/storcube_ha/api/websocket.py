"""WebSocket client for Storcube Battery Monitor integration."""
from __future__ import annotations

import logging
import json
import asyncio
import websockets
from typing import Any, Callable, Dict, Optional

from ..const import WS_URI

_LOGGER = logging.getLogger(__name__)

class StorcubeWebSocketClient:
    """WebSocket client for Storcube Battery Monitor."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        callback: Callable[[Dict[str, Any]], None],
    ) -> None:
        """Initialize the WebSocket client."""
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._callback = callback
        self._ws = None
        self._running = False
        self._last_heartbeat = None

    async def async_connect(self) -> None:
        """Connect to the WebSocket server."""
        if self._ws:
            return

        uri = f"{WS_URI}{self._username}/{self._password}"
        try:
            self._ws = await websockets.connect(uri)
            self._running = True
            asyncio.create_task(self._async_receive())
            _LOGGER.info("Connected to WebSocket server")
        except Exception as e:
            _LOGGER.error("Failed to connect to WebSocket server: %s", str(e))
            raise

    async def async_disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
            _LOGGER.info("Disconnected from WebSocket server")

    async def _async_receive(self) -> None:
        """Receive messages from the WebSocket server."""
        while self._running:
            try:
                if not self._ws:
                    await asyncio.sleep(1)
                    continue

                message = await self._ws.recv()
                if not message:
                    continue

                try:
                    data = json.loads(message)
                    if isinstance(data, dict):
                        self._callback(data)
                except json.JSONDecodeError:
                    _LOGGER.error("Failed to decode WebSocket message: %s", message)
                    continue

            except websockets.exceptions.ConnectionClosed:
                _LOGGER.warning("WebSocket connection closed")
                self._ws = None
                await asyncio.sleep(5)
                try:
                    await self.async_connect()
                except Exception as e:
                    _LOGGER.error("Failed to reconnect to WebSocket server: %s", str(e))
                    await asyncio.sleep(30)
            except Exception as e:
                _LOGGER.error("Error in WebSocket receive loop: %s", str(e))
                await asyncio.sleep(5)

    async def async_send(self, message: Dict[str, Any]) -> None:
        """Send a message to the WebSocket server."""
        if not self._ws:
            raise Exception("WebSocket not connected")

        try:
            await self._ws.send(json.dumps(message))
        except Exception as e:
            _LOGGER.error("Failed to send WebSocket message: %s", str(e))
            raise 