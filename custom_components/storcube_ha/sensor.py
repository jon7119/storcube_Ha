"""Support for Storcube Battery Monitor sensors."""
from __future__ import annotations

import logging
import json
import asyncio
import aiohttp
import websockets
from datetime import datetime
from typing import Any

from homeassistant.components import mqtt
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    PERCENTAGE,
    UnitOfPower,
    UnitOfEnergy,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    DOMAIN,
    NAME,
    CONF_DEVICE_ID,
    CONF_APP_CODE,
    CONF_LOGIN_NAME,
    CONF_AUTH_PASSWORD,
    WS_URI,
    TOKEN_URL,
    TOPIC_BATTERY,
    TOPIC_OUTPUT,
    TOPIC_FIRMWARE,
    TOPIC_POWER,
    TOPIC_OUTPUT_POWER,
    TOPIC_THRESHOLD,
    OUTPUT_URL,
    FIRMWARE_URL,
    SET_POWER_URL,
    SET_THRESHOLD_URL,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    config = config_entry.data

    sensors = [
        # Capteurs de batterie
        StorcubeBatteryLevelSensor(config),
        StorcubeBatteryPowerSensor(config),
        StorcubeBatteryTemperatureSensor(config),
        StorcubeBatteryCapacityWhSensor(config),
        StorcubeBatteryStatusSensor(config),
        StorcubeBatteryThresholdSensor(config),
        
        # Capteurs solaires
        StorcubeSolarPowerSensor(config),
        StorcubeSolarEnergySensor(config),
        
        # Capteurs solaires pour le deuxième panneau
        StorcubeSolarPowerSensor2(config),
        StorcubeSolarEnergySensor2(config),
        
        # Capteur d'énergie solaire totale
        StorcubeSolarEnergyTotalSensor(config),
        
        # Capteurs de sortie
        StorcubeOutputPowerSensor(config),
        StorcubeOutputEnergySensor(config),
        
        # Capteurs système
        StorcubeStatusSensor(config),
        StorcubeModelSensor(config),
        StorcubeSerialNumberSensor(config),
        
        # Capteurs d'état
        StorcubeOutputTypeSensor(config),
        StorcubeReservedSensor(config),
        StorcubeWorkStatusSensor(config),
        StorcubeOnlineSensor(config),
        StorcubeErrorCodeSensor(config),
        StorcubeOperatingModeSensor(config),
    ]

    async_add_entities(sensors)

    # Store sensors in hass.data
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][config_entry.entry_id] = {"sensors": sensors}

    # Créer la vue Lovelace
    await create_lovelace_view(hass, config_entry)

    # Start websocket connection and output API connection
    asyncio.create_task(websocket_to_mqtt(hass, config, config_entry))
    asyncio.create_task(output_api_to_mqtt(hass, config, config_entry))

