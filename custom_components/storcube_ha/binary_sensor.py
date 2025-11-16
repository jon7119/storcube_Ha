"""Capteur binaire pour l'intégration Storcube Battery Monitor."""
import json
import logging
from typing import Any
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, ICON_CONNECTION, CONF_DEVICE_ID
from .coordinator import StorCubeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Configurer le capteur binaire basé sur une entrée de configuration."""
    config = config_entry.data
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Créer les capteurs binaires
    entities = []
    # Capteur de connexion pour chaque batterie existante
    # Les equip_id sont dans coordinator.data["combined"]
    combined_data = coordinator.data.get("combined", {})
    for equip_id in combined_data:
        # Vérifier que c'est bien un equip_id (pas une clé système comme "websocket", "rest_api", etc.)
        if equip_id not in ["websocket", "rest_api", "combined", "firmware", "last_ws_update", "last_rest_update"]:
            entities.append(StorCubeBatteryConnectionSensor(coordinator, equip_id))
    
    # Ajouter les nouveaux capteurs binaires
    entities.extend([
        StorcubeGridConnectedBinarySensor(config),
        StorcubeBatteryChargingBinarySensor(config),
        StorcubeBatteryDischargingBinarySensor(config),
        StorcubePvConnectedBinarySensor(config),
        StorcubeLoadConnectedBinarySensor(config),
        StorcubeFaultBinarySensor(config),
        StorcubeWarningBinarySensor(config),
    ])

    async_add_entities(entities)
    
    # Enregistrer les binary sensors dans le coordinateur pour les mises à jour
    # Le coordinateur est déjà stocké dans hass.data[DOMAIN][config_entry.entry_id]
    # On peut stocker les binary sensors dans un attribut du coordinateur si nécessaire
    # Pour l'instant, on les laisse gérer par Home Assistant

class StorCubeBatteryConnectionSensor(CoordinatorEntity, BinarySensorEntity):
    """Capteur binaire pour l'état de la connexion de la batterie."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = ICON_CONNECTION

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


class StorcubeBaseBinarySensor(BinarySensorEntity):
    """Base class for Storcube binary sensors."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the binary sensor."""
        self._config = config
        self._device_id = config[CONF_DEVICE_ID]
        self._websocket_data = {}
        self._attr_is_on = False
        self._attr_available = True
    
    @property
    def device_info(self) -> DeviceInfo:
        """Retourner les informations de l'appareil."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name="StorCube Battery Monitor",
            manufacturer="StorCube",
            model="S1000",
        )

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Gérer la mise à jour de l'état depuis les différentes sources."""
        try:
            if "websocket_data" in payload:
                self._websocket_data = payload["websocket_data"]
                self._update_value_from_sources()
            elif "list" in payload and payload["list"]:
                self._websocket_data = {"list": payload["list"]}
                self._update_value_from_sources()
        except Exception as e:
            _LOGGER.error("Erreur lors de la mise à jour du capteur binaire %s: %s", self.name, str(e))

    def _update_value_from_sources(self):
        """Mettre à jour la valeur en fonction des sources disponibles."""
        pass


class StorcubeGridConnectedBinarySensor(StorcubeBaseBinarySensor):
    """Capteur binaire pour la connexion au réseau."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the binary sensor."""
        super().__init__(config)
        self._attr_name = "Réseau Connecté Storcube"
        self._attr_unique_id = f"{self._device_id}_grid_connected"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_icon = "mdi:transmission-tower"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                self._attr_is_on = equip.get("grid_connected", False)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating grid connected: %s", e)


class StorcubeBatteryChargingBinarySensor(StorcubeBaseBinarySensor):
    """Capteur binaire pour la charge de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the binary sensor."""
        super().__init__(config)
        self._attr_name = "Batterie en Charge Storcube"
        self._attr_unique_id = f"{self._device_id}_battery_charging"
        self._attr_device_class = None
        self._attr_icon = "mdi:battery-charging"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                self._attr_is_on = equip.get("battery_charging", False)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery charging: %s", e)


class StorcubeBatteryDischargingBinarySensor(StorcubeBaseBinarySensor):
    """Capteur binaire pour la décharge de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the binary sensor."""
        super().__init__(config)
        self._attr_name = "Batterie en Décharge Storcube"
        self._attr_unique_id = f"{self._device_id}_battery_discharging"
        self._attr_device_class = None
        self._attr_icon = "mdi:battery-arrow-down"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                self._attr_is_on = equip.get("battery_discharging", False)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery discharging: %s", e)


class StorcubePvConnectedBinarySensor(StorcubeBaseBinarySensor):
    """Capteur binaire pour la connexion PV."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the binary sensor."""
        super().__init__(config)
        self._attr_name = "PV Connecté Storcube"
        self._attr_unique_id = f"{self._device_id}_pv_connected"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_icon = "mdi:solar-power"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                self._attr_is_on = equip.get("pv_connected", False)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating PV connected: %s", e)


class StorcubeLoadConnectedBinarySensor(StorcubeBaseBinarySensor):
    """Capteur binaire pour la connexion de la charge."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the binary sensor."""
        super().__init__(config)
        self._attr_name = "Charge Connectée Storcube"
        self._attr_unique_id = f"{self._device_id}_load_connected"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_icon = "mdi:home-lightning-bolt"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                self._attr_is_on = equip.get("load_connected", False)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating load connected: %s", e)


class StorcubeFaultBinarySensor(StorcubeBaseBinarySensor):
    """Capteur binaire pour les erreurs."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the binary sensor."""
        super().__init__(config)
        self._attr_name = "Erreur Storcube"
        self._attr_unique_id = f"{self._device_id}_fault"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_icon = "mdi:alert"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                self._attr_is_on = equip.get("fault", False)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating fault: %s", e)


class StorcubeWarningBinarySensor(StorcubeBaseBinarySensor):
    """Capteur binaire pour les avertissements."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the binary sensor."""
        super().__init__(config)
        self._attr_name = "Avertissement Storcube"
        self._attr_unique_id = f"{self._device_id}_warning"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_icon = "mdi:alert-circle"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                self._attr_is_on = equip.get("warning", False)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating warning: %s", e) 