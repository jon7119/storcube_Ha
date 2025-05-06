"""Binary sensor entity for Storcube Battery Monitor integration."""
from __future__ import annotations

import logging
from typing import Any, Optional

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import StorcubeBaseEntity
from ..core.coordinator import StorcubeDataUpdateCoordinator
from ..const import (
    DOMAIN,
    BINARY_SENSOR_TYPES,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Storcube Battery Monitor binary sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    for equip_id in coordinator.data.get("rest_api", {}):
        for sensor_type in BINARY_SENSOR_TYPES:
            entities.append(
                StorcubeBinarySensor(
                    coordinator,
                    config_entry,
                    equip_id,
                    sensor_type,
                )
            )
    
    async_add_entities(entities)

class StorcubeBinarySensor(StorcubeBaseEntity, BinarySensorEntity):
    """Representation of a Storcube Battery Monitor binary sensor."""

    def __init__(
        self,
        coordinator: StorcubeDataUpdateCoordinator,
        config_entry: ConfigEntry,
        equip_id: str,
        sensor_type: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, config_entry, equip_id)
        self._sensor_type = sensor_type
        self._attr_name = f"{MANUFACTURER} {BINARY_SENSOR_TYPES[sensor_type]['name']} {equip_id}"
        self._attr_unique_id = f"{equip_id}_{sensor_type}"
        self._attr_device_class = BINARY_SENSOR_TYPES[sensor_type]["device_class"]
        self._attr_icon = BINARY_SENSOR_TYPES[sensor_type]["icon"]

    @property
    def is_on(self) -> Optional[bool]:
        """Return the state of the binary sensor."""
        if not self.coordinator.data:
            return None

        websocket_data = self.coordinator.data.get("websocket", {}).get(self._equip_id, {})
        rest_data = self.coordinator.data.get("rest_api", {}).get(self._equip_id, {})

        if self._sensor_type == "online":
            return websocket_data.get("online", False)
        elif self._sensor_type == "charging":
            return websocket_data.get("charging", False)
        elif self._sensor_type == "discharging":
            return websocket_data.get("discharging", False)

        return None 