async def create_lovelace_view(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Create the Lovelace view for Storcube."""
    device_id = config_entry.data[CONF_DEVICE_ID]
    
    view_config = {
        "path": "storcube",
        "title": "Storcube Battery Monitor",
        "icon": "mdi:battery-charging",
        "badges": [],
        "cards": [
            {
                "type": "energy-distribution",
                "title": "Distribution d'Énergie",
                "entities": {
                    "solar_power": [
                        f"sensor.{device_id}_solar_power",
                        f"sensor.{device_id}_solar_power_2"
                    ],
                    "battery": {
                        "entity": f"sensor.{device_id}_battery_level"
                    },
                    "grid_power": f"sensor.{device_id}_output_power"
                }
            },
            {
                "type": "grid",
                "columns": 2,
                "square": False,
                "cards": [
                    {
                        "type": "gauge",
                        "entity": f"sensor.{device_id}_battery_level",
                        "name": "Niveau Batterie",
                        "min": 0,
                        "max": 100,
                        "severity": {
                            "green": 50,
                            "yellow": 25,
                            "red": 10
                        }
                    },
                    {
                        "type": "gauge",
                        "entity": f"sensor.{device_id}_reserved",
                        "name": "Niveau Réserve",
                        "min": 0,
                        "max": 100,
                        "severity": {
                            "green": 50,
                            "yellow": 25,
                            "red": 10
                        }
                    }
                ]
            },
            {
                "type": "grid",
                "columns": 3,
                "cards": [
                    {
                        "type": "sensor",
                        "entity": f"sensor.{device_id}_solar_power",
                        "name": "Solaire 1",
                        "icon": "mdi:solar-power",
                        "graph": "line"
                    },
                    {
                        "type": "sensor",
                        "entity": f"sensor.{device_id}_solar_power_2",
                        "name": "Solaire 2",
                        "icon": "mdi:solar-power",
                        "graph": "line"
                    },
                    {
                        "type": "sensor",
                        "entity": f"sensor.{device_id}_output_power",
                        "name": "Sortie",
                        "icon": "mdi:power-plug",
                        "graph": "line"
                    }
                ]
            },
            {
                "type": "grid",
                "columns": 2,
                "cards": [
                    {
                        "type": "entities",
                        "title": "État du système",
                        "entities": [
                            {
                                "entity": f"sensor.{device_id}_work_status",
                                "name": "État"
                            },
                            {
                                "entity": f"sensor.{device_id}_online_status",
                                "name": "Connexion"
                            },
                            {
                                "entity": f"sensor.{device_id}_output_type",
                                "name": "Mode de sortie"
                            }
                        ]
                    },
                    {
                        "type": "sensor",
                        "entity": f"sensor.{device_id}_battery_temperature",
                        "name": "Température",
                        "icon": "mdi:thermometer",
                        "graph": "line"
                    }
                ]
            },
            {
                "type": "history-graph",
                "title": "Historique des Puissances",
                "hours_to_show": 24,
                "entities": [
                    {
                        "entity": f"sensor.{device_id}_solar_power",
                        "name": "Solaire 1"
                    },
                    {
                        "entity": f"sensor.{device_id}_solar_power_2",
                        "name": "Solaire 2"
                    },
                    {
                        "entity": f"sensor.{device_id}_output_power",
                        "name": "Sortie"
                    }
                ]
            }
        ]
    }

    try:
        # Ajouter la vue à la configuration Lovelace existante
        await hass.services.async_call(
            "lovelace",
            "save_config",
            {
                "config": {
                    "views": [view_config]
                }
            }
        )
        _LOGGER.info("Vue Lovelace Storcube créée avec succès")
    except Exception as e:
        _LOGGER.error("Erreur lors de la création de la vue Lovelace: %s", str(e))

class StorcubeBatterySensor(SensorEntity):
    """Capteur pour les données de la batterie solaire."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._config = config
        self._websocket_data = {}
        self._rest_data = {}
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Gérer la mise à jour de l'état depuis les différentes sources."""
        try:
            if "websocket_data" in payload:
                self._websocket_data = payload["websocket_data"]
                self._update_value_from_sources()
            elif "rest_data" in payload:
                rest_data = payload["rest_data"]
                # Créer une structure compatible avec le format WebSocket
                websocket_format = {
                    "list": [{
                        "outputType": rest_data.get("outputType"),
                        "equipId": rest_data.get("equipId"),
                        "reserved": rest_data.get("reserved"),
                        "outputPower": rest_data.get("outputPower"),
                        "workStatus": rest_data.get("workStatus"),
                        "rgOnline": rest_data.get("fgOnline"),
                        "mainEquipOnline": rest_data.get("mainEquipOnline"),
                        "equipModelCode": rest_data.get("equipModelCode"),
                        "version": rest_data.get("version", ""),
                        "isWork": 1 if rest_data.get("workStatus") == 1 else 0,
                        "errorCode": rest_data.get("errorCode", 0),
                        "operatingMode": rest_data.get("operatingMode", 0)
                    }]
                }
                self._websocket_data = websocket_format
                self._update_value_from_sources()
            elif isinstance(payload, dict) and ("list" in payload or "totalPv1power" in payload):
                self._websocket_data = payload
                self._update_value_from_sources()
            else:
                _LOGGER.debug("Format de données non reconnu: %s", payload)
        except Exception as e:
            _LOGGER.error("Erreur lors de la mise à jour du capteur %s: %s", self.name, str(e))

    def _update_value_from_sources(self):
        """Mettre à jour la valeur en fonction des sources disponibles."""
        # À implémenter dans les classes enfants
        pass

class StorcubeBatteryLevelSensor(StorcubeBatterySensor):
    """Représentation du niveau de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialiser le capteur."""
        super().__init__(config)
        self._attr_name = "Niveau Batterie Storcube"
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_level"
        self._attr_icon = "mdi:battery-high"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                if "soc" in equip:
                    self._attr_native_value = equip["soc"]
                    self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery level: %s", e)

class StorcubeBatteryPowerSensor(StorcubeBatterySensor):
    """Représentation de la puissance de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Puissance Batterie Storcube"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_power"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                if "invPower" in equip:
                    self._attr_native_value = equip["invPower"]
                    self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery power: %s", e)

class StorcubeBatteryThresholdSensor(StorcubeBatterySensor):
    """Représentation du seuil de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Seuil Batterie Storcube"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_threshold"
        self._attr_icon = "mdi:battery-charging-medium"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                if "reserved" in equip:
                    self._attr_native_value = equip["reserved"]
                    self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery threshold: %s", e)

class StorcubeBatteryTemperatureSensor(StorcubeBatterySensor):
    """Représentation de la température de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Température Batterie Storcube"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_temperature"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                self._attr_native_value = equip.get("temp")
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery temperature: %s", e)
            _LOGGER.debug("Payload reçu: %s", payload)

class StorcubeBatteryEnergySensor(SensorEntity):
    """Représentation de l'énergie de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Énergie Batterie Storcube"
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_energy"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("battery_energy")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery energy: %s", e)

