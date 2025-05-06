"""Data coordinator for Storcube Battery Monitor integration."""
from __future__ import annotations

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from ..api.rest import StorcubeRestClient
from ..api.websocket import StorcubeWebSocketClient
from ..api.mqtt import StorcubeMqttClient
from ..const import (
    DOMAIN,
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_APP_CODE,
    CONF_LOGIN_NAME,
    CONF_AUTH_PASSWORD,
    CONF_DEVICE_ID,
)

_LOGGER = logging.getLogger(__name__)

class StorcubeDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Storcube data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Storcube Battery Monitor",
            update_interval=timedelta(seconds=30),
        )
        self._config_entry = config_entry
        self._rest_client = None
        self._ws_client = None
        self._mqtt_client = None
        self.data = {
            "rest_api": {},
            "websocket": {},
            "mqtt": {},
            "last_rest_update": None,
            "last_ws_update": None,
            "last_mqtt_update": None,
        }

    async def async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            # Initialize REST client
            self._rest_client = StorcubeRestClient(
                host=self._config_entry.data[CONF_HOST],
                port=self._config_entry.data[CONF_PORT],
                username=self._config_entry.data[CONF_USERNAME],
                password=self._config_entry.data[CONF_PASSWORD],
                app_code=self._config_entry.data[CONF_APP_CODE],
                login_name=self._config_entry.data[CONF_LOGIN_NAME],
                auth_password=self._config_entry.data[CONF_AUTH_PASSWORD],
            )

            # Initialize WebSocket client
            self._ws_client = StorcubeWebSocketClient(
                host=self._config_entry.data[CONF_HOST],
                port=self._config_entry.data[CONF_PORT],
                username=self._config_entry.data[CONF_USERNAME],
                password=self._config_entry.data[CONF_PASSWORD],
                callback=self._handle_websocket_message,
            )

            # Initialize MQTT client
            self._mqtt_client = StorcubeMqttClient(
                hass=self.hass,
                host=self._config_entry.data[CONF_HOST],
                port=self._config_entry.data[CONF_PORT],
                username=self._config_entry.data[CONF_USERNAME],
                password=self._config_entry.data[CONF_PASSWORD],
                callback=self._handle_mqtt_message,
            )

            # Connect to all services
            await self._rest_client.async_get_token()
            await self._ws_client.async_connect()
            await self._mqtt_client.async_connect()

            # Start background tasks
            asyncio.create_task(self._async_update_rest_data())
            asyncio.create_task(self._async_update_websocket_data())
            asyncio.create_task(self._async_update_mqtt_data())

        except Exception as e:
            _LOGGER.error("Failed to set up coordinator: %s", str(e))
            raise ConfigEntryNotReady from e

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        if self._ws_client:
            await self._ws_client.async_disconnect()
        if self._mqtt_client:
            await self._mqtt_client.async_disconnect()

    async def _async_update_rest_data(self) -> None:
        """Update REST data."""
        while True:
            try:
                output_info = await self._rest_client.async_get_output_info()
                if output_info:
                    equip_id = output_info.get("equipId")
                    if equip_id:
                        if equip_id not in self.data["rest_api"]:
                            self.data["rest_api"][equip_id] = {}
                        
                        self.data["rest_api"][equip_id].update({
                            "output_type": output_info.get("outputType"),
                            "reserved": output_info.get("reserved"),
                            "output_power": output_info.get("outputPower"),
                            "work_status": output_info.get("workStatus"),
                            "rg_online": output_info.get("rgOnline"),
                            "equip_type": output_info.get("equipType"),
                            "main_equip_online": output_info.get("mainEquipOnline"),
                            "equip_model": output_info.get("equipModelCode"),
                            "last_update": output_info.get("createTime")
                        })
                        
                        self.data["last_rest_update"] = datetime.now().isoformat()
                        
                        # Notify listeners
                        self.async_update_listeners()
                        
                        _LOGGER.info("REST data updated for equipment %s", equip_id)
            except Exception as e:
                _LOGGER.error("Error updating REST data: %s", str(e))
            
            await asyncio.sleep(30)

    async def _async_update_websocket_data(self) -> None:
        """Update WebSocket data."""
        while True:
            try:
                if not self._ws_client:
                    await asyncio.sleep(5)
                    continue

                # WebSocket data is updated in the callback
                await asyncio.sleep(1)
            except Exception as e:
                _LOGGER.error("Error updating WebSocket data: %s", str(e))
                await asyncio.sleep(5)

    async def _async_update_mqtt_data(self) -> None:
        """Update MQTT data."""
        while True:
            try:
                if not self._mqtt_client:
                    await asyncio.sleep(5)
                    continue

                # MQTT data is updated in the callback
                await asyncio.sleep(1)
            except Exception as e:
                _LOGGER.error("Error updating MQTT data: %s", str(e))
                await asyncio.sleep(5)

    def _handle_websocket_message(self, message: Dict[str, Any]) -> None:
        """Handle WebSocket message."""
        try:
            equip_data = next(iter(message.values()), {})
            if equip_data and isinstance(equip_data, dict) and "list" in equip_data:
                equip_id = equip_data.get("equipId")
                if equip_id:
                    if equip_id not in self.data["websocket"]:
                        self.data["websocket"][equip_id] = {}
                    
                    self.data["websocket"][equip_id].update(equip_data)
                    self.data["last_ws_update"] = datetime.now().isoformat()
                    
                    # Notify listeners
                    self.async_update_listeners()
                    
                    _LOGGER.info("WebSocket data updated for equipment %s", equip_id)
        except Exception as e:
            _LOGGER.error("Error handling WebSocket message: %s", str(e))

    def _handle_mqtt_message(self, message: Dict[str, Any]) -> None:
        """Handle MQTT message."""
        try:
            topic = message.get("topic", "")
            payload = message.get("payload", {})
            
            if topic.startswith("storcube/"):
                equip_id = topic.split("/")[1]
                if equip_id:
                    if equip_id not in self.data["mqtt"]:
                        self.data["mqtt"][equip_id] = {}
                    
                    self.data["mqtt"][equip_id].update(payload)
                    self.data["last_mqtt_update"] = datetime.now().isoformat()
                    
                    # Notify listeners
                    self.async_update_listeners()
                    
                    _LOGGER.info("MQTT data updated for equipment %s", equip_id)
        except Exception as e:
            _LOGGER.error("Error handling MQTT message: %s", str(e))

    async def async_set_power(self, equip_id: str, power_on: bool) -> None:
        """Set power state."""
        try:
            await self._rest_client.async_set_power(equip_id, power_on)
        except Exception as e:
            _LOGGER.error("Error setting power: %s", str(e))
            raise

    async def async_set_output(self, equip_id: str, output_on: bool) -> None:
        """Set output state."""
        try:
            await self._rest_client.async_set_power(equip_id, output_on)
        except Exception as e:
            _LOGGER.error("Error setting output: %s", str(e))
            raise

    async def async_set_threshold(self, equip_id: str, threshold: int) -> None:
        """Set threshold value."""
        try:
            await self._rest_client.async_set_threshold(equip_id, threshold)
        except Exception as e:
            _LOGGER.error("Error setting threshold: %s", str(e))
            raise 