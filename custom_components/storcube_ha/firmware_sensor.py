"""Capteur de firmware pour l'intégration Storcube Battery Monitor."""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_NAME,
    PERCENTAGE,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfElectricCurrent,
    UnitOfVoltage,
    UnitOfEnergy,
)

from .const import (
    DOMAIN,
    NAME,
    ATTR_FIRMWARE_CURRENT,
    ATTR_FIRMWARE_LATEST,
    ATTR_FIRMWARE_UPGRADE_AVAILABLE,
    ATTR_FIRMWARE_NOTES,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configurer le capteur de firmware."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    # Créer le capteur de firmware
    firmware_sensor = StorCubeFirmwareSensor(coordinator, config_entry)
    async_add_entities([firmware_sensor], True)

class StorCubeFirmwareSensor(SensorEntity):
    """Capteur pour les informations de firmware StorCube."""

    def __init__(self, coordinator, config_entry):
        """Initialiser le capteur de firmware."""
        self.coordinator = coordinator
        self.config_entry = config_entry
        self._attr_name = f"Firmware StorCube"
        self._attr_unique_id = f"{config_entry.entry_id}_firmware"
        self._attr_icon = "mdi:update"
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None
        self._attr_state_class = None

    @property
    def device_info(self) -> DeviceInfo:
        """Retourner les informations de l'appareil."""
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": NAME,
            "manufacturer": "StorCube",
        }

    @property
    def available(self) -> bool:
        """Retourner True si l'entité est disponible."""
        return self.coordinator.last_update_success

    @property
    def native_value(self) -> StateType:
        """Retourner la valeur native du capteur."""
        firmware_data = self.coordinator.data.get("firmware", {})
        current_version = firmware_data.get("current_version", "Inconnue")
        upgrade_available = firmware_data.get("upgrade_available", False)
        
        if upgrade_available:
            return f"Mise à jour disponible ({current_version})"
        else:
            return f"À jour ({current_version})"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Retourner les attributs supplémentaires."""
        firmware_data = self.coordinator.data.get("firmware", {})
        
        return {
            ATTR_FIRMWARE_CURRENT: firmware_data.get("current_version", "Inconnue"),
            ATTR_FIRMWARE_LATEST: firmware_data.get("latest_version", "Inconnue"),
            ATTR_FIRMWARE_UPGRADE_AVAILABLE: firmware_data.get("upgrade_available", False),
            ATTR_FIRMWARE_NOTES: firmware_data.get("firmware_notes", []),
            "last_check": firmware_data.get("last_check", "Jamais"),
        }

    async def async_added_to_hass(self) -> None:
        """Appelé quand l'entité est ajoutée à Home Assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_update(self) -> None:
        """Mettre à jour le capteur."""
        await self.coordinator.async_request_refresh() 