class StorcubeBatteryCapacityWhSensor(SensorEntity):
    """Représentation de la capacité de la batterie en Wh."""

    def __init__(self, config: ConfigType) -> None:
        """Initialiser le capteur."""
        self._attr_name = "Capacité Batterie Storcube (Wh)"
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY_STORAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_capacity_wh"
        self._config = config
        self._attr_native_value = None
        self._attr_icon = "mdi:battery-charging"

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Gérer la mise à jour de l'état."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                self._attr_native_value = float(equip.get("capacity", 0))
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery capacity (Wh): %s", e)

class StorcubeBatteryHealthSensor(SensorEntity):
    """Représentation de la santé de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Santé Batterie Storcube"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_health"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                if "capacity" in equip and "totalCapacity" in payload:
                    current_capacity = float(equip["capacity"])
                    total_capacity = float(payload["totalCapacity"])
                    if total_capacity > 0:
                        health = (current_capacity / total_capacity) * 100
                        self._attr_native_value = round(health, 1)
                    else:
                        _LOGGER.warning("Capacité totale est 0")
                        self._attr_native_value = None
                else:
                    _LOGGER.warning("Données de capacité non trouvées dans le payload")
                    self._attr_native_value = None
            else:
                _LOGGER.warning("Structure de payload invalide pour la santé de la batterie: %s", payload)
                self._attr_native_value = None
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery health: %s", e)
            _LOGGER.debug("Payload reçu: %s", payload)

class StorcubeBatteryStatusSensor(SensorEntity):
    """Représentation de l'état de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "État Batterie Storcube"
        self._attr_device_class = None
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_status"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                # Prendre le premier équipement de la liste
                equip = payload["list"][0]
                if "isWork" in equip:
                    self._attr_native_value = 'online' if equip["isWork"] == 1 else 'offline'
                else:
                    _LOGGER.warning("isWork non trouvé dans l'équipement: %s", equip)
                    self._attr_native_value = 'unknown'
            else:
                _LOGGER.warning("Structure de payload invalide: %s", payload)
                self._attr_native_value = 'unknown'
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery status: %s", e)
            _LOGGER.debug("Payload reçu: %s", payload)

