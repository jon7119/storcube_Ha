"""Support for Storcube Battery Monitor sensors."""
from __future__ import annotations

import logging
import json
import asyncio
import aiohttp
import websockets
from datetime import datetime
from typing import Any, Optional

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
        StorcubeSceneInfoSensor(config),
        StorcubeSceneOutputTypeSensor(config),
        StorcubeSceneReservedSensor(config),
        StorcubeSceneOutputPowerSensor(config),
        StorcubeSceneWorkStatusSensor(config),
        StorcubeSceneIsOnlineSensor(config),
        StorcubeSceneEquipTypeSensor(config),
        StorcubeSceneBluetoothNameSensor(config),
        StorcubeSceneEquipModelCodeSensor(config),
        StorcubeSceneCreateTimeSensor(config),
    ]

    async_add_entities(sensors)

    # Store sensors in hass.data
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][config_entry.entry_id] = {"sensors": sensors}

    # Créer la vue Lovelace
    await create_lovelace_view(hass, config_entry)

    # Start websocket connection
    asyncio.create_task(websocket_to_mqtt(hass, config_entry, config))

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
        _LOGGER.debug("Capteur d'énergie solaire initialisé avec valeur: %s", self._attr_native_value)

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            _LOGGER.debug("Mise à jour du capteur d'énergie solaire avec payload: %s", payload)
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                # Calculer l'énergie à partir de la puissance
                current_power = equip.get("pv1power", 0)
                _LOGGER.debug("Puissance solaire actuelle: %s W", current_power)
                current_time = datetime.now()
                
                # Si nous avons une mesure précédente, calculer l'énergie
                if self._last_update_time is not None:
                    # Calculer le temps écoulé en heures
                    time_diff = (current_time - self._last_update_time).total_seconds() / 3600
                    _LOGGER.debug("Temps écoulé depuis dernière mise à jour: %s heures", time_diff)
                    
                    # Calculer l'énergie en kWh (moyenne des puissances * temps)
                    energy_increment = ((self._last_power + current_power) / 2) * time_diff / 1000
                    _LOGGER.debug("Incrément d'énergie calculé: %s kWh", energy_increment)
                    
                    # Ajouter à la valeur totale
                    if self._attr_native_value is None:
                        self._attr_native_value = energy_increment
                    else:
                        self._attr_native_value += energy_increment
                    
                    _LOGGER.debug("Nouvelle valeur d'énergie totale: %s kWh", self._attr_native_value)
                else:
                    _LOGGER.debug("Première mise à jour, initialisation du temps de référence")
                
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
        _LOGGER.debug("Capteur d'énergie de sortie initialisé avec valeur: %s", self._attr_native_value)

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            _LOGGER.debug("Mise à jour du capteur d'énergie de sortie avec payload: %s", payload)
            if isinstance(payload, dict):
                # Calculer l'énergie à partir de la puissance
                # Note: Ceci est une estimation simplifiée, idéalement l'appareil devrait fournir cette valeur
                current_power = payload.get("totalInvPower", 0)
                _LOGGER.debug("Puissance de sortie actuelle: %s W", current_power)
                current_time = datetime.now()
                
                # Si nous avons une mesure précédente, calculer l'énergie
                if self._last_update_time is not None:
                    # Calculer le temps écoulé en heures
                    time_diff = (current_time - self._last_update_time).total_seconds() / 3600
                    _LOGGER.debug("Temps écoulé depuis dernière mise à jour: %s heures", time_diff)
                    
                    # Calculer l'énergie en kWh (moyenne des puissances * temps)
                    energy_increment = ((self._last_power + current_power) / 2) * time_diff / 1000
                    _LOGGER.debug("Incrément d'énergie calculé: %s kWh", energy_increment)
                    
                    # Ajouter à la valeur totale
                    if self._attr_native_value is None:
                        self._attr_native_value = energy_increment
                    else:
                        self._attr_native_value += energy_increment
                    
                    _LOGGER.debug("Nouvelle valeur d'énergie totale: %s kWh", self._attr_native_value)
                else:
                    _LOGGER.debug("Première mise à jour, initialisation du temps de référence")
                
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
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_solar_energy_total"
        self._config = config
        self._attr_native_value = 0  # Initialisé à 0 au lieu de None
        self._attr_icon = "mdi:solar-power"
        # Attributs pour le dashboard Énergie
        self._attr_suggested_display_precision = 2
        self._last_power_pv1 = 0
        self._last_power_pv2 = 0
        self._last_update_time = None
        _LOGGER.debug("Capteur d'énergie solaire totale initialisé avec valeur: %s", self._attr_native_value)

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            _LOGGER.debug("Mise à jour du capteur d'énergie solaire totale avec payload: %s", payload)
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                
                # Récupérer les puissances actuelles des deux panneaux
                current_power_pv1 = equip.get("pv1power", 0)
                current_power_pv2 = equip.get("pv2power", 0)
                _LOGGER.debug("Puissances actuelles: PV1=%sW, PV2=%sW", current_power_pv1, current_power_pv2)
                current_time = datetime.now()
                
                # Calculer la puissance totale
                total_current_power = current_power_pv1 + current_power_pv2
                total_last_power = self._last_power_pv1 + self._last_power_pv2
                _LOGGER.debug("Puissance totale actuelle: %sW, Puissance totale précédente: %sW", 
                             total_current_power, total_last_power)
                
                # Si nous avons une mesure précédente, calculer l'énergie
                if self._last_update_time is not None:
                    # Calculer le temps écoulé en heures
                    time_diff = (current_time - self._last_update_time).total_seconds() / 3600
                    _LOGGER.debug("Temps écoulé depuis dernière mise à jour: %s heures", time_diff)
                    
                    # Calculer l'énergie en kWh (moyenne des puissances * temps)
                    energy_increment = ((total_last_power + total_current_power) / 2) * time_diff / 1000
                    _LOGGER.debug("Incrément d'énergie calculé: %s kWh", energy_increment)
                    
                    # Ajouter à la valeur totale
                    if self._attr_native_value is None:
                        self._attr_native_value = energy_increment
                    else:
                        self._attr_native_value += energy_increment
                    
                    _LOGGER.debug("Nouvelle valeur d'énergie totale: %s kWh", self._attr_native_value)
                else:
                    _LOGGER.debug("Première mise à jour, initialisation du temps de référence")
                
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

