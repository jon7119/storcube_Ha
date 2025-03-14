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
        #StorcubeBatteryThresholdSensor(config),
        StorcubeBatteryTemperatureSensor(config),
        StorcubeBatteryCapacitySensor(config),
        #StorcubeBatteryHealthSensor(config),
        StorcubeBatteryStatusSensor(config),
        
        # Capteurs solaires
        StorcubeSolarPowerSensor(config),  # Gardé
        StorcubeSolarEnergySensor(config),  # Réactivé pour le dashboard Énergie
        
        # Capteurs solaires pour le deuxième panneau
        StorcubeSolarPowerSensor2(config),  # Gardé
        StorcubeSolarEnergySensor2(config),  # Réactivé pour le dashboard Énergie
        
        # Capteur d'énergie solaire totale
        StorcubeSolarEnergyTotalSensor(config),  # Gardé
        
        # Capteurs de sortie
        StorcubeOutputPowerSensor(config),
        StorcubeOutputEnergySensor(config),  # Ajouté pour le dashboard Énergie
        
        # Capteurs système
        StorcubeStatusSensor(config),
        #StorcubeFirmwareVersionSensor(config),
    ]

    async_add_entities(sensors)

    # Store sensors in hass.data
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][config_entry.entry_id] = {"sensors": sensors}

    # Créer la vue Lovelace
    await create_lovelace_view(hass, config_entry)

    # Start websocket connection
    asyncio.create_task(websocket_to_mqtt(hass, config, config_entry))

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
                        "entity": f"sensor.{device_id}_battery_health",
                        "name": "Santé Batterie",
                        "min": 0,
                        "max": 100,
                        "severity": {
                            "green": 80,
                            "yellow": 60,
                            "red": 40
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
                        "type": "sensor",
                        "entity": f"sensor.{device_id}_battery_temperature",
                        "name": "Température",
                        "icon": "mdi:thermometer",
                        "graph": "line"
                    },
                    {
                        "type": "entity",
                        "entity": f"sensor.{device_id}_battery_status",
                        "name": "État",
                        "icon": "mdi:battery-check"
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
        """Initialiser le capteur."""
        self._attr_name = f"Batterie {config['equipId']}"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config['equipId']}_battery"
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Gérer la mise à jour de l'état."""
        # Extraire les données pertinentes du payload
        self._attr_state = payload['list'][0]['invPower']  # Puissance de l'inverseur
        self._attr_extra_state_attributes = {
            "totalPv1power": payload['totalPv1power'],  # Puissance totale PV1
            "totalInvPower": payload['totalInvPower'],  # Puissance totale de l'inverseur
            "temp": payload['list'][0]['temp'],  # Température
            "pv1power": payload['list'][0]['pv1power'],  # Puissance PV1
            "soc": payload['list'][0]['soc'],  # État de charge
            "pv2power": payload['list'][0]['pv2power'],  # Puissance PV2
            "capacity": payload['list'][0]['capacity'],  # Capacité
            "isWork": payload['list'][0]['isWork'],  # État de fonctionnement
            "plugPower": payload['plugPower'],  # Puissance de la prise
            "totalCapacity": payload['totalCapacity'],  # Capacité totale
            "mainEquipId": payload['mainEquipId'],  # ID de l'équipement principal
            "totalPv2power": payload['totalPv2power'],  # Puissance totale PV2
        }
        self.async_write_ha_state()

class StorcubeBatteryLevelSensor(SensorEntity):
    """Représentation du niveau de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialiser le capteur."""
        self._attr_name = "Niveau Batterie Storcube"
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_level"
        self._config = config
        self._attr_native_value = None
        self._attr_icon = "mdi:battery-high"  # Icône

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Gérer la mise à jour de l'état."""
        try:
            self._attr_native_value = payload['list'][0]['soc']  # État de charge
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery level: %s", e)

class StorcubeBatteryPowerSensor(SensorEntity):
    """Représentation de la puissance de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Puissance Batterie Storcube"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_power"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                self._attr_native_value = equip.get("invPower")
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery power: %s", e)
            _LOGGER.debug("Payload reçu: %s", payload)

class StorcubeBatteryThresholdSensor(SensorEntity):
    """Représentation du seuil de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Seuil Batterie Storcube"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_threshold"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                # Le seuil est le niveau de batterie minimum (à implémenter si disponible)
                self._attr_native_value = None
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery threshold: %s", e)

class StorcubeBatteryTemperatureSensor(SensorEntity):
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

class StorcubeBatteryCapacitySensor(SensorEntity):
    """Représentation de la capacité de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialiser le capteur."""
        self._attr_name = "Capacité Batterie Storcube"
        self._attr_native_unit_of_measurement = "Wh"  # Unité de mesure
        self._attr_device_class = SensorDeviceClass.BATTERY  # Classe d'entité pour la batterie
        self._attr_state_class = SensorStateClass.MEASUREMENT  # Classe d'état
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_capacity"
        self._config = config
        self._attr_native_value = None
        self._attr_icon = "mdi:battery-charging"


    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Gérer la mise à jour de l'état."""
        try:
            self._attr_native_value = payload['list'][0]['capacity']  # Capacité de la batterie
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery capacity: %s", e)

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