class StorcubeSolarPowerSensor(StorcubeBatterySensor):
    """Représentation de la puissance solaire."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Puissance Solaire Storcube"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_solar_power"
        self._attr_icon = "mdi:solar-power"
        self._attr_suggested_display_precision = 1
        self._attr_has_entity_name = True

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data:
                if "totalPv1power" in self._websocket_data:
                    self._attr_native_value = self._websocket_data["totalPv1power"]
                elif "list" in self._websocket_data and self._websocket_data["list"]:
                    equip = self._websocket_data["list"][0]
                    if "pv1power" in equip:
                        self._attr_native_value = equip["pv1power"]
                
                # Ajouter des attributs pour le dashboard Énergie
                self._attr_extra_state_attributes = {
                    "last_reset": None,
                    "is_solar_production": True
                }
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating solar power: %s", e)

class StorcubeSolarEnergySensor(StorcubeBatterySensor):
    """Représentation de l'énergie solaire produite."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Énergie Solaire Storcube"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_solar_energy"
        self._attr_icon = "mdi:solar-power"
        self._attr_suggested_display_precision = 2
        self._last_power = 0
        self._last_update_time = None
        self._attr_native_value = 0

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data:
                current_power = 0
                if "totalPv1power" in self._websocket_data:
                    current_power = self._websocket_data["totalPv1power"]
                elif "list" in self._websocket_data and self._websocket_data["list"]:
                    equip = self._websocket_data["list"][0]
                    current_power = equip.get("pv1power", 0)

                current_time = datetime.now()
                
                if self._last_update_time is not None and current_power > 0:
                    time_diff = (current_time - self._last_update_time).total_seconds() / 3600
                    energy_increment = ((self._last_power + current_power) / 2) * time_diff / 1000
                    
                    if self._attr_native_value is None:
                        self._attr_native_value = energy_increment
                    else:
                        self._attr_native_value += energy_increment
                
                self._last_power = current_power
                self._last_update_time = current_time
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating solar energy: %s", e)

class StorcubeSolarPowerSensor2(StorcubeBatterySensor):
    """Représentation de la puissance solaire du deuxième panneau."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Puissance Solaire 2 Storcube"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_solar_power_2"
        self._attr_icon = "mdi:solar-power"
        self._attr_suggested_display_precision = 1
        self._attr_has_entity_name = True

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data:
                if "totalPv2power" in self._websocket_data:
                    self._attr_native_value = self._websocket_data["totalPv2power"]
                elif "list" in self._websocket_data and self._websocket_data["list"]:
                    equip = self._websocket_data["list"][0]
                    if "pv2power" in equip:
                        self._attr_native_value = equip["pv2power"]
                
                # Ajouter des attributs pour le dashboard Énergie
                self._attr_extra_state_attributes = {
                    "last_reset": None,
                    "is_solar_production": True
                }
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating solar power 2: %s", e)

class StorcubeSolarEnergySensor2(StorcubeBatterySensor):
    """Représentation de l'énergie solaire produite par le deuxième panneau."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Énergie Solaire 2 Storcube"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_solar_energy_2"
        self._attr_icon = "mdi:solar-power"
        self._attr_suggested_display_precision = 2
        self._last_power = 0
        self._last_update_time = None
        self._attr_native_value = 0

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data:
                current_power = 0
                if "totalPv2power" in self._websocket_data:
                    current_power = self._websocket_data["totalPv2power"]
                elif "list" in self._websocket_data and self._websocket_data["list"]:
                    equip = self._websocket_data["list"][0]
                    current_power = equip.get("pv2power", 0)

                current_time = datetime.now()
                
                if self._last_update_time is not None and current_power > 0:
                    time_diff = (current_time - self._last_update_time).total_seconds() / 3600
                    energy_increment = ((self._last_power + current_power) / 2) * time_diff / 1000
                    
                    if self._attr_native_value is None:
                        self._attr_native_value = energy_increment
                    else:
                        self._attr_native_value += energy_increment
                
                self._last_power = current_power
                self._last_update_time = current_time
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating solar energy 2: %s", e)