def extract_equipment_data(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Extraire les données d'équipement à partir de différents formats de payload."""
    try:
        _LOGGER.debug("Tentative d'extraction des données d'équipement du payload: %s", payload)
        
        # Cas 0: Format direct de l'API scene/user/list/V2 (format exact observé dans la capture d'écran)
        if isinstance(payload, dict) and "code" in payload and payload["code"] == 200 and "data" in payload:
            _LOGGER.debug("Format API scene/user/list/V2 détecté")
            if isinstance(payload["data"], list) and len(payload["data"]) > 0:
                # Trouver l'équipement dans la liste
                for item in payload["data"]:
                    if isinstance(item, dict) and "equipId" in item:
                        _LOGGER.debug("Équipement trouvé dans la liste: %s", item)
                        # Vérifier spécifiquement le code modèle
                        if "equipModelCode" in item:
                            _LOGGER.info("Code modèle trouvé dans les données: %s", item["equipModelCode"])
                        return item
                # Si aucun équipement spécifique n'est trouvé, retourner le premier
                if payload["data"][0]:
                    _LOGGER.debug("Premier équipement de la liste retourné: %s", payload["data"][0])
                    # Vérifier spécifiquement le code modèle
                    if isinstance(payload["data"][0], dict) and "equipModelCode" in payload["data"][0]:
                        _LOGGER.info("Code modèle trouvé dans les données: %s", payload["data"][0]["equipModelCode"])
                    return payload["data"][0]
            elif isinstance(payload["data"], dict):
                _LOGGER.debug("Données d'équipement trouvées directement dans data: %s", payload["data"])
                # Vérifier spécifiquement le code modèle
                if "equipModelCode" in payload["data"]:
                    _LOGGER.info("Code modèle trouvé dans les données: %s", payload["data"]["equipModelCode"])
                return payload["data"]
        
        # Cas 1: Format standard avec scene_info
        if isinstance(payload, dict) and "scene_info" in payload:
            scene_info = payload["scene_info"]
            _LOGGER.debug("Format scene_info détecté: %s", scene_info)
            if "data" in scene_info and scene_info["data"]:
                # Extraire les données correctement, qu'elles soient dans une liste ou directement dans un dictionnaire
                if isinstance(scene_info["data"], list) and scene_info["data"]:
                    _LOGGER.debug("Données extraites de scene_info (format liste)")
                    # Vérifier spécifiquement le code modèle
                    if isinstance(scene_info["data"][0], dict) and "equipModelCode" in scene_info["data"][0]:
                        _LOGGER.info("Code modèle trouvé dans les données: %s", scene_info["data"][0]["equipModelCode"])
                    return scene_info["data"][0]
                else:
                    _LOGGER.debug("Données extraites de scene_info (format direct)")
                    # Vérifier spécifiquement le code modèle
                    if isinstance(scene_info["data"], dict) and "equipModelCode" in scene_info["data"]:
                        _LOGGER.info("Code modèle trouvé dans les données: %s", scene_info["data"]["equipModelCode"])
                    return scene_info["data"]
        
        # Cas 2: Format WebSocket avec ID d'équipement comme clé principale
        elif isinstance(payload, dict) and any(key.startswith("9") for key in payload.keys()):
            equip_id = next((key for key in payload.keys() if key.startswith("9")), None)
            _LOGGER.debug("Format avec ID d'équipement détecté: %s", equip_id)
            if equip_id and isinstance(payload[equip_id], dict):
                equip_data = payload[equip_id]
                _LOGGER.debug("Données d'équipement extraites: %s", equip_data)
                
                # Traiter les données selon leur format
                if "list" in equip_data and isinstance(equip_data["list"], list) and equip_data["list"]:
                    # Format avec liste d'équipements
                    _LOGGER.debug("Données extraites du format liste")
                    # Vérifier spécifiquement le code modèle
                    if isinstance(equip_data["list"][0], dict) and "equipModelCode" in equip_data["list"][0]:
                        _LOGGER.info("Code modèle trouvé dans les données: %s", equip_data["list"][0]["equipModelCode"])
                    return equip_data["list"][0]
                else:
                    # Format sans liste
                    _LOGGER.debug("Données extraites directement")
                    # Vérifier spécifiquement le code modèle
                    if "equipModelCode" in equip_data:
                        _LOGGER.info("Code modèle trouvé dans les données: %s", equip_data["equipModelCode"])
                    return equip_data
        
        # Cas 3: Format API standard avec code/message/data
        elif isinstance(payload, dict) and "code" in payload and "data" in payload:
            _LOGGER.debug("Format API standard détecté")
            if payload["code"] == 200:
                data = payload["data"]
                _LOGGER.debug("Données extraites du format API: %s", data)
                
                # Vérifier si les données contiennent des informations d'équipement
                if isinstance(data, dict):
                    if "equipId" in data:
                        _LOGGER.debug("Données d'équipement trouvées avec equipId")
                        # Vérifier spécifiquement le code modèle
                        if "equipModelCode" in data:
                            _LOGGER.info("Code modèle trouvé dans les données: %s", data["equipModelCode"])
                        return data
                    # Format spécifique observé dans le message WebSocket
                    elif any(key in data for key in ["outputType", "equipId", "reserved", "outputPower", "workStatus", "isOnline", "equipType", "mainEquipOnline", "bluetoothName", "equipModelCode", "createTime"]):
                        _LOGGER.debug("Données d'équipement trouvées avec attributs spécifiques")
                        # Vérifier spécifiquement le code modèle
                        if "equipModelCode" in data:
                            _LOGGER.info("Code modèle trouvé dans les données: %s", data["equipModelCode"])
                        return data
                    # Format avec sceneAlias, sceneId, etc.
                    elif any(key in data for key in ["sceneAlias", "sceneId", "sceneCode"]):
                        _LOGGER.debug("Données de scène trouvées")
                        # Vérifier spécifiquement le code modèle
                        if "equipModelCode" in data:
                            _LOGGER.info("Code modèle trouvé dans les données: %s", data["equipModelCode"])
                        return data
                # Format API OUTPUT_URL avec liste d'équipements
                elif isinstance(data, list) and data:
                    _LOGGER.debug("Format API OUTPUT_URL avec liste d'équipements détecté")
                    # Trouver l'équipement correspondant dans la liste
                    for item in data:
                        if isinstance(item, dict) and "equipId" in item:
                            _LOGGER.debug("Équipement trouvé dans la liste: %s", item)
                            # Vérifier spécifiquement le code modèle
                            if "equipModelCode" in item:
                                _LOGGER.info("Code modèle trouvé dans les données: %s", item["equipModelCode"])
                            return item
                    # Si aucun équipement spécifique n'est trouvé, retourner le premier
                    if data[0]:
                        _LOGGER.debug("Premier équipement de la liste retourné: %s", data[0])
                        # Vérifier spécifiquement le code modèle
                        if isinstance(data[0], dict) and "equipModelCode" in data[0]:
                            _LOGGER.info("Code modèle trouvé dans les données: %s", data[0]["equipModelCode"])
                        return data[0]
        
        # Cas 4: Format direct avec les données d'équipement
        elif isinstance(payload, dict) and any(key in payload for key in ["outputType", "equipId", "reserved", "outputPower", "workStatus", "isOnline", "equipType", "mainEquipOnline", "bluetoothName", "equipModelCode", "createTime"]):
            _LOGGER.debug("Format direct avec données d'équipement détecté")
            # Vérifier spécifiquement le code modèle
            if "equipModelCode" in payload:
                _LOGGER.info("Code modèle trouvé dans les données: %s", payload["equipModelCode"])
            return payload
            
        # Cas 5: Format avec liste d'équipements et totalPv1power, totalInvPower, etc.
        elif isinstance(payload, dict) and "list" in payload and isinstance(payload["list"], list) and payload["list"]:
            _LOGGER.debug("Format avec liste d'équipements et données totales détecté")
            # Extraire les données du premier équipement dans la liste
            equip_data = payload["list"][0]
            
            # Ajouter les données totales aux données de l'équipement
            if "equipId" in equip_data:
                result = equip_data.copy()
                # Ajouter les données totales
                for key, value in payload.items():
                    if key != "list":
                        result[key] = value
                _LOGGER.debug("Données combinées extraites: %s", result)
                # Vérifier spécifiquement le code modèle
                if "equipModelCode" in result:
                    _LOGGER.info("Code modèle trouvé dans les données: %s", result["equipModelCode"])
                return result
            # Vérifier spécifiquement le code modèle
            if "equipModelCode" in equip_data:
                _LOGGER.info("Code modèle trouvé dans les données: %s", equip_data["equipModelCode"])
            return equip_data
        
        # Aucun format reconnu
        _LOGGER.warning("Aucun format reconnu dans le payload: %s", payload)
        return None
    except Exception as e:
        _LOGGER.error("Erreur lors de l'extraction des données d'équipement: %s", e)
        import traceback
        _LOGGER.error("Traceback: %s", traceback.format_exc())
        return None

class StorcubeSceneInfoSensor(SensorEntity):
    """Représentation des informations de scène de Storcube."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Informations Scène Storcube"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_scene_info"
        self._config = config
        self._attr_native_value = "Non disponible"
        self._attr_extra_state_attributes = {"Inconnu": "Inconnu"}
        self._attr_icon = "mdi:information-outline"

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from coordinator."""
        try:
            _LOGGER.debug("StorcubeSceneInfoSensor - Payload reçu: %s", payload)
            
            # Extraire les données d'équipement
            data = extract_equipment_data(payload)
            
            if data:
                # Mettre à jour la valeur native avec un résumé
                output_power = data.get('outputPower', 'N/A')
                reserved = data.get('reserved', 'N/A')
                self._attr_native_value = f"Puissance: {output_power}W, Réserve: {reserved}%"
                _LOGGER.debug("Valeur native mise à jour: %s", self._attr_native_value)
                
                # Mettre à jour les attributs avec toutes les informations disponibles
                attributes = {}
                for key, value in data.items():
                    attributes[key] = value
                
                self._attr_extra_state_attributes = attributes
                _LOGGER.debug("Attributs mis à jour: %s", attributes)
                
                _LOGGER.info("Informations de scène mises à jour: %s", self._attr_native_value)
                self.async_write_ha_state()
            else:
                _LOGGER.warning("Aucune donnée d'équipement extraite du payload")
        except Exception as e:
            _LOGGER.error("Erreur lors de la mise à jour des informations de scène: %s", e)
            import traceback
            _LOGGER.error("Traceback: %s", traceback.format_exc())

class StorcubeSceneOutputTypeSensor(SensorEntity):
    """Représentation du type de sortie de Storcube."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Type de Sortie Storcube"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_output_type"
        self._config = config
        self._attr_native_value = "Non disponible"
        self._attr_icon = "mdi:power-plug"

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from coordinator."""
        try:
            # Extraire les données d'équipement
            data = extract_equipment_data(payload)
            
            if data:
                self._attr_native_value = data.get("outputType", "Non disponible")
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Erreur lors de la mise à jour du type de sortie: %s", e)

class StorcubeSceneReservedSensor(SensorEntity):
    """Représentation du niveau de réserve de Storcube."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Niveau de Réserve Storcube"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_reserved"
        self._config = config
        self._attr_native_value = 0
        self._attr_native_unit_of_measurement = "%"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:battery-low"

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from coordinator."""
        try:
            # Extraire les données d'équipement
            data = extract_equipment_data(payload)
            
            if data:
                self._attr_native_value = data.get("reserved", 0)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Erreur lors de la mise à jour du niveau de réserve: %s", e)

class StorcubeSceneOutputPowerSensor(SensorEntity):
    """Représentation de la puissance de sortie configurée de Storcube."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Puissance de Sortie Configurée Storcube"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_configured_output_power"
        self._config = config
        self._attr_native_value = 0
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:lightning-bolt-outline"

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from coordinator."""
        try:
            # Extraire les données d'équipement
            data = extract_equipment_data(payload)
            
            if data:
                self._attr_native_value = data.get("outputPower", 0)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Erreur lors de la mise à jour de la puissance de sortie configurée: %s", e)

class StorcubeSceneWorkStatusSensor(SensorEntity):
    """Représentation du statut de fonctionnement de Storcube."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Statut de Fonctionnement Storcube"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_work_status"
        self._config = config
        self._attr_native_value = "Non disponible"
        self._attr_icon = "mdi:power"

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from coordinator."""
        try:
            # Extraire les données d'équipement
            data = extract_equipment_data(payload)
            
            if data:
                work_status = data.get("workStatus", 0)
                self._attr_native_value = "En marche" if work_status == 1 else "Arrêté"
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Erreur lors de la mise à jour du statut de fonctionnement: %s", e)

class StorcubeSceneIsOnlineSensor(SensorEntity):
    """Représentation du statut en ligne de Storcube."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Statut En Ligne Storcube"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_is_online"
        self._config = config
        self._attr_native_value = "Non disponible"
        self._attr_icon = "mdi:wifi"

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from coordinator."""
        try:
            # Extraire les données d'équipement
            data = extract_equipment_data(payload)
            
            if data:
                is_online = data.get("isOnline", 0)
                self._attr_native_value = "En ligne" if is_online == 1 else "Hors ligne"
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Erreur lors de la mise à jour du statut en ligne: %s", e)

class StorcubeSceneEquipTypeSensor(SensorEntity):
    """Représentation du type d'équipement Storcube."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Type d'Équipement Storcube"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_equip_type"
        self._config = config
        self._attr_native_value = "Non disponible"
        self._attr_icon = "mdi:battery"

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from coordinator."""
        try:
            # Extraire les données d'équipement
            data = extract_equipment_data(payload)
            
            if data:
                self._attr_native_value = data.get("equipType", "Non disponible")
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Erreur lors de la mise à jour du type d'équipement: %s", e)

class StorcubeSceneBluetoothNameSensor(SensorEntity):
    """Représentation du nom Bluetooth de Storcube."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Nom Bluetooth Storcube"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_bluetooth_name"
        self._config = config
        self._attr_native_value = "Non disponible"
        self._attr_icon = "mdi:bluetooth"

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from coordinator."""
        try:
            # Extraire les données d'équipement
            data = extract_equipment_data(payload)
            
            if data:
                self._attr_native_value = data.get("bluetoothName", "Non disponible")
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Erreur lors de la mise à jour du nom Bluetooth: %s", e)

class StorcubeSceneEquipModelCodeSensor(SensorEntity):
    """Représentation du code modèle de l'équipement Storcube."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Code Modèle Storcube"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_model_code"
        self._config = config
        self._attr_native_value = "Non disponible"
        self._attr_icon = "mdi:barcode"
        self._last_valid_value = None  # Stocker la dernière valeur valide
        self._attr_extra_state_attributes = {
            "dernière_valeur_connue": None,
            "dernière_mise_à_jour": None
        }

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from coordinator."""
        try:
            # Extraire les données d'équipement
            data = extract_equipment_data(payload)
            
            if data:
                model_code = data.get("equipModelCode")
                if model_code is not None and model_code != "":
                    self._attr_native_value = model_code
                    self._last_valid_value = model_code
                    self._attr_extra_state_attributes["dernière_valeur_connue"] = model_code
                    self._attr_extra_state_attributes["dernière_mise_à_jour"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    _LOGGER.info("Code modèle mis à jour: %s", model_code)
                elif self._last_valid_value is not None:
                    # Si aucune valeur n'est disponible mais que nous avons une valeur précédente, l'utiliser
                    self._attr_native_value = self._last_valid_value
                    _LOGGER.debug("Utilisation de la dernière valeur connue pour le code modèle: %s", self._last_valid_value)
                else:
                    self._attr_native_value = "Non disponible"
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Erreur lors de la mise à jour du code modèle: %s", e)
            # En cas d'erreur, conserver la dernière valeur valide si disponible
            if self._last_valid_value is not None:
                self._attr_native_value = self._last_valid_value
                self.async_write_ha_state()

class StorcubeSceneCreateTimeSensor(SensorEntity):
    """Représentation de la date de création de Storcube."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Date de Création Storcube"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_create_time"
        self._config = config
        self._attr_native_value = "Non disponible"
        self._attr_icon = "mdi:calendar"

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from coordinator."""
        try:
            # Extraire les données d'équipement
            data = extract_equipment_data(payload)
            
            if data:
                self._attr_native_value = data.get("createTime", "Non disponible")
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Erreur lors de la mise à jour de la date de création: %s", e)

async def websocket_to_mqtt(hass: HomeAssistant, config_entry: ConfigEntry, config: ConfigType) -> None:
    """Handle websocket connection and forward data to MQTT."""
    # Créer une tâche pour la récupération des données API
    asyncio.create_task(periodic_api_fetch(hass, config_entry, config))
    
    # Continuer avec la connexion WebSocket
    try:
        uri = f"wss://baterway.com/websocket/{config[CONF_DEVICE_ID]}"
        _LOGGER.info("Connexion WebSocket à %s", uri)
        
        async with websockets.connect(uri) as websocket:
            _LOGGER.info("Connexion WebSocket établie")
            
            # Envoyer un message de heartbeat toutes les 30 secondes
            async def heartbeat():
                while True:
                    try:
                        await websocket.ping()
                        _LOGGER.debug("Ping WebSocket envoyé")
                        await asyncio.sleep(30)
                    except Exception as e:
                        _LOGGER.error("Erreur lors de l'envoi du ping WebSocket: %s", str(e))
                        break
            
            # Démarrer la tâche de heartbeat
            heartbeat_task = asyncio.create_task(heartbeat())
            
            try:
                while True:
                    try:
                        message = await websocket.recv()
                        _LOGGER.debug("Message WebSocket reçu: %s", message)
                        
                        # Analyser le message JSON
                        try:
                            data = json.loads(message)
                            
                            # Journaliser les clés du message pour le débogage
                            if isinstance(data, dict):
                                _LOGGER.debug("Clés du message WebSocket: %s", list(data.keys()))
                                
                                # Vérifier spécifiquement le code modèle dans les données
                                if "9" in data:
                                    equip_data = data["9"]
                                    if isinstance(equip_data, dict) and "equipModelCode" in equip_data:
                                        _LOGGER.info("Code modèle trouvé dans le message WebSocket: %s", equip_data["equipModelCode"])
                                
                                # Vérifier si nous avons des données d'équipement
                                has_equip_data = False
                                for key in data.keys():
                                    if key.startswith("9"):
                                        has_equip_data = True
                                        break
                                
                                if has_equip_data:
                                    _LOGGER.info("Message WebSocket contient des données d'équipement")
                                else:
                                    _LOGGER.debug("Message WebSocket ne contient pas de données d'équipement")
                            
                            # Mettre à jour les capteurs directement avec le message brut
                            if DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]:
                                for sensor in hass.data[DOMAIN][config_entry.entry_id]["sensors"]:
                                    # Vérifier si c'est le capteur de code modèle
                                    if hasattr(sensor, '_attr_unique_id') and 'model_code' in sensor._attr_unique_id:
                                        _LOGGER.info("Mise à jour du capteur de code modèle avec les données WebSocket: %s", data)
                                    sensor.handle_state_update(data)
                            else:
                                _LOGGER.warning("Impossible de trouver les capteurs dans hass.data")
                                
                        except json.JSONDecodeError:
                            _LOGGER.warning("Message WebSocket non-JSON reçu: %s", message)
                    except websockets.exceptions.ConnectionClosed:
                        _LOGGER.warning("Connexion WebSocket fermée, tentative de reconnexion...")
                        break
                    except Exception as e:
                        _LOGGER.error("Erreur lors du traitement du message WebSocket: %s", str(e))
                        import traceback
                        _LOGGER.error("Traceback: %s", traceback.format_exc())
                        await asyncio.sleep(5)  # Attendre avant de continuer
            finally:
                # Annuler la tâche de heartbeat
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
    
    except Exception as e:
        _LOGGER.error("Erreur lors de la connexion WebSocket: %s", str(e))
        import traceback
        _LOGGER.error("Traceback: %s", traceback.format_exc())
        
    # Attendre avant de réessayer
    await asyncio.sleep(10)
    
    # Réessayer la connexion
    _LOGGER.info("Tentative de reconnexion WebSocket...")
    asyncio.create_task(websocket_to_mqtt(hass, config_entry, config))

async def periodic_api_fetch(hass: HomeAssistant, config_entry: ConfigEntry, config: ConfigType) -> None:
    """Récupérer périodiquement les données de l'API pour s'assurer que les capteurs sont à jour."""
    _LOGGER.info("Démarrage de la récupération périodique des données API")
    
    # Créer une session HTTP pour les requêtes API
    async with aiohttp.ClientSession() as session:
        # Obtenir les en-têtes d'authentification
        headers = await get_auth_headers(session, config)
        if not headers:
            _LOGGER.error("Impossible d'obtenir les en-têtes d'authentification pour les requêtes API")
            return
        
        while True:
            try:
                # Récupérer les données de scène
                await fetch_scene_data(hass, session, headers, config, config_entry)
                
                # Récupérer les données d'équipement
                await fetch_equipment_data(hass, session, headers, config, config_entry)
                
                # Récupérer les données en temps réel
                await fetch_realtime_data(hass, session, headers, config, config_entry)
                
                # Attendre avant la prochaine récupération (toutes les 60 secondes)
                await asyncio.sleep(60)
            except Exception as e:
                _LOGGER.error("Erreur lors de la récupération périodique des données API: %s", str(e))
                import traceback
                _LOGGER.error("Traceback: %s", traceback.format_exc())
                
                # Attendre avant de réessayer
                await asyncio.sleep(30)

async def get_auth_headers(session: aiohttp.ClientSession, config: ConfigType) -> Optional[dict]:
    """Obtenir les en-têtes d'authentification pour les requêtes API."""
    try:
        # Construire le payload d'authentification
        payload = {
            "appCode": config[CONF_APP_CODE],
            "loginName": config[CONF_LOGIN_NAME],
            "password": config[CONF_AUTH_PASSWORD]
        }
        
        # Faire la requête d'authentification
        async with session.post(
            TOKEN_URL,
            json=payload,
            headers={
                'Content-Type': 'application/json',
                'accept-language': 'fr-FR',
                'user-agent': 'Mozilla/5.0 (Linux; Android 11; SM-A202F Build/RP1A.200720.012; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/132.0.6834.163 Mobile Safari/537.36 uni-app Html5Plus/1.0 (Immersed/24.0)'
            }
        ) as response:
            response_text = await response.text()
            _LOGGER.debug("Réponse d'authentification brute: %s", response_text)
            
            token_data = json.loads(response_text)
            if token_data.get("code") != 200:
                _LOGGER.error("Échec de l'authentification: %s", token_data.get("message", "Erreur inconnue"))
                return None
            
            token = token_data["data"]["token"]
            _LOGGER.info("Token obtenu avec succès")
            
            # Construire les en-têtes avec le token
            headers = {
                "Authorization": token,
                "Content-Type": "application/json",
                "appCode": config[CONF_APP_CODE]
            }
            
            return headers
    except Exception as e:
        _LOGGER.error("Erreur lors de l'obtention des en-têtes d'authentification: %s", str(e))
        return None

async def fetch_equipment_data(hass: HomeAssistant, session: aiohttp.ClientSession, headers: dict, config: ConfigType, config_entry: ConfigEntry) -> None:
    """Récupérer les données détaillées de l'équipement."""
    try:
        # Construire l'URL avec l'ID de l'équipement
        api_url = f"http://baterway.com/api/equip/detail?equipId={config[CONF_DEVICE_ID]}"
        _LOGGER.debug("Récupération des données d'équipement depuis %s", api_url)
        
        # Faire la requête API
        async with session.get(
            api_url,
            headers=headers
        ) as api_response:
            api_response_text = await api_response.text()
            _LOGGER.debug("Réponse API équipement brute: %s", api_response_text)
            
            api_data = json.loads(api_response_text)
            if api_data.get("code") != 200:
                _LOGGER.error("Échec de la requête API équipement: %s", api_data.get("message", "Erreur inconnue"))
                return
            
            _LOGGER.info("Données API équipement récupérées avec succès")
            
            # Mettre à jour les capteurs directement avec les données API
            if DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]:
                # Mettre à jour uniquement les capteurs d'équipement
                for sensor in hass.data[DOMAIN][config_entry.entry_id]["sensors"]:
                    if hasattr(sensor, '_attr_unique_id') and any(
                        equip_type in sensor._attr_unique_id for equip_type in 
                        ['battery_level', 'battery_power', 'battery_temperature', 'battery_capacity', 
                         'battery_status', 'solar_power', 'solar_energy', 'output_power', 'output_energy']
                    ):
                        _LOGGER.debug("Mise à jour du capteur d'équipement: %s", sensor._attr_unique_id)
                        sensor.handle_state_update(api_data)
            else:
                _LOGGER.warning("Impossible de trouver les capteurs dans hass.data")
    
    except Exception as e:
        _LOGGER.error("Erreur lors de la récupération des données d'équipement: %s", str(e))
        import traceback
        _LOGGER.error("Traceback: %s", traceback.format_exc())

