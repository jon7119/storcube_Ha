"""Capteurs pour l'intégration Storcube Battery Monitor."""
from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPower,
    UnitOfEnergy,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import (
    DOMAIN,
    ICON_BATTERY,
    ICON_SOLAR,
    ICON_INVERTER,
    ICON_TEMPERATURE,
)
from .coordinator import StorcubeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configurer les capteurs basés sur une entrée de configuration."""
    coordinator: StorcubeDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Liste pour stocker tous les capteurs
    entities = []

    # Pour chaque batterie détectée
    for equip_id in coordinator.data:
        entities.extend([
            StorCubeBatteryStatusSensor(coordinator, equip_id),
            StorCubeBatteryCapacitySensor(coordinator, equip_id),
            StorCubeBatteryPowerSensor(coordinator, equip_id),
            StorCubeBatterySolarPowerSensor(coordinator, equip_id),
            StorCubeBatteryTemperatureSensor(coordinator, equip_id),
        ])

    async_add_entities(entities)

class StorCubeBaseSensor(CoordinatorEntity, SensorEntity):
    """Classe de base pour les capteurs StorCube."""

    def __init__(
        self,
        coordinator: StorcubeDataUpdateCoordinator,
        equip_id: str,
        key: str,
        name: str,
        icon: str | None = None,
        device_class: str | None = None,
        state_class: str | None = None,
        unit_of_measurement: str | None = None,
    ) -> None:
        """Initialiser le capteur."""
        super().__init__(coordinator)
        
        self._equip_id = equip_id
        self._key = key
        self._attr_name = f"StorCube {name}"
        self._attr_unique_id = f"{equip_id}_{key}"
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit_of_measurement

    @property
    def device_info(self) -> DeviceInfo:
        """Retourner les informations sur l'appareil."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._equip_id)},
            name=f"Batterie StorCube {self._equip_id}",
            manufacturer="StorCube",
        )

    @property
    def native_value(self) -> StateType:
        """Retourner la valeur du capteur."""
        try:
            data = self.coordinator.data.get(self._equip_id, {}).get(self._key, "{}")
            return json.loads(data).get("value")
        except (json.JSONDecodeError, KeyError, AttributeError):
            return None

class StorCubeBatteryStatusSensor(StorCubeBaseSensor):
    """Capteur pour l'état de la batterie."""

    def __init__(self, coordinator: StorcubeDataUpdateCoordinator, equip_id: str) -> None:
        """Initialiser le capteur."""
        super().__init__(
            coordinator,
            equip_id,
            "battery_status",
            "État Batterie",
            icon=ICON_BATTERY,
            device_class=SensorDeviceClass.ENUM,
        )

    @property
    def options(self) -> list[str]:
        """Retourner les états possibles."""
        return ["En ligne", "Hors ligne"]

    @property
    def native_value(self) -> str | None:
        """Retourner l'état de la batterie."""
        try:
            data = self.coordinator.data.get(self._equip_id, {}).get(self._key, "{}")
            value = json.loads(data).get("value", 0)
            return "En ligne" if value == 1 else "Hors ligne"
        except (json.JSONDecodeError, KeyError, AttributeError):
            return None

class StorCubeBatteryCapacitySensor(StorCubeBaseSensor):
    """Capteur pour la capacité de la batterie."""

    def __init__(self, coordinator: StorcubeDataUpdateCoordinator, equip_id: str) -> None:
        """Initialiser le capteur."""
        super().__init__(
            coordinator,
            equip_id,
            "battery_capacity",
            "Capacité Batterie",
            icon=ICON_BATTERY,
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
            unit_of_measurement=PERCENTAGE,
        )

class StorCubeBatteryPowerSensor(StorCubeBaseSensor):
    """Capteur pour la puissance de la batterie."""

    def __init__(self, coordinator: StorcubeDataUpdateCoordinator, equip_id: str) -> None:
        """Initialiser le capteur."""
        super().__init__(
            coordinator,
            equip_id,
            "battery_power",
            "Puissance Batterie",
            icon=ICON_INVERTER,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            unit_of_measurement=UnitOfPower.WATT,
        )

class StorCubeBatterySolarPowerSensor(StorCubeBaseSensor):
    """Capteur pour la puissance solaire."""

    def __init__(self, coordinator: StorcubeDataUpdateCoordinator, equip_id: str) -> None:
        """Initialiser le capteur."""
        super().__init__(
            coordinator,
            equip_id,
            "battery_solar",
            "Puissance Solaire",
            icon=ICON_SOLAR,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            unit_of_measurement=UnitOfPower.WATT,
        )

class StorCubeBatteryTemperatureSensor(StorCubeBaseSensor):
    """Capteur pour la température de la batterie."""

    def __init__(self, coordinator: StorcubeDataUpdateCoordinator, equip_id: str) -> None:
        """Initialiser le capteur."""
        super().__init__(
            coordinator,
            equip_id,
            "battery_temperature",
            "Température Batterie",
            icon=ICON_TEMPERATURE,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            unit_of_measurement=UnitOfTemperature.CELSIUS,
        )

    @property
    def native_value(self) -> float | None:
        """Retourner la température de la batterie."""
        try:
            data = self.coordinator.data.get(self._equip_id, {}).get("battery_output", "{}")
            battery_data = json.loads(data)
            return float(battery_data.get("temperature", 0))
        except (json.JSONDecodeError, KeyError, ValueError, AttributeError):
            return None 