class StorcubeOutputPowerSensor(StorcubeBatterySensor):
    """Représentation de la puissance de sortie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Puissance Sortie Storcube"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_output_power"
        self._attr_icon = "mdi:flash"
        self._attr_suggested_display_precision = 1
        self._attr_has_entity_name = True

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data:
                if "totalInvPower" in self._websocket_data:
                    self._attr_native_value = self._websocket_data["totalInvPower"]
                elif "list" in self._websocket_data and self._websocket_data["list"]:
                    equip = self._websocket_data["list"][0]
                    if "invPower" in equip:
                        self._attr_native_value = equip["invPower"]
                
                # Ajouter des attributs pour le dashboard Énergie
                self._attr_extra_state_attributes = {
                    "last_reset": None,
                    "is_battery_output": True
                }
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating output power: %s", e)

class StorcubeOutputEnergySensor(StorcubeBatterySensor):
    """Représentation de l'énergie de sortie cumulée."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Énergie Sortie Storcube"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_output_energy"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_suggested_display_precision = 2
        self._last_power = 0
        self._last_update_time = None
        self._attr_native_value = 0

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data:
                current_power = 0
                if "totalInvPower" in self._websocket_data:
                    current_power = self._websocket_data["totalInvPower"]
                elif "list" in self._websocket_data and self._websocket_data["list"]:
                    equip = self._websocket_data["list"][0]
                    current_power = equip.get("invPower", 0)

                current_time = datetime.now()
                
                if self._last_update_time is not None and current_power > 0:
                    time_diff = (current_time - self._last_update_time).total_seconds() / 3600
                    energy_increment = ((self._last_power + current_power) / 2) * time_diff / 1000
                    
                    if self._attr_native_value is None:
                        self._attr_native_value = energy_increment
                    else:
                        self._attr_native_value += energy_increment
                
                self._last_power = current_power
                self._last_update_time = current_time
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating output energy: %s", e)

class StorcubeStatusSensor(StorcubeBatterySensor):
    """Représentation de l'état du système."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "État Système Storcube"
        self._attr_device_class = None
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_status"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                self._attr_native_value = "En marche" if equip.get("isWork") == 1 else "Arrêté"
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating status: %s", e)

class StorcubeModelSensor(StorcubeBatterySensor):
    """Représentation du modèle de l'équipement."""
    
    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Modèle"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_model"
        self._attr_icon = "mdi:information"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                if "equipModelCode" in equip:
                    self._attr_native_value = equip["equipModelCode"]
                    self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating model: %s", e)

class StorcubeSerialNumberSensor(StorcubeBatterySensor):
    """Représentation du numéro de série."""
    
    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Numéro de série"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_serial_number"
        self._attr_icon = "mdi:barcode"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                if "equipId" in equip:
                    self._attr_native_value = equip["equipId"]
                    self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating serial number: %s", e)

class StorcubeOutputTypeSensor(StorcubeBatterySensor):
    """Représentation du type de sortie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialiser le capteur."""
        super().__init__(config)
        self._attr_name = "Type de sortie"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_output_type"
        self._attr_icon = "mdi:power-plug"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                if "outputType" in equip:
                    output_type = equip["outputType"]
                    # Gérer le cas où output_type est une chaîne de caractères
                    if isinstance(output_type, str):
                        type_map = {
                            "manual": "Manuel",
                            "auto": "Automatique",
                            "eco": "Économique"
                        }
                        self._attr_native_value = type_map.get(output_type.lower(), output_type)
                    else:
                        # Gérer le cas où output_type est un nombre
                        type_map = {
                            0: "Normal",
                            1: "Économique",
                            2: "Performance"
                        }
                        self._attr_native_value = type_map.get(output_type, f"Mode {output_type}")
                    self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating output type: %s", e)

class StorcubeReservedSensor(StorcubeBatterySensor):
    """Capteur pour le niveau de réserve."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Niveau de réserve"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_reserved"
        self._attr_native_value = None
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_icon = "mdi:battery-charging-medium"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                if "reserved" in equip:
                    self._attr_native_value = equip["reserved"]
                    self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating reserved level: %s", e)

class StorcubeWorkStatusSensor(StorcubeBatterySensor):
    """Représentation de l'état de fonctionnement."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "État de fonctionnement"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_work_status"
        self._attr_icon = "mdi:power"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                work_status = equip.get("workStatus")
                
                status_map = {
                    0: "Arrêté",
                    1: "En fonctionnement",
                    2: "En erreur"
                }
                
                self._attr_native_value = status_map.get(work_status, "Inconnu")
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating work status: %s", e)

class StorcubeOnlineSensor(StorcubeBatterySensor):
    """Représentation de l'état de connexion."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "État de connexion"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_online_status"
        self._attr_icon = "mdi:wifi"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                rg_online = equip.get("rgOnline")
                main_equip_online = equip.get("mainEquipOnline")
                
                if rg_online == 1 and main_equip_online == 1:
                    self._attr_native_value = "En ligne"
                else:
                    self._attr_native_value = "Hors ligne"
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating online status: %s", e)

class StorcubeErrorCodeSensor(StorcubeBatterySensor):
    """Représentation du code d'erreur."""
    
    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Code d'erreur"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_error_code"
        self._attr_icon = "mdi:alert-circle"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                if "errorCode" in equip:
                    self._attr_native_value = equip["errorCode"]
                    self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating error code: %s", e)