async def fetch_realtime_data(hass: HomeAssistant, session: aiohttp.ClientSession, headers: dict, config: ConfigType, config_entry: ConfigEntry) -> None:
    """Récupérer les données en temps réel de l'équipement."""
    try:
        # Construire l'URL avec l'ID de l'équipement
        api_url = f"http://baterway.com/api/slb/equip/real/time/data?equipId={config[CONF_DEVICE_ID]}"
        _LOGGER.debug("Récupération des données en temps réel depuis %s", api_url)
        
        # Faire la requête API
        async with session.get(
            api_url,
            headers=headers
        ) as api_response:
            api_response_text = await api_response.text()
            _LOGGER.debug("Réponse API temps réel brute: %s", api_response_text)
            
            api_data = json.loads(api_response_text)
            if api_data.get("code") != 200:
                _LOGGER.error("Échec de la requête API temps réel: %s", api_data.get("message", "Erreur inconnue"))
                return
            
            _LOGGER.info("Données API temps réel récupérées avec succès")
            
            # Mettre à jour les capteurs directement avec les données API
            if DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]:
                # Mettre à jour uniquement les capteurs en temps réel
                for sensor in hass.data[DOMAIN][config_entry.entry_id]["sensors"]:
                    if hasattr(sensor, '_attr_unique_id') and any(
                        rt_type in sensor._attr_unique_id for rt_type in 
                        ['battery_level', 'battery_power', 'solar_power', 'output_power']
                    ):
                        _LOGGER.debug("Mise à jour du capteur temps réel: %s", sensor._attr_unique_id)
                        sensor.handle_state_update(api_data)
            else:
                _LOGGER.warning("Impossible de trouver les capteurs dans hass.data")
    
    except Exception as e:
        _LOGGER.error("Erreur lors de la récupération des données en temps réel: %s", str(e))
        import traceback
        _LOGGER.error("Traceback: %s", traceback.format_exc())

