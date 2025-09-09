"""Capteurs individuels pour chaque batterie StorCube."""
from __future__ import annotations

import logging
from typing import Any, Optional
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPower,
    UnitOfEnergy,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, CONF_DEVICE_ID
from .battery_manager import BatteryInfo

_LOGGER = logging.getLogger(__name__)

class IndividualBatterySensor(SensorEntity):
    """Capteur de base pour une batterie individuelle."""

    def __init__(self, config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> None:
        """Initialiser le capteur."""
        self._config = config
        self._equip_id = equip_id
        self._battery_info = battery_info
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    @callback
    def handle_state_update(self, battery_info: BatteryInfo) -> None:
        """Gérer la mise à jour de l'état de la batterie."""
        self._battery_info = battery_info
        self._update_value()
        self.async_write_ha_state()

    def _update_value(self):
        """Mettre à jour la valeur du capteur."""
        # À implémenter dans les classes enfants
        pass

    @property
    def device_info(self) -> dict[str, Any]:
        """Retourner les informations de l'appareil."""
        # Déterminer le rôle de la batterie
        role = "Maître" if self._battery_info.is_master else "Esclave"
        
        device_info = {
            "identifiers": {(DOMAIN, self._equip_id)},
            "name": f"Batterie StorCube {self._equip_id} ({role})",  # Afficher l'ID complet avec le rôle
            "manufacturer": "StorCube",
            "model": "S1000",
        }
        
        # Seulement ajouter via_device si ce n'est pas la batterie maître
        if not self._battery_info.is_master:
            device_info["via_device"] = (DOMAIN, self._config[CONF_DEVICE_ID])
        
        return device_info

class IndividualBatteryLevelSensor(IndividualBatterySensor):
    """Capteur de niveau de batterie individuelle."""

    def __init__(self, config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> None:
        """Initialiser le capteur."""
        super().__init__(config, equip_id, battery_info)
        role = "Maître" if battery_info.is_master else "Esclave"
        self._attr_name = f"Niveau Batterie {equip_id} ({role})"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_{equip_id}_level"
        self._attr_icon = "mdi:battery-high"

    def _update_value(self):
        """Mettre à jour la valeur du capteur."""
        if self._battery_info.soc is not None:
            self._attr_native_value = self._battery_info.soc
            self._attr_extra_state_attributes = {
                "is_master": self._battery_info.is_master,
                "last_update": self._battery_info.last_update.isoformat() if self._battery_info.last_update else None,
                "equip_id": self._equip_id
            }

class IndividualBatteryTemperatureSensor(IndividualBatterySensor):
    """Capteur de température de batterie individuelle."""

    def __init__(self, config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> None:
        """Initialiser le capteur."""
        super().__init__(config, equip_id, battery_info)
        role = "Maître" if battery_info.is_master else "Esclave"
        self._attr_name = f"Température Batterie {equip_id} ({role})"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_{equip_id}_temperature"
        self._attr_icon = "mdi:thermometer"

    def _update_value(self):
        """Mettre à jour la valeur du capteur."""
        if self._battery_info.temp is not None:
            self._attr_native_value = self._battery_info.temp
            self._attr_extra_state_attributes = {
                "is_master": self._battery_info.is_master,
                "last_update": self._battery_info.last_update.isoformat() if self._battery_info.last_update else None,
                "equip_id": self._equip_id
            }

class IndividualBatteryCapacitySensor(IndividualBatterySensor):
    """Capteur de capacité de batterie individuelle."""

    def __init__(self, config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> None:
        """Initialiser le capteur."""
        super().__init__(config, equip_id, battery_info)
        role = "Maître" if battery_info.is_master else "Esclave"
        self._attr_name = f"Capacité Batterie {equip_id} ({role})"
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY_STORAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_{equip_id}_capacity"
        self._attr_icon = "mdi:battery-charging"

    def _update_value(self):
        """Mettre à jour la valeur du capteur."""
        if self._battery_info.capacity is not None:
            self._attr_native_value = float(self._battery_info.capacity)
            self._attr_extra_state_attributes = {
                "is_master": self._battery_info.is_master,
                "last_update": self._battery_info.last_update.isoformat() if self._battery_info.last_update else None,
                "equip_id": self._equip_id
            }

class IndividualBatteryStatusSensor(IndividualBatterySensor):
    """Capteur de statut de batterie individuelle."""

    def __init__(self, config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> None:
        """Initialiser le capteur."""
        super().__init__(config, equip_id, battery_info)
        role = "Maître" if battery_info.is_master else "Esclave"
        self._attr_name = f"Statut Batterie {equip_id} ({role})"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_{equip_id}_status"
        self._attr_icon = "mdi:power"

    def _update_value(self):
        """Mettre à jour la valeur du capteur."""
        if self._battery_info.isWork is not None:
            status_map = {
                0: "Arrêté",
                1: "En fonctionnement",
                2: "En erreur"
            }
            self._attr_native_value = status_map.get(self._battery_info.isWork, "Inconnu")
            self._attr_extra_state_attributes = {
                "is_master": self._battery_info.is_master,
                "last_update": self._battery_info.last_update.isoformat() if self._battery_info.last_update else None,
                "equip_id": self._equip_id,
                "work_status_code": self._battery_info.isWork
            }

class IndividualBatterySolarPowerSensor(IndividualBatterySensor):
    """Capteur de puissance solaire de batterie individuelle."""

    def __init__(self, config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> None:
        """Initialiser le capteur."""
        super().__init__(config, equip_id, battery_info)
        role = "Maître" if battery_info.is_master else "Esclave"
        self._attr_name = f"Puissance Solaire Batterie {equip_id} ({role})"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_{equip_id}_solar_power"
        self._attr_icon = "mdi:solar-power"

    def _update_value(self):
        """Mettre à jour la valeur du capteur."""
        pv1_power = self._battery_info.pv1power or 0
        pv2_power = self._battery_info.pv2power or 0
        total_power = pv1_power + pv2_power
        
        if total_power > 0:
            self._attr_native_value = total_power
            self._attr_extra_state_attributes = {
                "pv1_power": pv1_power,
                "pv2_power": pv2_power,
                "is_master": self._battery_info.is_master,
                "last_update": self._battery_info.last_update.isoformat() if self._battery_info.last_update else None,
                "equip_id": self._equip_id
            }

class IndividualBatteryInverterPowerSensor(IndividualBatterySensor):
    """Capteur de puissance onduleur de batterie individuelle."""

    def __init__(self, config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> None:
        """Initialiser le capteur."""
        super().__init__(config, equip_id, battery_info)
        role = "Maître" if battery_info.is_master else "Esclave"
        self._attr_name = f"Puissance Onduleur Batterie {equip_id} ({role})"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_{equip_id}_inverter_power"
        self._attr_icon = "mdi:flash"

    def _update_value(self):
        """Mettre à jour la valeur du capteur."""
        if self._battery_info.invPower is not None:
            self._attr_native_value = self._battery_info.invPower
            self._attr_extra_state_attributes = {
                "is_master": self._battery_info.is_master,
                "last_update": self._battery_info.last_update.isoformat() if self._battery_info.last_update else None,
                "equip_id": self._equip_id
            }

class IndividualBatteryWorkStatusSensor(IndividualBatterySensor):
    """Capteur d'état de fonctionnement de batterie individuelle."""

    def __init__(self, config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> None:
        """Initialiser le capteur."""
        super().__init__(config, equip_id, battery_info)
        role = "Maître" if battery_info.is_master else "Esclave"
        self._attr_name = f"État de Fonctionnement {equip_id} ({role})"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_{equip_id}_work_status"
        self._attr_icon = "mdi:power"

    def _update_value(self):
        """Mettre à jour la valeur du capteur."""
        if hasattr(self._battery_info, 'is_work'):
            self._attr_native_value = 'online' if self._battery_info.is_work == 1 else 'offline'
        else:
            self._attr_native_value = 'unknown'

class IndividualBatteryConnectionStatusSensor(IndividualBatterySensor):
    """Capteur d'état de connexion de batterie individuelle."""

    def __init__(self, config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> None:
        """Initialiser le capteur."""
        super().__init__(config, equip_id, battery_info)
        role = "Maître" if battery_info.is_master else "Esclave"
        self._attr_name = f"État de Connexion {equip_id} ({role})"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_{equip_id}_connection_status"
        self._attr_icon = "mdi:wifi"

    def _update_value(self):
        """Mettre à jour la valeur du capteur."""
        # Pour l'instant, on considère que si on a des données, la connexion est OK
        self._attr_native_value = 'connected' if self._battery_info else 'disconnected'

class IndividualBatteryErrorCodeSensor(IndividualBatterySensor):
    """Capteur de code d'erreur de batterie individuelle."""

    def __init__(self, config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> None:
        """Initialiser le capteur."""
        super().__init__(config, equip_id, battery_info)
        role = "Maître" if battery_info.is_master else "Esclave"
        self._attr_name = f"Code d'Erreur {equip_id} ({role})"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_{equip_id}_error_code"
        self._attr_icon = "mdi:alert-circle"

    def _update_value(self):
        """Mettre à jour la valeur du capteur."""
        # Pour l'instant, pas de code d'erreur spécifique par batterie
        self._attr_native_value = 'none'

class IndividualBatteryFirmwareSensor(IndividualBatterySensor):
    """Capteur de firmware de batterie individuelle."""

    def __init__(self, config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> None:
        """Initialiser le capteur."""
        super().__init__(config, equip_id, battery_info)
        role = "Maître" if battery_info.is_master else "Esclave"
        self._attr_name = f"Firmware StorCube {equip_id} ({role})"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_{equip_id}_firmware"
        self._attr_icon = "mdi:update"

    def _update_value(self):
        """Mettre à jour la valeur du capteur."""
        # Pour l'instant, pas de firmware spécifique par batterie
        self._attr_native_value = 'unknown'

class IndividualBatteryOperatingModeSensor(IndividualBatterySensor):
    """Capteur de mode de fonctionnement de batterie individuelle."""

    def __init__(self, config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> None:
        """Initialiser le capteur."""
        super().__init__(config, equip_id, battery_info)
        role = "Maître" if battery_info.is_master else "Esclave"
        self._attr_name = f"Mode de Fonctionnement {equip_id} ({role})"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_{equip_id}_operating_mode"
        self._attr_icon = "mdi:cog"

    def _update_value(self):
        """Mettre à jour la valeur du capteur."""
        # Pour l'instant, pas de mode spécifique par batterie
        self._attr_native_value = 'unknown'

class IndividualBatteryEnergySensor(IndividualBatterySensor):
    """Capteur d'énergie de batterie individuelle."""

    def __init__(self, config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> None:
        """Initialiser le capteur."""
        super().__init__(config, equip_id, battery_info)
        role = "Maître" if battery_info.is_master else "Esclave"
        self._attr_name = f"Énergie Batterie {equip_id} ({role})"
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_{equip_id}_energy"
        self._attr_icon = "mdi:battery-charging"

    def _update_value(self):
        """Mettre à jour la valeur du capteur."""
        # Pour l'instant, pas d'énergie spécifique par batterie
        self._attr_native_value = None

class IndividualBatteryHealthSensor(IndividualBatterySensor):
    """Capteur de santé de batterie individuelle."""

    def __init__(self, config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> None:
        """Initialiser le capteur."""
        super().__init__(config, equip_id, battery_info)
        role = "Maître" if battery_info.is_master else "Esclave"
        self._attr_name = f"Santé Batterie {equip_id} ({role})"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_{equip_id}_health"
        self._attr_icon = "mdi:heart-pulse"

    def _update_value(self):
        """Mettre à jour la valeur du capteur."""
        # Pour l'instant, pas de santé spécifique par batterie
        self._attr_native_value = None

class IndividualBatterySystemStatusSensor(IndividualBatterySensor):
    """Capteur d'état système de batterie individuelle."""

    def __init__(self, config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> None:
        """Initialiser le capteur."""
        super().__init__(config, equip_id, battery_info)
        role = "Maître" if battery_info.is_master else "Esclave"
        self._attr_name = f"État Système {equip_id} ({role})"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_{equip_id}_system_status"
        self._attr_icon = "mdi:information"

    def _update_value(self):
        """Mettre à jour la valeur du capteur."""
        # Pour l'instant, pas d'état système spécifique par batterie
        self._attr_native_value = 'unknown'

class IndividualBatteryModelSensor(IndividualBatterySensor):
    """Capteur de modèle de batterie individuelle."""

    def __init__(self, config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> None:
        """Initialiser le capteur."""
        super().__init__(config, equip_id, battery_info)
        role = "Maître" if battery_info.is_master else "Esclave"
        self._attr_name = f"Modèle {equip_id} ({role})"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_{equip_id}_model"
        self._attr_icon = "mdi:information"

    def _update_value(self):
        """Mettre à jour la valeur du capteur."""
        self._attr_native_value = 'S1000'

class IndividualBatterySerialNumberSensor(IndividualBatterySensor):
    """Capteur de numéro de série de batterie individuelle."""

    def __init__(self, config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> None:
        """Initialiser le capteur."""
        super().__init__(config, equip_id, battery_info)
        role = "Maître" if battery_info.is_master else "Esclave"
        self._attr_name = f"Numéro de Série {equip_id} ({role})"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_{equip_id}_serial_number"
        self._attr_icon = "mdi:identifier"

    def _update_value(self):
        """Mettre à jour la valeur du capteur."""
        self._attr_native_value = self._equip_id

def create_individual_battery_sensors(config: ConfigType, equip_id: str, battery_info: BatteryInfo) -> list[IndividualBatterySensor]:
    """Créer tous les capteurs pour une batterie individuelle."""
    # Capteurs de base pour toutes les batteries
    sensors = [
        IndividualBatteryLevelSensor(config, equip_id, battery_info),
        IndividualBatteryTemperatureSensor(config, equip_id, battery_info),
        IndividualBatteryCapacitySensor(config, equip_id, battery_info),
        IndividualBatteryStatusSensor(config, equip_id, battery_info),
    ]
    
    # Capteurs spécifiques selon le rôle
    if battery_info.is_master:
        # La batterie maître a les capteurs de puissance solaire et onduleur
        sensors.extend([
            IndividualBatterySolarPowerSensor(config, equip_id, battery_info),
            IndividualBatteryInverterPowerSensor(config, equip_id, battery_info),
        ])
    
    # Capteurs système pour toutes les batteries (seulement ceux qui ont des valeurs connues)
    sensors.extend([
        IndividualBatteryConnectionStatusSensor(config, equip_id, battery_info),
        IndividualBatteryErrorCodeSensor(config, equip_id, battery_info),
        IndividualBatteryModelSensor(config, equip_id, battery_info),
        IndividualBatterySerialNumberSensor(config, equip_id, battery_info),
    ])
    
    return sensors