class StorcubeOperatingModeSensor(StorcubeBatterySensor):
    """Représentation du mode de fonctionnement."""
    
    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Mode de fonctionnement"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_operating_mode"
        self._attr_icon = "mdi:cog"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                if "operatingMode" in equip:
                    mode = equip["operatingMode"]
                    mode_map = {
                        0: "Normal",
                        1: "Économie",
                        2: "Boost",
                        3: "Veille"
                    }
                    self._attr_native_value = mode_map.get(mode, f"Mode {mode}")
                    self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating operating mode: %s", e)

class StorcubeFirmwareVersionSensor(StorcubeBatterySensor):
    """Représentation de la version du firmware."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Version Firmware Storcube"
        self._attr_device_class = None
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_firmware"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data and "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
                if "version" in equip:
                    self._attr_native_value = equip["version"]
                    self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating firmware version: %s", e)

class StorcubeSolarEnergyTotalSensor(StorcubeBatterySensor):
    """Représentation de l'énergie solaire totale des deux panneaux."""
    
    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Énergie Solaire Totale Storcube"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_solar_energy_total"
        self._attr_icon = "mdi:solar-power"
        self._attr_suggested_display_precision = 2
        self._last_power_pv1 = 0
        self._last_power_pv2 = 0
        self._last_update_time = None
        self._attr_native_value = 0

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            if self._websocket_data:
                current_power_pv1 = 0
                current_power_pv2 = 0
                
                if "totalPv1power" in self._websocket_data and "totalPv2power" in self._websocket_data:
                    current_power_pv1 = self._websocket_data["totalPv1power"]
                    current_power_pv2 = self._websocket_data["totalPv2power"]
                elif "list" in self._websocket_data and self._websocket_data["list"]:
                    equip = self._websocket_data["list"][0]
                    current_power_pv1 = equip.get("pv1power", 0)
                    current_power_pv2 = equip.get("pv2power", 0)

                total_current_power = current_power_pv1 + current_power_pv2
                total_last_power = self._last_power_pv1 + self._last_power_pv2
                current_time = datetime.now()
                
                if self._last_update_time is not None and total_current_power > 0:
                    time_diff = (current_time - self._last_update_time).total_seconds() / 3600
                    energy_increment = ((total_last_power + total_current_power) / 2) * time_diff / 1000
                    
                    if self._attr_native_value is None:
                        self._attr_native_value = energy_increment
                    else:
                        self._attr_native_value += energy_increment
                
                self._last_power_pv1 = current_power_pv1
                self._last_power_pv2 = current_power_pv2
                self._last_update_time = current_time
                
                self._attr_extra_state_attributes = {
                    "last_reset": None,
                    "is_solar_production": True,
                    "pv1_power": current_power_pv1,
                    "pv2_power": current_power_pv2,
                    "total_power": total_current_power
                }
                
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating total solar energy: %s", e)