async def fetch_scene_data(hass: HomeAssistant, session: aiohttp.ClientSession, headers: dict, config: ConfigType, config_entry: ConfigEntry) -> None:
    """Récupérer les données de scène depuis l'API OUTPUT_URL."""
    try:
        # Construire l'URL avec l'ID de l'équipement
        api_url = f"{OUTPUT_URL}?equipId={config[CONF_DEVICE_ID]}"
        _LOGGER.debug("Récupération des données de scène depuis %s", api_url)
        
        # Faire la requête API
        async with session.get(
            api_url,
            headers=headers
        ) as api_response:
            api_response_text = await api_response.text()
            _LOGGER.debug("Réponse API scène brute: %s", api_response_text)
            
            api_data = json.loads(api_response_text)
            if api_data.get("code") != 200:
                _LOGGER.error("Échec de la requête API scène: %s", api_data.get("message", "Erreur inconnue"))
                return
            
            _LOGGER.info("Données API scène récupérées avec succès")
            
            # Vérifier spécifiquement le code modèle dans les données
            if "data" in api_data and isinstance(api_data["data"], list) and api_data["data"]:
                for item in api_data["data"]:
                    if isinstance(item, dict) and "equipModelCode" in item:
                        _LOGGER.info("Code modèle trouvé dans les données de scène: %s", item["equipModelCode"])
                        break
            
            # Mettre à jour les capteurs directement avec les données API
            if DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]:
                # Mettre à jour uniquement les capteurs de scène
                for sensor in hass.data[DOMAIN][config_entry.entry_id]["sensors"]:
                    if hasattr(sensor, '_attr_unique_id') and any(
                        scene_type in sensor._attr_unique_id for scene_type in 
                        ['scene_info', 'output_type', 'reserved', 'configured_output_power', 
                         'work_status', 'is_online', 'equip_type', 'bluetooth_name', 
                         'model_code', 'create_time']
                    ):
                        _LOGGER.debug("Mise à jour du capteur de scène: %s", sensor._attr_unique_id)
                        # Vérifier si c'est le capteur de code modèle
                        if hasattr(sensor, '_attr_unique_id') and 'model_code' in sensor._attr_unique_id:
                            _LOGGER.info("Mise à jour du capteur de code modèle avec les données: %s", api_data)
                        sensor.handle_state_update(api_data)
            else:
                _LOGGER.warning("Impossible de trouver les capteurs dans hass.data")
    
    except Exception as e:
        _LOGGER.error("Erreur lors de la récupération des données de scène: %s", str(e))
        import traceback
        _LOGGER.error("Traceback: %s", traceback.format_exc())