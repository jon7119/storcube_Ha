"""Capteur binaire pour l'intégration Storcube Battery Monitor."""
import json
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .coordinator import StorCubeDataUpdateCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configurer le capteur binaire basé sur une entrée de configuration."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Créer un capteur binaire pour chaque batterie
    entities = []
    for equip_id in coordinator.data:
        entities.append(StorCubeBatteryConnectionSensor(coordinator, equip_id))

    async_add_entities(entities)

class StorCubeBatteryConnectionSensor(CoordinatorEntity, BinarySensorEntity):
    """Capteur binaire pour l'état de la connexion de la batterie."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:connection"

    def __init__(self, coordinator: StorCubeDataUpdateCoordinator, equip_id: str) -> None:
        """Initialiser le capteur."""
        super().__init__(coordinator)
        self._equip_id = equip_id
        self._attr_unique_id = f"{equip_id}_connection"
        self._attr_name = f"StorCube Battery {equip_id} Status"

    @property
    def device_info(self) -> DeviceInfo:
        """Retourner les informations sur l'appareil."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._equip_id)},
            name=f"Batterie StorCube {self._equip_id}",
            manufacturer="StorCube",
        )

    @property
    def is_on(self) -> bool:
        """Retourner l'état de la connexion."""
        try:
            data = self.coordinator.data.get(self._equip_id, {}).get("battery_status", "{}")
            value = json.loads(data).get("value", 0)
            return value == 1
        except (json.JSONDecodeError, KeyError, AttributeError):
            return False 