async def websocket_to_mqtt(hass: HomeAssistant, config: ConfigType, config_entry: ConfigEntry) -> None:
    """Handle websocket connection and forward data to MQTT."""
    while True:
        try:
            headers = {
                'Content-Type': 'application/json',
                'accept-language': 'fr-FR',
                'user-agent': 'Mozilla/5.0 (Linux; Android 11; SM-A202F Build/RP1A.200720.012; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/132.0.6834.163 Mobile Safari/537.36 uni-app Html5Plus/1.0 (Immersed/24.0)'
            }
            
            payload = {
                "appCode": config[CONF_APP_CODE],
                "loginName": config[CONF_LOGIN_NAME],
                "password": config[CONF_AUTH_PASSWORD]
            }

            _LOGGER.debug("Tentative de connexion à %s", TOKEN_URL)
            try:
                connector = aiohttp.TCPConnector(ssl=False)
                timeout = aiohttp.ClientTimeout(total=30)
                
                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    async with session.post(
                        TOKEN_URL,
                        headers=headers,
                        json=payload
                    ) as response:
                        response_text = await response.text()
                        _LOGGER.debug("Réponse brute: %s", response_text)
                        
                        token_data = json.loads(response_text)
                        if token_data.get("code") != 200:
                            _LOGGER.error("Échec de l'authentification: %s", token_data.get("message", "Erreur inconnue"))
                            raise Exception("Échec de l'authentification")
                        token = token_data["data"]["token"]
                        _LOGGER.info("Token obtenu avec succès")

                        # Connect to websocket with proper headers
                        uri = f"{WS_URI}{token}"
                        _LOGGER.debug("Connexion WebSocket à %s", uri)

                        websocket_headers = {
                            "Authorization": token,
                            "Content-Type": "application/json",
                            "accept-language": "fr-FR",
                            "user-agent": "Mozilla/5.0 (Linux; Android 11; SM-A202F Build/RP1A.200720.012; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/132.0.6834.163 Mobile Safari/537.36 uni-app Html5Plus/1.0 (Immersed/24.0)"
                        }

                        async with websockets.connect(
                            uri,
                            additional_headers=websocket_headers,
                            ping_interval=15,
                            ping_timeout=5
                        ) as websocket:
                            _LOGGER.info("Connexion WebSocket établie")
                            
                            # Send initial request
                            request_data = {"reportEquip": [config[CONF_DEVICE_ID]]}
                            await websocket.send(json.dumps(request_data))
                            _LOGGER.debug("Requête envoyée: %s", request_data)

                            last_heartbeat = datetime.now()
                            while True:
                                try:
                                    message = await asyncio.wait_for(websocket.recv(), timeout=30)
                                    last_heartbeat = datetime.now()
                                    _LOGGER.debug("Message WebSocket reçu brut: %s", message)

                                    if message.strip():
                                        try:
                                            json_data = json.loads(message)
                                            
                                            # Ignorer silencieusement les messages "SUCCESS"
                                            if json_data == "SUCCESS":
                                                _LOGGER.debug("Message de confirmation 'SUCCESS' reçu")
                                                continue
                                                
                                            # Ignorer les dictionnaires vides
                                            if not json_data:
                                                _LOGGER.debug("Message vide reçu")
                                                continue
                                            
                                            if isinstance(json_data, dict):
                                                # Log toutes les clés du message
                                                _LOGGER.debug("Structure du message reçu: %s", json_data)
                                                
                                                # Vérifier si c'est une réponse d'API REST
                                                if "code" in json_data and "data" in json_data and json_data["code"] == 200:
                                                    data_list = json_data.get("data", [])
                                                    if data_list and isinstance(data_list, list):
                                                        equip_data = data_list[0]
                                                        _LOGGER.info("Mise à jour des capteurs avec les données de l'API: %s", equip_data)
                                                        for sensor in hass.data[DOMAIN][config_entry.entry_id]["sensors"]:
                                                            sensor.handle_state_update(equip_data)
                                                # Vérifier si c'est une réponse WebSocket avec l'ID de l'équipement
                                                elif config[CONF_DEVICE_ID] in json_data:
                                                    equip_data = json_data[config[CONF_DEVICE_ID]]
                                                    _LOGGER.info("Mise à jour des capteurs avec les données WebSocket: %s", equip_data)
                                                    for sensor in hass.data[DOMAIN][config_entry.entry_id]["sensors"]:
                                                        sensor.handle_state_update(equip_data)
                                                else:
                                                    # Extraire les données d'équipement pour le format WebSocket
                                                    equip_data = next(iter(json_data.values()), {})
                                                    
                                                    # Vérifier si les données d'équipement sont valides
                                                    if equip_data and isinstance(equip_data, dict):
                                                        # Si les données sont dans la liste
                                                        if "list" in equip_data and equip_data["list"]:
                                                            _LOGGER.info("Mise à jour des capteurs avec les données de la liste: %s", equip_data)
                                                            for sensor in hass.data[DOMAIN][config_entry.entry_id]["sensors"]:
                                                                sensor.handle_state_update(equip_data)
                                                        # Si les données sont au niveau racine
                                                        else:
                                                            _LOGGER.info("Mise à jour des capteurs avec les données racines: %s", equip_data)
                                                            for sensor in hass.data[DOMAIN][config_entry.entry_id]["sensors"]:
                                                                sensor.handle_state_update(equip_data)
                                                    else:
                                                        _LOGGER.debug("Message reçu sans données d'équipement valides")
                                            else:
                                                _LOGGER.debug("Message reçu dans un format inattendu: %s", type(json_data))
                                        except json.JSONDecodeError as e:
                                            _LOGGER.warning("Impossible de décoder le message JSON: %s", e)
                                            continue

                                except asyncio.TimeoutError:
                                    time_since_last = (datetime.now() - last_heartbeat).total_seconds()
                                    _LOGGER.debug("Timeout WebSocket après %d secondes, envoi heartbeat...", time_since_last)
                                    try:
                                        await websocket.send(json.dumps(request_data))
                                        _LOGGER.debug("Heartbeat envoyé avec succès")
                                    except Exception as e:
                                        _LOGGER.warning("Échec de l'envoi du heartbeat: %s", str(e))
                                        break
                                    continue

            except Exception as e:
                _LOGGER.error("Erreur inattendue: %s", str(e))
                await asyncio.sleep(5)
                continue

        except Exception as e:
            _LOGGER.error("Erreur de connexion: %s", str(e))
            await asyncio.sleep(5)

