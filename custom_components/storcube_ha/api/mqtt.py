"""MQTT client for Storcube Battery Monitor integration."""
from __future__ import annotations

import logging
import json
import asyncio
from typing import Any, Callable, Dict, Optional

import paho.mqtt.client as mqtt
from homeassistant.components import mqtt as hass_mqtt
from homeassistant.core import HomeAssistant

from ..const import (
    MQTT_TOPIC_PREFIX,
    MQTT_TOPIC_STATUS,
    MQTT_TOPIC_POWER,
    MQTT_TOPIC_SOLAR,
)

_LOGGER = logging.getLogger(__name__)

class StorcubeMqttClient:
    """MQTT client for Storcube Battery Monitor."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        username: str,
        password: str,
        callback: Callable[[Dict[str, Any]], None],
    ) -> None:
        """Initialize the MQTT client."""
        self._hass = hass
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._callback = callback
        self._client = None
        self._running = False

    async def async_connect(self) -> None:
        """Connect to the MQTT broker."""
        if self._client:
            return

        try:
            self._client = mqtt.Client()
            self._client.username_pw_set(self._username, self._password)
            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message
            self._client.on_disconnect = self._on_disconnect

            self._client.connect(self._host, self._port)
            self._client.loop_start()
            self._running = True
            _LOGGER.info("Connected to MQTT broker")
        except Exception as e:
            _LOGGER.error("Failed to connect to MQTT broker: %s", str(e))
            raise

    async def async_disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        self._running = False
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
            _LOGGER.info("Disconnected from MQTT broker")

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Dict[str, Any], rc: int) -> None:
        """Handle MQTT connection."""
        if rc == 0:
            _LOGGER.info("Connected to MQTT broker")
            # Subscribe to topics
            client.subscribe(f"{MQTT_TOPIC_PREFIX}/#")
        else:
            _LOGGER.error("Failed to connect to MQTT broker with code %d", rc)

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        """Handle MQTT message."""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            if topic.startswith(MQTT_TOPIC_PREFIX):
                self._callback({
                    "topic": topic,
                    "payload": payload,
                })
        except json.JSONDecodeError:
            _LOGGER.error("Failed to decode MQTT message: %s", msg.payload)
        except Exception as e:
            _LOGGER.error("Error handling MQTT message: %s", str(e))

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int) -> None:
        """Handle MQTT disconnection."""
        if rc != 0:
            _LOGGER.warning("Disconnected from MQTT broker with code %d", rc)
            if self._running:
                asyncio.create_task(self._async_reconnect())

    async def _async_reconnect(self) -> None:
        """Reconnect to the MQTT broker."""
        await asyncio.sleep(5)
        try:
            await self.async_connect()
        except Exception as e:
            _LOGGER.error("Failed to reconnect to MQTT broker: %s", str(e))
            await asyncio.sleep(30)

    async def async_publish(self, topic: str, payload: Dict[str, Any]) -> None:
        """Publish a message to the MQTT broker."""
        if not self._client:
            raise Exception("MQTT client not connected")

        try:
            self._client.publish(topic, json.dumps(payload))
        except Exception as e:
            _LOGGER.error("Failed to publish MQTT message: %s", str(e))
            raise 