"""Sensor entity for Storcube Battery Monitor integration."""
from __future__ import annotations

import logging
from typing import Any, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    POWER_WATT,
    ELECTRIC_POTENTIAL_VOLT,
    ELECTRIC_CURRENT_AMPERE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import StorcubeBaseEntity
from ..core.coordinator import StorcubeDataUpdateCoordinator
from ..const import (
    DOMAIN,
    SENSOR_TYPES,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Storcube Battery Monitor sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    for equip_id in coordinator.data.get("rest_api", {}):
        for sensor_type in SENSOR_TYPES:
            entities.append(
                StorcubeSensor(
                    coordinator,
                    config_entry,
                    equip_id,
                    sensor_type,
                )
            )
    
    async_add_entities(entities)

class StorcubeSensor(StorcubeBaseEntity, SensorEntity):
    """Representation of a Storcube Battery Monitor sensor."""

    def __init__(
        self,
        coordinator: StorcubeDataUpdateCoordinator,
        config_entry: ConfigEntry,
        equip_id: str,
        sensor_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, equip_id)
        self._sensor_type = sensor_type
        self._attr_name = f"{MANUFACTURER} {SENSOR_TYPES[sensor_type]['name']} {equip_id}"
        self._attr_unique_id = f"{equip_id}_{sensor_type}"
        self._attr_device_class = SENSOR_TYPES[sensor_type]["device_class"]
        self._attr_state_class = SENSOR_TYPES[sensor_type]["state_class"]
        self._attr_native_unit_of_measurement = SENSOR_TYPES[sensor_type]["unit_of_measurement"]
        self._attr_icon = SENSOR_TYPES[sensor_type]["icon"]

    @property
    def native_value(self) -> Optional[Any]:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        websocket_data = self.coordinator.data.get("websocket", {}).get(self._equip_id, {})
        rest_data = self.coordinator.data.get("rest_api", {}).get(self._equip_id, {})

        if self._sensor_type == "battery_level":
            return websocket_data.get("batteryLevel")
        elif self._sensor_type == "power":
            return websocket_data.get("power")
        elif self._sensor_type == "voltage":
            return websocket_data.get("voltage")
        elif self._sensor_type == "current":
            return websocket_data.get("current")
        elif self._sensor_type == "temperature":
            return websocket_data.get("temperature")

        return None 