async def output_api_to_mqtt(hass: HomeAssistant, config: ConfigType, config_entry: ConfigEntry) -> None:
    """Handle output API connection and forward data to MQTT."""
    while True:
        try:
            headers = {
                'Content-Type': 'application/json',
                'accept-language': 'fr-FR',
                'user-agent': 'Mozilla/5.0 (Linux; Android 11; SM-A202F Build/RP1A.200720.012; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/132.0.6834.163 Mobile Safari/537.36 uni-app Html5Plus/1.0 (Immersed/24.0)'
            }
            
            payload = {
                "appCode": config[CONF_APP_CODE],
                "loginName": config[CONF_LOGIN_NAME],
                "password": config[CONF_AUTH_PASSWORD]
            }

            _LOGGER.debug("Tentative de connexion à %s", TOKEN_URL)
            try:
                connector = aiohttp.TCPConnector(ssl=False)
                timeout = aiohttp.ClientTimeout(total=30)
                
                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    async with session.post(
                        TOKEN_URL,
                        headers=headers,
                        json=payload
                    ) as response:
                        response_text = await response.text()
                        _LOGGER.debug("Réponse brute: %s", response_text)
                        
                        token_data = json.loads(response_text)
                        if token_data.get("code") != 200:
                            _LOGGER.error("Échec de l'authentification: %s", token_data.get("message", "Erreur inconnue"))
                            raise Exception("Échec de l'authentification")
                        token = token_data["data"]["token"]
                        _LOGGER.info("Token obtenu avec succès")

                        while True:
                            try:
                                # Appel à l'API output avec le token dans les headers
                                output_url = f"{OUTPUT_URL}{config[CONF_DEVICE_ID]}"
                                _LOGGER.debug("Appel à l'API output: %s", output_url)
                                
                                headers["Authorization"] = token
                                async with session.get(
                                    output_url,
                                    headers=headers
                                ) as response:
                                    response_text = await response.text()
                                    _LOGGER.debug("Réponse API output brute: %s", response_text)
                                    
                                    try:
                                        json_data = json.loads(response_text)
                                        if json_data.get("code") == 200 and "data" in json_data:
                                            data_list = json_data.get("data", [])
                                            if data_list and isinstance(data_list, list):
                                                equip_data = data_list[0]
                                                _LOGGER.info("Mise à jour des capteurs avec les données de l'API output: %s", equip_data)
                                                for sensor in hass.data[DOMAIN][config_entry.entry_id]["sensors"]:
                                                    sensor.handle_state_update({"rest_data": equip_data})
                                    except json.JSONDecodeError as e:
                                        _LOGGER.warning("Impossible de décoder la réponse JSON de l'API output: %s", e)
                                
                                # Attendre 30 secondes avant le prochain appel
                                await asyncio.sleep(30)
                                
                            except Exception as e:
                                _LOGGER.error("Erreur lors de l'appel à l'API output: %s", str(e))
                                await asyncio.sleep(5)
                                continue

            except Exception as e:
                _LOGGER.error("Erreur inattendue: %s", str(e))
                await asyncio.sleep(5)
                continue

        except Exception as e:
            _LOGGER.error("Erreur de connexion: %s", str(e))
            await asyncio.sleep(5) 
