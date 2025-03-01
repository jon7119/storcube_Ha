"""Support for Storcube Battery Monitor sensors."""
from __future__ import annotations

import logging
import json
import asyncio
import requests
import paho.mqtt.client as mqtt
import websockets
from datetime import datetime
from typing import Any

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
    UnitOfEnergy,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTemperature,
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
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    config = config_entry.data

    sensors = [
        StorcubeBatteryLevelSensor(config),
        StorcubeBatteryPowerSensor(config),
        StorcubeBatteryVoltageSensor(config),
        StorcubeBatteryCurrentSensor(config),
        StorcubeBatteryTemperatureSensor(config),
    ]

    async_add_entities(sensors)

    # Start websocket connection
    asyncio.create_task(websocket_to_mqtt(hass, config))

class StorcubeBatteryLevelSensor(SensorEntity):
    """Représentation du niveau de batterie."""

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

class StorcubeBatteryPowerSensor(SensorEntity):
    """Représentation de la puissance de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Puissance Batterie Storcube"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_power"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("battery_power")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery power: %s", e)

class StorcubeBatteryVoltageSensor(SensorEntity):
    """Représentation de la tension de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Tension Batterie Storcube"
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_voltage"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("battery_voltage")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery voltage: %s", e)

class StorcubeBatteryCurrentSensor(SensorEntity):
    """Représentation du courant de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Courant Batterie Storcube"
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_device_class = SensorDeviceClass.CURRENT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_current"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("battery_current")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery current: %s", e)

class StorcubeBatteryTemperatureSensor(SensorEntity):
    """Représentation de la température de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Température Batterie Storcube"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_temperature"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("battery_temperature")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery temperature: %s", e)

async def websocket_to_mqtt(hass: HomeAssistant, config: ConfigType) -> None:
    """Handle websocket connection and forward data to MQTT."""
    mqtt_client = mqtt.Client()
    mqtt_client.username_pw_set(config[CONF_USERNAME], config[CONF_PASSWORD])
    mqtt_client.connect(config[CONF_HOST], config[CONF_PORT])
    mqtt_client.loop_start()

    while True:
        try:
            response = requests.post(
                TOKEN_URL,
                json={
                    "appCode": config[CONF_APP_CODE],
                    "loginName": config[CONF_LOGIN_NAME],
                    "password": config[CONF_AUTH_PASSWORD],
                },
            )
            token_data = response.json()
            if token_data.get("code") != 200:
                raise Exception("Failed to get token")
            token = token_data["data"]["token"]

            uri = f"{WS_URI}{config[CONF_DEVICE_ID]}"
            async with websockets.connect(uri) as websocket:
                _LOGGER.info("Connected to websocket")

                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)

                        mqtt_client.publish(
                            TOPIC_BATTERY,
                            json.dumps(data),
                            qos=0,
                            retain=False,
                        )

                    except websockets.ConnectionClosed:
                        break

        except Exception as e:
            _LOGGER.error("Error in websocket connection: %s", e)
            await asyncio.sleep(30)  # Wait before retrying 