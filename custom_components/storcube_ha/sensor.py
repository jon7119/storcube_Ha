"""Support for Storcube Battery Monitor sensors."""
from __future__ import annotations

import logging
import json
import asyncio
import websockets
from datetime import datetime
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    PERCENTAGE,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    DOMAIN,
    NAME,
    CONF_DEVICE_ID,
    CONF_APP_CODE,
    CONF_LOGIN_NAME,
    CONF_AUTH_PASSWORD,
    WS_URI,
    TOKEN_URL,
    TOPIC_BATTERY,
    TOPIC_OUTPUT,
    TOPIC_FIRMWARE,
    TOPIC_POWER,
    TOPIC_OUTPUT_POWER,
    TOPIC_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    config = config_entry.data

    # Create battery sensors
    sensors = [
        StorcubeBatteryLevelSensor(config),
        StorcubePowerSensor(config),
        StorcubeThresholdSensor(config),
    ]

    async_add_entities(sensors)

    # Start websocket connection
    asyncio.create_task(websocket_to_mqtt(hass, config))

class StorcubeBatteryLevelSensor(SensorEntity):
    """Representation of a Storcube Battery Level Sensor."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Niveau Batterie Storcube"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_level"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("battery_level")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery level: %s", e)

class StorcubePowerSensor(SensorEntity):
    """Representation of a Storcube Power Sensor."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Puissance Storcube"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_power"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("power")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating power: %s", e)

class StorcubeThresholdSensor(SensorEntity):
    """Representation of a Storcube Threshold Sensor."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Seuil Batterie Storcube"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_threshold"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("threshold")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating threshold: %s", e)

async def websocket_to_mqtt(hass: HomeAssistant, config: ConfigType) -> None:
    """Handle websocket connection and forward data to MQTT."""
    while True:
        try:
            # Get authentication token
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TOKEN_URL,
                    json={
                        "appCode": config[CONF_APP_CODE],
                        "loginName": config[CONF_LOGIN_NAME],
                        "password": config[CONF_AUTH_PASSWORD],
                    },
                ) as response:
                    token_data = await response.json()
                    if token_data.get("code") != 200:
                        raise Exception("Failed to get token")
                    token = token_data["data"]["token"]

            # Connect to websocket
            uri = f"{WS_URI}{config[CONF_DEVICE_ID]}"
            async with websockets.connect(uri) as websocket:
                _LOGGER.info("Connected to websocket")

                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)

                        # Publish to MQTT
                        await mqtt.async_publish(
                            hass,
                            TOPIC_BATTERY,
                            json.dumps(data),
                            config[CONF_PORT],
                            False,
                        )

                    except websockets.ConnectionClosed:
                        break

        except Exception as e:
            _LOGGER.error("Error in websocket connection: %s", e)
            await asyncio.sleep(30)  # Wait before retrying 