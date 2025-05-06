"""Switch entity for Storcube Battery Monitor integration."""
from __future__ import annotations

import logging
from typing import Any, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base import StorcubeBaseEntity
from ..core.coordinator import StorcubeDataUpdateCoordinator
from ..const import (
    DOMAIN,
    SWITCH_TYPES,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Storcube Battery Monitor switches."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    for equip_id in coordinator.data.get("rest_api", {}):
        for switch_type in SWITCH_TYPES:
            entities.append(
                StorcubeSwitch(
                    coordinator,
                    config_entry,
                    equip_id,
                    switch_type,
                )
            )
    
    async_add_entities(entities)

class StorcubeSwitch(StorcubeBaseEntity, SwitchEntity):
    """Representation of a Storcube Battery Monitor switch."""

    def __init__(
        self,
        coordinator: StorcubeDataUpdateCoordinator,
        config_entry: ConfigEntry,
        equip_id: str,
        switch_type: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, config_entry, equip_id)
        self._switch_type = switch_type
        self._attr_name = f"{MANUFACTURER} {SWITCH_TYPES[switch_type]['name']} {equip_id}"
        self._attr_unique_id = f"{equip_id}_{switch_type}"
        self._attr_icon = SWITCH_TYPES[switch_type]["icon"]

    @property
    def is_on(self) -> Optional[bool]:
        """Return the state of the switch."""
        if not self.coordinator.data:
            return None

        websocket_data = self.coordinator.data.get("websocket", {}).get(self._equip_id, {})
        rest_data = self.coordinator.data.get("rest_api", {}).get(self._equip_id, {})

        if self._switch_type == "power":
            return websocket_data.get("powerOn", False)
        elif self._switch_type == "output":
            return websocket_data.get("outputOn", False)

        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if self._switch_type == "power":
            await self.coordinator.async_set_power(self._equip_id, True)
        elif self._switch_type == "output":
            await self.coordinator.async_set_output(self._equip_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if self._switch_type == "power":
            await self.coordinator.async_set_power(self._equip_id, False)
        elif self._switch_type == "output":
            await self.coordinator.async_set_output(self._equip_id, False) 