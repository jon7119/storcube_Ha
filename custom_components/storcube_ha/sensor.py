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
        StorcubeBatteryThresholdSensor(config),
        StorcubeBatteryVoltageSensor(config),
        StorcubeBatteryCurrentSensor(config),
        StorcubeBatteryTemperatureSensor(config),
        StorcubeBatteryEnergySensor(config),
        StorcubeBatteryCapacitySensor(config),
        StorcubeBatteryHealthSensor(config),
        StorcubeBatteryCyclesSensor(config),
        StorcubeBatteryStatusSensor(config),
        
        # Capteurs solaires
        StorcubeSolarPowerSensor(config),
        StorcubeSolarVoltageSensor(config),
        StorcubeSolarCurrentSensor(config),
        StorcubeSolarEnergySensor(config),
        
        # Capteurs solaires pour le deuxième panneau
        StorcubeSolarPowerSensor2(config),
        StorcubeSolarVoltageSensor2(config),
        StorcubeSolarCurrentSensor2(config),
        StorcubeSolarEnergySensor2(config),
        
        # Capteurs de sortie
        StorcubeOutputPowerSensor(config),
        StorcubeOutputVoltageSensor(config),
        StorcubeOutputCurrentSensor(config),
        StorcubeOutputEnergySensor(config),
        
        # Capteurs système
        StorcubeStatusSensor(config),
        StorcubeFirmwareVersionSensor(config),
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

class StorcubeBatteryLevelSensor(SensorEntity):
    """Représentation du niveau de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Niveau Batterie Storcube"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_level"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                self._attr_native_value = equip.get("soc")
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery level: %s", e)
            _LOGGER.debug("Payload reçu: %s", payload)

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

class StorcubeBatteryVoltageSensor(SensorEntity):
    """Représentation de la tension de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Tension Batterie Storcube"
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_voltage"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                # La tension n'est pas disponible dans les données actuelles
                self._attr_native_value = None
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery voltage: %s", e)

class StorcubeBatteryCurrentSensor(SensorEntity):
    """Représentation du courant de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Courant Batterie Storcube"
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_device_class = SensorDeviceClass.CURRENT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_current"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                # Le courant n'est pas disponible dans les données actuelles
                self._attr_native_value = None
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery current: %s", e)

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
        """Initialize the sensor."""
        self._attr_name = "Capacité Batterie Storcube"
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY_STORAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_capacity"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                self._attr_native_value = equip.get("capacity")
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery capacity: %s", e)
            _LOGGER.debug("Payload reçu: %s", payload)

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

class StorcubeBatteryCyclesSensor(SensorEntity):
    """Représentation des cycles de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Cycles Batterie Storcube"
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_battery_cycles"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("battery_cycles")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery cycles: %s", e)

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

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                self._attr_native_value = equip.get("pv1power")
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating solar power: %s", e)
            _LOGGER.debug("Payload reçu: %s", payload)

class StorcubeSolarVoltageSensor(SensorEntity):
    """Représentation de la tension solaire."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Tension Solaire Storcube"
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_solar_voltage"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("solar_voltage")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating solar voltage: %s", e)

class StorcubeSolarCurrentSensor(SensorEntity):
    """Représentation du courant solaire."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Courant Solaire Storcube"
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_device_class = SensorDeviceClass.CURRENT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_solar_current"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("solar_current")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating solar current: %s", e)

class StorcubeSolarEnergySensor(SensorEntity):
    """Représentation de l'énergie solaire produite."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Énergie Solaire Storcube"
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_solar_energy"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("solar_energy")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating solar energy: %s", e)

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

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                equip = payload["list"][0]
                self._attr_native_value = equip.get("pv2power")
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating solar power 2: %s", e)
            _LOGGER.debug("Payload reçu: %s", payload)

class StorcubeSolarVoltageSensor2(SensorEntity):
    """Représentation de la tension solaire du deuxième panneau."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Tension Solaire 2 Storcube"
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_solar_voltage_2"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("solar_voltage_2")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating solar voltage 2: %s", e)

class StorcubeSolarCurrentSensor2(SensorEntity):
    """Représentation du courant solaire du deuxième panneau."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Courant Solaire 2 Storcube"
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_device_class = SensorDeviceClass.CURRENT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_solar_current_2"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("solar_current_2")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating solar current 2: %s", e)

class StorcubeSolarEnergySensor2(SensorEntity):
    """Représentation de l'énergie solaire produite par le deuxième panneau."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Énergie Solaire 2 Storcube"
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_solar_energy_2"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("solar_energy_2")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating solar energy 2: %s", e)

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

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            if isinstance(payload, dict):
                self._attr_native_value = payload.get("totalInvPower")
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating output power: %s", e)
            _LOGGER.debug("Payload reçu: %s", payload)

class StorcubeOutputVoltageSensor(SensorEntity):
    """Représentation de la tension de sortie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Tension Sortie Storcube"
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_output_voltage"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("output_voltage")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating output voltage: %s", e)

class StorcubeOutputCurrentSensor(SensorEntity):
    """Représentation du courant de sortie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Courant Sortie Storcube"
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_device_class = SensorDeviceClass.CURRENT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_output_current"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("output_current")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating output current: %s", e)

class StorcubeOutputEnergySensor(SensorEntity):
    """Représentation de l'énergie consommée."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._attr_name = "Énergie Consommée Storcube"
        self._attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_output_energy"
        self._config = config
        self._attr_native_value = None

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from MQTT."""
        try:
            self._attr_native_value = payload.get("output_energy")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating output energy: %s", e)

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