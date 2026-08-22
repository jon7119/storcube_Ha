"""Entités de réglage pour l'intégration Storcube Battery Monitor."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MAX_POWER,
    MAX_THRESHOLD,
    MIN_POWER,
    MIN_THRESHOLD,
)
from .coordinator import StorCubeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configurer les entités de réglage."""
    coordinator: StorCubeDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    known: set[str] = set()

    @callback
    def _async_add_new_devices() -> None:
        """Créer les entités des batteries découvertes depuis le dernier appel."""
        # Les consignes s'appliquent au stack et sont envoyées avec
        # l'equipId du maître. Créer ces curseurs sur un esclave laisserait
        # croire qu'on pilote cette batterie-là.
        master = coordinator.master_equip_id
        if master in known or master not in (coordinator.data or {}):
            return
        known.add(master)
        async_add_entities(
            [
                StorCubePowerNumber(coordinator, master),
                StorCubeThresholdNumber(coordinator, master),
            ]
        )

    _async_add_new_devices()
    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_add_new_devices)
    )


class StorCubeNumberBase(
    CoordinatorEntity[StorCubeDataUpdateCoordinator], NumberEntity
):
    """Base commune aux réglages StorCube."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER
    _attr_native_step = 1.0

    def __init__(
        self, coordinator: StorCubeDataUpdateCoordinator, equip_id: str
    ) -> None:
        """Initialiser l'entité."""
        super().__init__(coordinator)
        self.equip_id = equip_id
        # Valeur optimiste retenue entre l'envoi de la consigne et sa
        # confirmation par l'appareil.
        self._pending: float | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Rattacher l'entité à l'appareil batterie."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.equip_id)},
            name=f"Batterie StorCube {self.equip_id}",
            manufacturer="StorCube",
        )

    @property
    def _device_data(self) -> dict:
        """Retourner les données combinées de cette batterie."""
        return (self.coordinator.data or {}).get(self.equip_id) or {}

    @property
    def available(self) -> bool:
        """Indiquer si la batterie répond."""
        return super().available and self.equip_id in (self.coordinator.data or {})

    def _reported_value(self) -> float | None:
        """Retourner la valeur remontée par l'appareil (à surcharger)."""
        raise NotImplementedError

    @property
    def native_value(self) -> float | None:
        """Retourner la consigne courante."""
        reported = self._reported_value()
        if self._pending is not None:
            # L'appareil a confirmé : on abandonne la valeur optimiste.
            if reported is not None and abs(reported - self._pending) < 1:
                self._pending = None
            else:
                return self._pending
        return reported

    @callback
    def _handle_coordinator_update(self) -> None:
        """Rafraîchir l'entité sur nouvelle donnée."""
        super()._handle_coordinator_update()


def _num(value: Any) -> float | None:
    """Convertir en float, ou None si impossible."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class StorCubePowerNumber(StorCubeNumberBase):
    """Consigne de puissance de sortie."""

    _attr_name = "Puissance de sortie"
    _attr_icon = "mdi:flash"
    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = float(MIN_POWER)
    _attr_native_max_value = float(MAX_POWER)

    def __init__(
        self, coordinator: StorCubeDataUpdateCoordinator, equip_id: str
    ) -> None:
        """Initialiser l'entité."""
        super().__init__(coordinator, equip_id)
        self._attr_unique_id = f"{equip_id}_output_power"

    def _reported_value(self) -> float | None:
        """Lire la puissance de sortie remontée par l'appareil."""
        data = self._device_data
        raw = data.get("battery_output")
        raw = raw if isinstance(raw, dict) else {}
        for key in ("outputPower", "output_power", "invPower"):
            value = _num(raw.get(key))
            if value is None:
                value = _num(data.get(key))
            if value is not None:
                return value
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Envoyer une nouvelle consigne de puissance."""
        if await self.coordinator.async_set_power_value(int(value)):
            self._pending = value
            self.async_write_ha_state()
        else:
            _LOGGER.warning(
                "La consigne de puissance %s W n'a pas été acceptée", int(value)
            )
            # Réaffiche la valeur réelle plutôt que de laisser le curseur
            # sur une consigne qui n'a pas pris.
            self.async_write_ha_state()


class StorCubeThresholdNumber(StorCubeNumberBase):
    """Seuil de décharge de la batterie."""

    _attr_name = "Seuil de décharge"
    _attr_icon = "mdi:battery-charging-medium"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_native_min_value = float(MIN_THRESHOLD)
    _attr_native_max_value = float(MAX_THRESHOLD)

    def __init__(
        self, coordinator: StorCubeDataUpdateCoordinator, equip_id: str
    ) -> None:
        """Initialiser l'entité."""
        super().__init__(coordinator, equip_id)
        self._attr_unique_id = f"{equip_id}_battery_threshold"
        self._queried: float | None = None

    async def async_added_to_hass(self) -> None:
        """Synchroniser le seuil avec l'appareil au démarrage."""
        await super().async_added_to_hass()
        if self._reported_value() is None:
            value = await self.coordinator.async_get_threshold()
            if value is not None:
                self._queried = float(value)
                self.async_write_ha_state()

    def _reported_value(self) -> float | None:
        """Lire le seuil remonté par l'appareil."""
        data = self._device_data
        raw = data.get("battery_output")
        raw = raw if isinstance(raw, dict) else {}
        value = _num(raw.get("reserved"))
        if value is None:
            value = _num(data.get("reserved"))
        if value is None:
            value = self._queried
        return value

    async def async_set_native_value(self, value: float) -> None:
        """Envoyer un nouveau seuil de décharge."""
        if await self.coordinator.async_set_threshold_value(int(value)):
            self._pending = value
            self._queried = value
            self.async_write_ha_state()
        else:
            _LOGGER.warning("Le seuil %s %% n'a pas été accepté", int(value))
            self.async_write_ha_state()
