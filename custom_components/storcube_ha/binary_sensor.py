"""Capteur binaire pour l'intégration Storcube Battery Monitor."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ICON_CONNECTION
from .coordinator import StorCubeDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configurer les capteurs binaires depuis une entrée de configuration."""
    coordinator: StorCubeDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    known: set[str] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Créer les entités des batteries apparues depuis le dernier appel."""
        new = [
            StorCubeBatteryConnectionSensor(coordinator, equip_id)
            for equip_id in (coordinator.data or {})
            if equip_id not in known
        ]
        if new:
            known.update(entity.equip_id for entity in new)
            async_add_entities(new)

    _async_add_new_devices()
    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_add_new_devices)
    )


class StorCubeBatteryConnectionSensor(CoordinatorEntity, BinarySensorEntity):
    """État de connexion d'une batterie StorCube."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = ICON_CONNECTION
    _attr_has_entity_name = True
    _attr_name = "Connexion"

    def __init__(
        self, coordinator: StorCubeDataUpdateCoordinator, equip_id: str
    ) -> None:
        """Initialiser le capteur."""
        super().__init__(coordinator)
        self.equip_id = equip_id
        self._attr_unique_id = f"{DOMAIN}_{equip_id}_connection"

    @property
    def device_info(self) -> DeviceInfo:
        """Retourner les informations de l'appareil."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.equip_id)},
            name=f"Batterie StorCube {self.equip_id}",
            manufacturer="StorCube",
        )

    @property
    def available(self) -> bool:
        """Indiquer si la batterie est présente dans les données."""
        return super().available and self.equip_id in (self.coordinator.data or {})

    @property
    def is_on(self) -> bool:
        """Retourner True si la batterie est en ligne."""
        data = (self.coordinator.data or {}).get(self.equip_id) or {}
        value = data.get("battery_status")
        # Tolère les valeurs héritées sérialisées en JSON.
        if isinstance(value, dict):
            value = value.get("value")
        try:
            return int(value) == 1
        except (TypeError, ValueError):
            return False
