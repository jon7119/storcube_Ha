"""Base entity for Storcube Battery Monitor integration."""
from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry

from ..core.coordinator import StorcubeDataUpdateCoordinator
from ..const import DOMAIN

class StorcubeBaseEntity(CoordinatorEntity):
    """Base entity for Storcube Battery Monitor."""

    def __init__(
        self,
        coordinator: StorcubeDataUpdateCoordinator,
        config_entry: ConfigEntry,
        equip_id: str,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self._equip_id = equip_id
        self._config_entry = config_entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._equip_id)},
            name=f"Batterie StorCube {self._equip_id}",
            manufacturer="StorCube",
            model=self.coordinator.data.get("rest_api", {}).get(self._equip_id, {}).get("equip_model", "Unknown"),
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.data.get("rest_api", {}).get(self._equip_id, {}).get("rg_online", False)
            and self.coordinator.data.get("websocket", {}).get(self._equip_id, {}).get("online", False)
        ) 