class StorcubeSolarPowerSensor(SensorEntity):
    """Représentation de la puissance solaire."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Puissance Solaire Storcube"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_solar_power"
        self._config = config
        self._attr_native_value = None
        self._attr_icon = "mdi:solar-power"
        # Attributs pour le dashboard Énergie
        self._attr_suggested_display_precision = 1
        self._attr_has_entity_name = True

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                self._attr_native_value = equip.get("pv1power")
                # Ajouter des attributs supplémentaires pour le dashboard Énergie
                self._attr_extra_state_attributes = {
                    "last_reset": None,
                    "is_solar_production": True  # Attribut personnalisé pour identifier cette entité comme production solaire
                }
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating solar power: %s", e)
            _LOGGER.debug("Payload reçu: %s", payload)

class StorcubeSolarEnergySensor(SensorEntity):
    """Représentation de l'énergie solaire produite."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Énergie Solaire Storcube"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_solar_energy"
        self._config = config
        self._attr_native_value = 0
        self._attr_icon = "mdi:solar-power"
        # Attributs pour le dashboard Énergie
        self._attr_suggested_display_precision = 2
        self._last_power = 0
        self._last_update_time = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                # Calculer l'énergie à partir de la puissance
                current_power = equip.get("pv1power", 0)
                current_time = datetime.now()
                
                # Si nous avons une mesure précédente, calculer l'énergie
                if self._last_update_time is not None and current_power > 0:
                    # Calculer le temps écoulé en heures
                    time_diff = (current_time - self._last_update_time).total_seconds() / 3600
                    # Calculer l'énergie en kWh (moyenne des puissances * temps)
                    energy_increment = ((self._last_power + current_power) / 2) * time_diff / 1000
                    # Ajouter à la valeur totale
                    if self._attr_native_value is None:
                        self._attr_native_value = energy_increment
                    else:
                        self._attr_native_value += energy_increment
                
                # Mettre à jour les valeurs pour le prochain calcul
                self._last_power = current_power
                self._last_update_time = current_time
                
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating solar energy: %s", e)
            _LOGGER.debug("Payload reçu: %s", payload)

class StorcubeSolarPowerSensor2(SensorEntity):
    """Représentation de la puissance solaire du deuxième panneau."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Puissance Solaire 2 Storcube"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_solar_power_2"
        self._config = config
        self._attr_native_value = None
        self._attr_icon = "mdi:solar-power"
        # Attributs pour le dashboard Énergie
        self._attr_suggested_display_precision = 1
        self._attr_has_entity_name = True
        
    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                self._attr_native_value = equip.get("pv2power")
                # Ajouter des attributs supplémentaires pour le dashboard Énergie
                self._attr_extra_state_attributes = {
                    "last_reset": None,
                    "is_solar_production": True  # Attribut personnalisé pour identifier cette entité comme production solaire
                }
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating solar power 2: %s", e)
            _LOGGER.debug("Payload reçu: %s", payload)

class StorcubeSolarEnergySensor2(SensorEntity):
    """Représentation de l'énergie solaire produite par le deuxième panneau."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Énergie Solaire 2 Storcube"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_solar_energy_2"
        self._config = config
        self._attr_native_value = 0
        self._attr_icon = "mdi:solar-power"
        # Attributs pour le dashboard Énergie
        self._attr_suggested_display_precision = 2
        self._last_power = 0
        self._last_update_time = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                # Calculer l'énergie à partir de la puissance
                current_power = equip.get("pv2power", 0)
                current_time = datetime.now()
                
                # Si nous avons une mesure précédente, calculer l'énergie
                if self._last_update_time is not None and current_power > 0:
                    # Calculer le temps écoulé en heures
                    time_diff = (current_time - self._last_update_time).total_seconds() / 3600
                    # Calculer l'énergie en kWh (moyenne des puissances * temps)
                    energy_increment = ((self._last_power + current_power) / 2) * time_diff / 1000
                    # Ajouter à la valeur totale
                    if self._attr_native_value is None:
                        self._attr_native_value = energy_increment
                    else:
                        self._attr_native_value += energy_increment
                
                # Mettre à jour les valeurs pour le prochain calcul
                self._last_power = current_power
                self._last_update_time = current_time
                
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating solar energy 2: %s", e)
            _LOGGER.debug("Payload reçu: %s", payload)

class StorcubeOutputPowerSensor(SensorEntity):
    """Représentation de la puissance de sortie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Puissance Sortie Storcube"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_output_power"
        self._config = config
        self._attr_native_value = None
        self._attr_icon = "mdi:flash"
        # Attributs pour le dashboard Énergie
        self._attr_suggested_display_precision = 1
        self._attr_has_entity_name = True

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict):
                self._attr_native_value = payload.get("totalInvPower")
                # Ajouter des attributs supplémentaires pour le dashboard Énergie
                self._attr_extra_state_attributes = {
                    "last_reset": None,  # Important pour les compteurs d'énergie
                    "is_battery_output": True  # Attribut personnalisé pour identifier cette entité comme sortie de batterie
                }
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating output power: %s", e)
            _LOGGER.debug("Payload reçu: %s", payload)

class StorcubeOutputEnergySensor(SensorEntity):
    """Représentation de l'énergie de sortie cumulée."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Énergie Sortie Storcube"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_output_energy"
        self._config = config
        self._attr_native_value = 0
        self._attr_icon = "mdi:lightning-bolt"
        # Attributs pour le dashboard Énergie
        self._attr_suggested_display_precision = 2
        self._last_power = 0
        self._last_update_time = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict):
                # Calculer l'énergie à partir de la puissance
                # Note: Ceci est une estimation simplifiée, idéalement l'appareil devrait fournir cette valeur
                current_power = payload.get("totalInvPower", 0)
                current_time = datetime.now()
                
                # Si nous avons une mesure précédente, calculer l'énergie
                if self._last_update_time is not None and current_power > 0:
                    # Calculer le temps écoulé en heures
                    time_diff = (current_time - self._last_update_time).total_seconds() / 3600
                    # Calculer l'énergie en kWh (moyenne des puissances * temps)
                    energy_increment = ((self._last_power + current_power) / 2) * time_diff / 1000
                    # Ajouter à la valeur totale
                    if self._attr_native_value is None:
                        self._attr_native_value = energy_increment
                    else:
                        self._attr_native_value += energy_increment
                
                # Mettre à jour les valeurs pour le prochain calcul
                self._last_power = current_power
                self._last_update_time = current_time
                
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating output energy: %s", e)
            _LOGGER.debug("Payload reçu: %s", payload)

class StorcubeStatusSensor(SensorEntity):
    """Représentation de l'état du système."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "État Système Storcube"
        self._attr_device_class = None
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_status"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                self._attr_native_value = "En marche" if equip.get("isWork") == 1 else "Arrêté"
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating status: %s", e)
            _LOGGER.debug("Payload reçu: %s", payload)

class StorcubeFirmwareVersionSensor(SensorEntity):
    """Représentation de la version du firmware."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Version Firmware Storcube"
        self._attr_device_class = None
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_firmware"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("firmware_version")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating firmware version: %s", e)

class StorcubeSolarEnergyTotalSensor(SensorEntity):
    """Représentation de l'énergie solaire totale des deux panneaux."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Énergie Solaire Totale Storcube"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR  # Changé en kWh pour être cohérent avec les autres capteurs
        self._attr_device_class = SensorDeviceClass.ENERGY  # Classe d'entité pour l'énergie
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING  # Classe d'état
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_solar_energy_total"
        self._config = config
        self._attr_native_value = 0  # Initialisé à 0 au lieu de None
        self._attr_icon = "mdi:solar-power"  # Icône
        # Attributs pour le dashboard Énergie
        self._attr_suggested_display_precision = 2
        self._last_power_pv1 = 0
        self._last_power_pv2 = 0
        self._last_update_time = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                
                # Récupérer les puissances actuelles des deux panneaux
                current_power_pv1 = equip.get("pv1power", 0)
                current_power_pv2 = equip.get("pv2power", 0)
                current_time = datetime.now()
                
                # Calculer la puissance totale
                total_current_power = current_power_pv1 + current_power_pv2
                total_last_power = self._last_power_pv1 + self._last_power_pv2
                
                # Si nous avons une mesure précédente, calculer l'énergie
                if self._last_update_time is not None and total_current_power > 0:
                    # Calculer le temps écoulé en heures
                    time_diff = (current_time - self._last_update_time).total_seconds() / 3600
                    # Calculer l'énergie en kWh (moyenne des puissances * temps)
                    energy_increment = ((total_last_power + total_current_power) / 2) * time_diff / 1000
                    # Ajouter à la valeur totale
                    if self._attr_native_value is None:
                        self._attr_native_value = energy_increment
                    else:
                        self._attr_native_value += energy_increment
                
                # Mettre à jour les valeurs pour le prochain calcul
                self._last_power_pv1 = current_power_pv1
                self._last_power_pv2 = current_power_pv2
                self._last_update_time = current_time
                
                # Ajouter des attributs supplémentaires pour le dashboard Énergie
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
            _LOGGER.debug("Payload reçu: %s", payload)

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
                                                
                                                # Extraire les données d'équipement
                                                equip_data = next(iter(json_data.values()), {})
                                                
                                                # Vérifier si les données d'équipement sont valides
                                                if equip_data and isinstance(equip_data, dict) and "list" in equip_data:
                                                    _LOGGER.info("Mise à jour des capteurs avec les données: %s", equip_data)
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
