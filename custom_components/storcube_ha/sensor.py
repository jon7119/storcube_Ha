"""Support for Storcube Battery Monitor sensors."""
from __future__ import annotations

import logging
import json
import asyncio
import aiohttp
import websockets
from datetime import datetime
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
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
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
    OUTPUT_URL,
    FIRMWARE_URL,
    SET_POWER_URL,
    SET_THRESHOLD_URL,
    DEVICE_INFO_URL,
    STATISTICS_ENERGY_URL,
)
from .battery_manager import StorCubeBatteryManager
from .individual_battery_sensor import create_individual_battery_sensors

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    config = config_entry.data
    
    # Récupérer le coordinateur
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    # Créer le gestionnaire de batteries
    battery_manager = StorCubeBatteryManager()
    
    # Fonction pour obtenir l'ID de la batterie maître
    def get_master_battery_id():
        """Obtenir l'ID de la batterie maître."""
        # Pour l'instant, on utilise le device_id principal comme batterie maître
        # Plus tard, cela sera mis à jour quand les données WebSocket arriveront
        return config[CONF_DEVICE_ID]

    sensors = [
        # Capteurs système globaux (seulement ceux qui ne sont pas dupliqués avec les capteurs individuels)
        StorcubeBatteryThresholdSensor(config),  # Seuil de batterie (global)
        
        # Capteurs solaires (globaux)
        StorcubeSolarPowerSensor(config),
        StorcubeSolarEnergySensor(config),
        StorcubeSolarPowerSensor2(config),
        StorcubeSolarEnergySensor2(config),
        StorcubeSolarEnergyTotalSensor(config),
        
        # Capteurs de sortie (globaux)
        StorcubeOutputPowerSensor(config),
        StorcubeOutputEnergySensor(config),
        
        # Capteurs d'état système (globaux)
        StorcubeStatusSensor(config),
        StorcubeOutputTypeSensor(config),
        StorcubeReservedSensor(config),
        StorcubeOnlineSensor(config),
        
        # Capteur de firmware (global)
        StorcubeFirmwareSensor(config, coordinator),
        StorcubeOperatingModeSensor(config),
        
        # Nouveaux capteurs depuis /api/device/info
        StorcubeVoltageSensor(config),
        StorcubeCurrentSensor(config),
        StorcubeFrequencySensor(config),
        StorcubeGridVoltageSensor(config),
        StorcubeLoadPowerSensor(config),
        StorcubeChargePowerSensor(config),
        StorcubeDischargePowerSensor(config),
        StorcubeEnergySensor(config),
    ]

    async_add_entities(sensors)

    # Store sensors and battery manager in hass.data
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    
    # Récupérer le coordinateur existant
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    # S'assurer que le battery_manager est bien initialisé (utiliser celui du coordinateur s'il existe)
    if hasattr(coordinator, 'battery_manager') and coordinator.battery_manager is not None:
        # Utiliser le battery_manager du coordinateur et le mettre à jour
        battery_manager = coordinator.battery_manager
    else:
        # Sinon utiliser celui créé ici et le stocker dans le coordinateur
        coordinator.battery_manager = battery_manager
    
    # Ajouter les données des capteurs au coordinateur
    coordinator.global_sensors = sensors  # Capteurs globaux (acceptent des dictionnaires)
    if not hasattr(coordinator, 'individual_sensors'):
        coordinator.individual_sensors = {}  # Pour stocker les capteurs individuels (acceptent des objets BatteryInfo)
    coordinator.async_add_entities = async_add_entities  # Stocker le callback pour ajouter des entités
    
    _LOGGER.info("Sensors globaux créés: %d sensors", len(sensors))

    # Créer la vue Lovelace (temporairement désactivé)
    # await create_lovelace_view(hass, config_entry)

    # Start websocket connection and output API connection
    asyncio.create_task(websocket_to_mqtt(hass, config, config_entry))
    asyncio.create_task(output_api_to_mqtt(hass, config, config_entry))

async def create_individual_battery_sensors_for_battery(
    hass: HomeAssistant, 
    config_entry: ConfigEntry, 
    equip_id: str, 
    battery_info
) -> None:
    """Créer les capteurs individuels pour une batterie spécifique."""
    try:
        config = config_entry.data
        _LOGGER.debug("Batterie détectée: %s", equip_id)
        _LOGGER.debug("Informations batterie: SOC=%s%%, Temp=%s°C, Cap=%sWh, Maître=%s", 
                    battery_info.soc, battery_info.temp, battery_info.capacity, battery_info.is_master)
        
        # Créer des capteurs réels pour cette batterie
        individual_sensors = create_individual_battery_sensors(config, equip_id, battery_info)
        _LOGGER.debug("Capteurs créés pour la batterie %s: %d capteurs", equip_id, len(individual_sensors))
        
        # Récupérer le coordinateur
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        
        # Ajouter les capteurs à la liste des capteurs individuels
        if equip_id not in coordinator.individual_sensors:
            coordinator.individual_sensors[equip_id] = []
        
        coordinator.individual_sensors[equip_id].extend(individual_sensors)
        
        # Ne pas ajouter les capteurs individuels à la liste globale car ils ont des méthodes handle_state_update différentes
        
        # Enregistrer les capteurs dans Home Assistant
        async_add_entities_callback = coordinator.async_add_entities
        if async_add_entities_callback is None:
            _LOGGER.error("Callback async_add_entities non disponible pour la batterie %s", equip_id)
            return
        
        _LOGGER.debug("Enregistrement des capteurs dans Home Assistant pour la batterie %s", equip_id)
        # async_add_entities n'est pas une fonction async, c'est juste un callback
        async_add_entities_callback(individual_sensors)
        
        _LOGGER.debug("Capteurs réels créés et enregistrés pour la batterie %s", equip_id)
        
    except Exception as e:
        _LOGGER.error("Erreur lors de la création des capteurs individuels pour %s: %s", equip_id, e)


async def update_individual_battery_sensors(
    hass: HomeAssistant, 
    config_entry: ConfigEntry, 
    battery_manager: StorCubeBatteryManager
) -> None:
    """Mettre à jour les capteurs individuels avec les nouvelles données."""
    try:
        if not battery_manager:
            _LOGGER.warning("Battery manager non disponible pour la mise à jour des capteurs individuels")
            return
            
        batteries = battery_manager.get_all_batteries()
        _LOGGER.info("Mise à jour des capteurs individuels - Batteries dans le gestionnaire: %d", len(batteries))
        
        if not batteries:
            _LOGGER.debug("Aucune batterie dans le gestionnaire pour le moment")
            return
        
        new_batteries_detected = False
        
        # Récupérer le coordinateur
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        
        # S'assurer que individual_sensors existe
        if not hasattr(coordinator, 'individual_sensors'):
            coordinator.individual_sensors = {}
        
        # Vérifier s'il y a de nouvelles batteries
        # D'abord créer la batterie maître, puis les batteries esclaves
        # Trier les batteries : maître d'abord, puis esclaves
        master_batteries = {k: v for k, v in batteries.items() if v.is_master}
        slave_batteries = {k: v for k, v in batteries.items() if not v.is_master}
        
        _LOGGER.info("Batteries détectées - Maître: %d, Esclaves: %d", len(master_batteries), len(slave_batteries))
        
        # Mettre à jour le nom du device dans le device registry avec le rôle
        device_registry = dr.async_get(hass)
        
        # Créer d'abord la batterie maître
        for equip_id, battery_info in master_batteries.items():
            # Mettre à jour le nom du device dans le registry
            device = device_registry.async_get_device(identifiers={(DOMAIN, equip_id)})
            if device:
                device_registry.async_update_device(
                    device.id,
                    name=f"Batterie StorCube {equip_id} (Maître)"
                )
            
            if equip_id not in coordinator.individual_sensors:
                # Créer les capteurs réels pour cette nouvelle batterie
                _LOGGER.info("Nouvelle batterie maître détectée, création des capteurs: %s", equip_id)
                await create_individual_battery_sensors_for_battery(hass, config_entry, equip_id, battery_info)
                new_batteries_detected = True
                _LOGGER.info("Nouvelle batterie maître détectée et capteurs créés: %s", equip_id)
            else:
                # Mettre à jour les capteurs existants avec les nouvelles données
                if equip_id in coordinator.individual_sensors:
                    for sensor in coordinator.individual_sensors[equip_id]:
                        if hasattr(sensor, 'handle_state_update'):
                            sensor.handle_state_update(battery_info)
        
        # Ensuite créer les batteries esclaves
        for equip_id, battery_info in slave_batteries.items():
            # Mettre à jour le nom du device dans le registry
            device = device_registry.async_get_device(identifiers={(DOMAIN, equip_id)})
            if device:
                device_registry.async_update_device(
                    device.id,
                    name=f"Batterie StorCube {equip_id} (Esclave)"
                )
            
            if equip_id not in coordinator.individual_sensors:
                # Créer les capteurs réels pour cette nouvelle batterie
                _LOGGER.info("Nouvelle batterie esclave détectée, création des capteurs: %s", equip_id)
                await create_individual_battery_sensors_for_battery(hass, config_entry, equip_id, battery_info)
                new_batteries_detected = True
                _LOGGER.info("Nouvelle batterie esclave détectée et capteurs créés: %s", equip_id)
            else:
                # Mettre à jour les capteurs existants avec les nouvelles données
                if equip_id in coordinator.individual_sensors:
                    for sensor in coordinator.individual_sensors[equip_id]:
                        if hasattr(sensor, 'handle_state_update'):
                            sensor.handle_state_update(battery_info)
        
        # Si de nouvelles batteries ont été détectées, mettre à jour la vue Lovelace (temporairement désactivé)
        if new_batteries_detected:
            _LOGGER.info("Nouvelles batteries détectées, mise à jour de la vue Lovelace...")
            # await update_lovelace_view_dynamically(hass, config_entry)
        
    except Exception as e:
        _LOGGER.error("Erreur lors de la mise à jour des capteurs individuels: %s", e)

async def create_lovelace_view(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Create the Lovelace view for Storcube."""
    device_id = config_entry.data[CONF_DEVICE_ID]
    
    # Attendre un peu pour que les capteurs soient créés
    await asyncio.sleep(2)
    
    # Récupérer le coordinateur et le gestionnaire de batteries
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    battery_manager = coordinator.battery_manager
    
    # Créer les cartes pour les batteries individuelles
    individual_battery_cards = []
    battery_summary_entities = []
    
    for equip_id, battery_info in battery_manager.get_all_batteries().items():
        role = "Maître" if battery_info.is_master else "Esclave"
        
        # Carte pour chaque batterie individuelle
        individual_battery_cards.append({
            "type": "grid",
            "columns": 2,
            "title": f"Batterie {equip_id} ({role})",
            "cards": [
                {
                    "type": "gauge",
                    "entity": f"sensor.{device_id}_battery_{equip_id}_level",
                    "name": "Niveau",
                    "min": 0,
                    "max": 100,
                    "severity": {
                        "green": 50,
                        "yellow": 25,
                        "red": 10
                    }
                },
                {
                    "type": "sensor",
                    "entity": f"sensor.{device_id}_battery_{equip_id}_temperature",
                    "name": "Température",
                    "icon": "mdi:thermometer"
                },
                {
                    "type": "sensor",
                    "entity": f"sensor.{device_id}_battery_{equip_id}_capacity",
                    "name": "Capacité",
                    "icon": "mdi:battery-charging"
                }
            ]
        })
        
        # Ajouter les entités pour le résumé
        battery_summary_entities.extend([
            {
                "entity": f"sensor.{device_id}_battery_{equip_id}_level",
                "name": f"Batterie {battery_short_id}"
            }
        ])
    
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
                "type": "entities",
                "title": "Résumé des Batteries",
                "entities": battery_summary_entities
            },
            {
                "type": "grid",
                "columns": 2,
                "square": False,
                "cards": [
                    {
                        "type": "gauge",
                        "entity": f"sensor.{device_id}_battery_level",
                        "name": "Niveau Batterie Global",
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
            }
        ]
    }
    
    # Ajouter les cartes des batteries individuelles
    view_config["cards"].extend(individual_battery_cards)
    
    # Ajouter le graphique d'historique à la fin
    view_config["cards"].append({
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
    })

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

async def update_lovelace_view_dynamically(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Mettre à jour dynamiquement la vue Lovelace quand de nouvelles batteries sont détectées."""
    try:
        # Attendre un peu pour que les capteurs soient créés
        await asyncio.sleep(1)
        
        # Recréer la vue Lovelace avec les nouvelles batteries
        await create_lovelace_view(hass, config_entry)
        _LOGGER.info("Vue Lovelace mise à jour dynamiquement")
        
    except Exception as e:
        _LOGGER.error("Erreur lors de la mise à jour dynamique de la vue Lovelace: %s", str(e))

class StorcubeBatterySensor(SensorEntity):
    """Capteur pour les données de la batterie solaire."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        self._config = config
        self._websocket_data = {}
        self._rest_data = {}
        self._device_info = {}
        self._attr_native_value = None
    
    def _get_value_from_sources(self, key: str, default=None, alt_keys=None):
        """Helper pour récupérer une valeur depuis toutes les sources disponibles.
        
        Args:
            key: Clé principale à chercher
            default: Valeur par défaut si non trouvée
            alt_keys: Liste de clés alternatives à essayer (pour mapping WebSocket)
        """
        # Chercher dans device_info d'abord (données détaillées)
        if self._device_info:
            if key in self._device_info:
                return self._device_info.get(key)
            # Essayer les clés alternatives dans device_info
            if alt_keys:
                for alt_key in alt_keys:
                    if alt_key in self._device_info:
                        return self._device_info.get(alt_key)
        
        # Chercher dans websocket_data
        if self._websocket_data:
            equip = None
            if "list" in self._websocket_data and self._websocket_data["list"]:
                equip = self._websocket_data["list"][0]
            elif isinstance(self._websocket_data, dict):
                equip = self._websocket_data
            
            if equip:
                # Essayer la clé principale
                if key in equip:
                    return equip.get(key)
                # Essayer les clés alternatives
                if alt_keys:
                    for alt_key in alt_keys:
                        if alt_key in equip:
                            return equip.get(alt_key)
            
            # Chercher directement dans websocket_data
            if key in self._websocket_data:
                return self._websocket_data.get(key)
            if alt_keys:
                for alt_key in alt_keys:
                    if alt_key in self._websocket_data:
                        return self._websocket_data.get(alt_key)
        
        # Chercher dans rest_data aussi
        if self._rest_data:
            if key in self._rest_data:
                return self._rest_data.get(key)
            if alt_keys:
                for alt_key in alt_keys:
                    if alt_key in self._rest_data:
                        return self._rest_data.get(alt_key)
        
        return default

    @property
    def device_info(self) -> dict[str, Any]:
        """Retourner les informations de l'appareil - tous les sensors partagent le même device."""
        # Tous les sensors utilisent le même device_id pour être regroupés ensemble
        device_id = self._config.get(CONF_DEVICE_ID, "storcube")
        return {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"StorCube Battery Monitor",
            "manufacturer": "StorCube",
            "model": "S1000",
        }

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Gérer la mise à jour de l'état depuis les différentes sources."""
        try:
            if "device_info" in payload:
                # Données détaillées depuis /api/device/info
                self._device_info = payload["device_info"]
                self._update_value_from_sources()
            elif "websocket_data" in payload:
                self._websocket_data = payload["websocket_data"]
                self._update_value_from_sources()
            elif "rest_data" in payload:
                rest_data = payload["rest_data"]
                self._rest_data = rest_data
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
            value = self._get_value_from_sources("soc")
            if value is not None:
                self._attr_native_value = value
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
            value = self._get_value_from_sources("invPower")
            if value is not None:
                self._attr_native_value = value
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
            value = self._get_value_from_sources("reserved")
            if value is not None:
                self._attr_native_value = value
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
        """Handle state update from data sources."""
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

    @property
    def device_info(self) -> dict[str, Any]:
        """Retourner les informations de l'appareil - tous les sensors partagent le même device."""
        # Tous les sensors utilisent le même device_id pour être regroupés ensemble
        device_id = self._config.get(CONF_DEVICE_ID, "storcube")
        return {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"StorCube Battery Monitor",
            "manufacturer": "StorCube",
            "model": "S1000",
        }

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from data sources."""
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

    @property
    def device_info(self) -> dict[str, Any]:
        """Retourner les informations de l'appareil - tous les sensors partagent le même device."""
        # Tous les sensors utilisent le même device_id pour être regroupés ensemble
        device_id = self._config.get(CONF_DEVICE_ID, "storcube")
        return {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"StorCube Battery Monitor",
            "manufacturer": "StorCube",
            "model": "S1000",
        }

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

    @property
    def device_info(self) -> dict[str, Any]:
        """Retourner les informations de l'appareil - tous les sensors partagent le même device."""
        # Tous les sensors utilisent le même device_id pour être regroupés ensemble
        device_id = self._config.get(CONF_DEVICE_ID, "storcube")
        return {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"StorCube Battery Monitor",
            "manufacturer": "StorCube",
            "model": "S1000",
        }

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from data sources."""
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

    @property
    def device_info(self) -> dict[str, Any]:
        """Retourner les informations de l'appareil - tous les sensors partagent le même device."""
        # Tous les sensors utilisent le même device_id pour être regroupés ensemble
        device_id = self._config.get(CONF_DEVICE_ID, "storcube")
        return {
            "identifiers": {(DOMAIN, device_id)},
            "name": f"StorCube Battery Monitor",
            "manufacturer": "StorCube",
            "model": "S1000",
        }

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Handle state update from data sources."""
        try:
            if isinstance(payload, dict) and "list" in payload and payload["list"]:
                # Prendre le premier équipement de la liste
                equip = payload["list"][0]
                if "isWork" in equip:
                    self._attr_native_value = 'online' if equip["isWork"] == 1 else 'offline'
                else:
                    # Si isWork n'est pas présent, considérer comme online si on a des données
                    self._attr_native_value = 'online'
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


# Nouveaux sensors depuis /api/device/info
class StorcubeVoltageSensor(StorcubeBatterySensor):
    """Représentation de la tension."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Tension Storcube"
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_voltage"
        self._attr_icon = "mdi:lightning-bolt"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            # Essayer voltage, battery_voltage, ou invVoltage
            value = self._get_value_from_sources("voltage", alt_keys=["battery_voltage", "invVoltage", "vol"])
            if value is not None:
                self._attr_native_value = float(value)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating voltage: %s", e)


class StorcubeCurrentSensor(StorcubeBatterySensor):
    """Représentation du courant."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Courant Storcube"
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_device_class = SensorDeviceClass.CURRENT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_current"
        self._attr_icon = "mdi:current-ac"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            # Essayer current, battery_current, ou invCurrent
            value = self._get_value_from_sources("current", alt_keys=["battery_current", "invCurrent", "cur"])
            if value is not None:
                self._attr_native_value = float(value)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating current: %s", e)


class StorcubeFrequencySensor(StorcubeBatterySensor):
    """Représentation de la fréquence."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Fréquence Storcube"
        self._attr_native_unit_of_measurement = "Hz"
        self._attr_device_class = None
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_frequency"
        self._attr_icon = "mdi:sine-wave"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            value = self._get_value_from_sources("frequency")
            if value is not None:
                self._attr_native_value = float(value)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating frequency: %s", e)


class StorcubeGridVoltageSensor(StorcubeBatterySensor):
    """Représentation de la tension réseau."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Tension Réseau Storcube"
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_grid_voltage"
        self._attr_icon = "mdi:transmission-tower"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            value = self._get_value_from_sources("grid_voltage")
            if value is not None:
                self._attr_native_value = float(value)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating grid voltage: %s", e)


class StorcubeLoadPowerSensor(StorcubeBatterySensor):
    """Représentation de la puissance de charge."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Puissance Charge Storcube"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_load_power"
        self._attr_icon = "mdi:home-lightning-bolt"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            # Essayer load_power, outputPower, ou invPower
            value = self._get_value_from_sources("load_power", alt_keys=["outputPower", "invPower", "output_power"])
            if value is not None:
                self._attr_native_value = float(value)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating load power: %s", e)


class StorcubeChargePowerSensor(StorcubeBatterySensor):
    """Représentation de la puissance de charge de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Puissance Charge Batterie Storcube"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_charge_power"
        self._attr_icon = "mdi:battery-charging"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            # Pour charge_power, on peut calculer depuis invPower si positif
            value = self._get_value_from_sources("charge_power", alt_keys=["chargePower", "charging_power"])
            if value is None:
                # Essayer de calculer depuis invPower (si positif = charge)
                inv_power = self._get_value_from_sources("invPower", alt_keys=["inv_power", "power"])
                if inv_power is not None and float(inv_power) > 0:
                    value = inv_power
            if value is not None:
                self._attr_native_value = float(value)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating charge power: %s", e)


class StorcubeDischargePowerSensor(StorcubeBatterySensor):
    """Représentation de la puissance de décharge de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Puissance Décharge Batterie Storcube"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_discharge_power"
        self._attr_icon = "mdi:battery-arrow-down"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            # Pour discharge_power, on peut calculer depuis invPower si négatif
            value = self._get_value_from_sources("discharge_power", alt_keys=["dischargePower", "discharging_power"])
            if value is None:
                # Essayer de calculer depuis invPower (si négatif = décharge)
                inv_power = self._get_value_from_sources("invPower", alt_keys=["inv_power", "power"])
                if inv_power is not None and float(inv_power) < 0:
                    value = abs(float(inv_power))
            if value is not None:
                self._attr_native_value = float(value)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating discharge power: %s", e)


class StorcubeEnergySensor(StorcubeBatterySensor):
    """Représentation de l'énergie totale depuis /api/statistics/energy."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the sensor."""
        super().__init__(config)
        self._attr_name = "Énergie Totale Storcube"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_energy"
        self._attr_icon = "mdi:lightning-bolt-circle"

    def _update_value_from_sources(self):
        """Mettre à jour la valeur depuis les sources disponibles."""
        try:
            # Essayer energy, total_energy, ou capacity (en Wh, convertir en kWh)
            value = self._get_value_from_sources("energy", alt_keys=["total_energy", "totalEnergy"])
            if value is None:
                # Essayer capacity (en Wh) et convertir en kWh
                capacity = self._get_value_from_sources("capacity", alt_keys=["battery_capacity"])
                if capacity is not None:
                    # Si capacity est en Wh, convertir en kWh
                    value = float(capacity) / 1000.0
            if value is not None:
                self._attr_native_value = float(value)
                self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating energy: %s", e)

async def websocket_to_mqtt(hass: HomeAssistant, config: ConfigType, config_entry: ConfigEntry) -> None:
    """Handle websocket connection and update sensors."""
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
                            
                            # Récupérer le coordinateur pour obtenir toutes les batteries découvertes
                            coordinator = hass.data[DOMAIN][config_entry.entry_id]
                            battery_manager = coordinator.battery_manager if hasattr(coordinator, 'battery_manager') else None
                            
                            # Construire la liste des equipIds à demander
                            equip_ids = [config[CONF_DEVICE_ID]]
                            if battery_manager:
                                all_batteries = battery_manager.get_all_batteries()
                                for equip_id in all_batteries.keys():
                                    if equip_id not in equip_ids:
                                        equip_ids.append(equip_id)
                            
                            # Send initial request avec toutes les batteries découvertes
                            request_data = {"reportEquip": equip_ids}
                            await websocket.send(json.dumps(request_data))
                            _LOGGER.info("Requête WebSocket envoyée pour %d batterie(s): %s", len(equip_ids), equip_ids)

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
                                                
                                                # Récupérer le coordinateur et le gestionnaire de batteries
                                                coordinator = hass.data[DOMAIN][config_entry.entry_id]
                                                if not hasattr(coordinator, 'battery_manager') or coordinator.battery_manager is None:
                                                    _LOGGER.warning("Battery manager non initialisé, création...")
                                                    from .battery_manager import StorCubeBatteryManager
                                                    coordinator.battery_manager = StorCubeBatteryManager()
                                                
                                                battery_manager = coordinator.battery_manager
                                                
                                                # Vérifier si c'est un message WebSocket avec l'ID de l'équipement
                                                if config[CONF_DEVICE_ID] in json_data:
                                                    equip_data = json_data[config[CONF_DEVICE_ID]]
                                                    _LOGGER.debug("Mise à jour des capteurs avec les données WebSocket: %s", equip_data)
                                                    
                                                    battery_manager.update_from_websocket(equip_data)
                                                    
                                                    # Mettre à jour les capteurs globaux
                                                    if hasattr(coordinator, 'global_sensors') and coordinator.global_sensors:
                                                        for sensor in coordinator.global_sensors:
                                                            sensor.handle_state_update(equip_data)
                                                    
                                                    # Mettre à jour les capteurs individuels (détection automatique)
                                                    await update_individual_battery_sensors(hass, config_entry, battery_manager)
                                                    
                                                    # Mettre à jour les sensors individuels avec les données WebSocket
                                                    if hasattr(coordinator, 'individual_sensors'):
                                                        for equip_id, sensors in coordinator.individual_sensors.items():
                                                            battery_info = battery_manager.get_battery_info(equip_id)
                                                            if battery_info:
                                                                for sensor in sensors:
                                                                    if hasattr(sensor, 'handle_state_update'):
                                                                        sensor.handle_state_update(battery_info)
                                                
                                                # Vérifier aussi si les données sont directement dans json_data avec "list"
                                                elif "list" in json_data and isinstance(json_data["list"], list):
                                                    _LOGGER.info("Données WebSocket avec 'list' détectées directement: %d batteries", len(json_data["list"]))
                                                    battery_manager.update_from_websocket(json_data)
                                                    
                                                    # Mettre à jour les capteurs globaux
                                                    if hasattr(coordinator, 'global_sensors') and coordinator.global_sensors:
                                                        for sensor in coordinator.global_sensors:
                                                            sensor.handle_state_update(json_data)
                                                    
                                                    # Mettre à jour les capteurs individuels (détection automatique)
                                                    await update_individual_battery_sensors(hass, config_entry, battery_manager)
                                                    
                                                    # Mettre à jour les sensors individuels avec les données WebSocket
                                                    if hasattr(coordinator, 'individual_sensors'):
                                                        for equip_id, sensors in coordinator.individual_sensors.items():
                                                            battery_info = battery_manager.get_battery_info(equip_id)
                                                            if battery_info:
                                                                for sensor in sensors:
                                                                    if hasattr(sensor, 'handle_state_update'):
                                                                        sensor.handle_state_update(battery_info)
                                                
                                                # Vérifier si c'est une réponse d'API REST
                                                elif "code" in json_data and "data" in json_data and json_data["code"] == 200:
                                                    data_list = json_data.get("data", [])
                                                    if data_list and isinstance(data_list, list):
                                                        equip_data = data_list[0]
                                                        _LOGGER.debug("Mise à jour des capteurs avec les données de l'API: %s", equip_data)
                                                        
                                                        # Récupérer le coordinateur et le gestionnaire de batteries
                                                        coordinator = hass.data[DOMAIN][config_entry.entry_id]
                                                        battery_manager = coordinator.battery_manager
                                                        battery_manager.update_from_output_api(equip_data)
                                                        
                                                        # Mettre à jour les capteurs globaux
                                                        for sensor in coordinator.global_sensors:
                                                            sensor.handle_state_update(equip_data)
                                                        
                                                        # Ne pas mettre à jour les capteurs individuels ici car l'API output n'a pas les données détaillées
                                                        # Les capteurs individuels seront mis à jour quand les données WebSocket arriveront
                                                else:
                                                    # Extraire les données d'équipement pour le format WebSocket
                                                    equip_data = next(iter(json_data.values()), {})
                                                    
                                                    # Vérifier si les données d'équipement sont valides
                                                    if equip_data and isinstance(equip_data, dict):
                                                        # Si les données sont dans la liste
                                                        if "list" in equip_data and equip_data["list"]:
                                                            _LOGGER.debug("Mise à jour des capteurs avec les données de la liste: %s", equip_data)
                                                            
                                                            # Récupérer le coordinateur et le gestionnaire de batteries
                                                            coordinator = hass.data[DOMAIN][config_entry.entry_id]
                                                            if not hasattr(coordinator, 'battery_manager') or coordinator.battery_manager is None:
                                                                _LOGGER.warning("Battery manager non initialisé, création...")
                                                                from .battery_manager import StorCubeBatteryManager
                                                                coordinator.battery_manager = StorCubeBatteryManager()
                                                            
                                                            battery_manager = coordinator.battery_manager
                                                            battery_manager.update_from_websocket(equip_data)
                                                            
                                                            # Mettre à jour les capteurs globaux
                                                            if hasattr(coordinator, 'global_sensors') and coordinator.global_sensors:
                                                                for sensor in coordinator.global_sensors:
                                                                    sensor.handle_state_update(equip_data)
                                                            
                                                            # Mettre à jour les capteurs individuels (détection automatique)
                                                            await update_individual_battery_sensors(hass, config_entry, battery_manager)
                                                            
                                                            # Mettre à jour les sensors individuels avec les données WebSocket
                                                            if hasattr(coordinator, 'individual_sensors'):
                                                                for equip_id, sensors in coordinator.individual_sensors.items():
                                                                    battery_info = battery_manager.get_battery_info(equip_id)
                                                                    if battery_info:
                                                                        for sensor in sensors:
                                                                            if hasattr(sensor, 'handle_state_update'):
                                                                                sensor.handle_state_update(battery_info)
                                                        # Si les données sont au niveau racine
                                                        else:
                                                            _LOGGER.debug("Mise à jour des capteurs avec les données racines: %s", equip_data)
                                                            
                                                            # Récupérer le coordinateur et le gestionnaire de batteries
                                                            coordinator = hass.data[DOMAIN][config_entry.entry_id]
                                                            if not hasattr(coordinator, 'battery_manager') or coordinator.battery_manager is None:
                                                                _LOGGER.warning("Battery manager non initialisé, création...")
                                                                from .battery_manager import StorCubeBatteryManager
                                                                coordinator.battery_manager = StorCubeBatteryManager()
                                                            
                                                            battery_manager = coordinator.battery_manager
                                                            battery_manager.update_from_websocket(equip_data)
                                                            
                                                            # Mettre à jour les capteurs globaux
                                                            if hasattr(coordinator, 'global_sensors') and coordinator.global_sensors:
                                                                for sensor in coordinator.global_sensors:
                                                                    sensor.handle_state_update(equip_data)
                                                            
                                                            # Mettre à jour les capteurs individuels (détection automatique)
                                                            await update_individual_battery_sensors(hass, config_entry, battery_manager)
                                                            
                                                            # Mettre à jour les sensors individuels avec les données WebSocket
                                                            if hasattr(coordinator, 'individual_sensors'):
                                                                for equip_id, sensors in coordinator.individual_sensors.items():
                                                                    battery_info = battery_manager.get_battery_info(equip_id)
                                                                    if battery_info:
                                                                        for sensor in sensors:
                                                                            if hasattr(sensor, 'handle_state_update'):
                                                                                sensor.handle_state_update(battery_info)
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
    """Handle output API connection and update sensors."""
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
                                                _LOGGER.debug("Mise à jour des capteurs avec les données de l'API output: %s", equip_data)
                                                
                                                # Récupérer le coordinateur et le gestionnaire de batteries
                                                coordinator = hass.data[DOMAIN][config_entry.entry_id]
                                                if not hasattr(coordinator, 'battery_manager') or coordinator.battery_manager is None:
                                                    _LOGGER.warning("Battery manager non initialisé dans output_api_to_mqtt, création...")
                                                    from .battery_manager import StorCubeBatteryManager
                                                    coordinator.battery_manager = StorCubeBatteryManager()
                                                
                                                battery_manager = coordinator.battery_manager
                                                battery_manager.update_from_output_api(equip_data)
                                                
                                                # Mettre à jour les capteurs globaux
                                                if hasattr(coordinator, 'global_sensors') and coordinator.global_sensors:
                                                    for sensor in coordinator.global_sensors:
                                                        sensor.handle_state_update({"rest_data": equip_data})
                                                
                                                # Mettre à jour les capteurs individuels (détection automatique)
                                                # L'API output contient equipIds qui permet de détecter les batteries
                                                await update_individual_battery_sensors(hass, config_entry, battery_manager)
                                                
                                                # Mettre à jour les sensors individuels avec les données de l'API output
                                                if hasattr(coordinator, 'individual_sensors'):
                                                    for equip_id, sensors in coordinator.individual_sensors.items():
                                                        battery_info = battery_manager.get_battery_info(equip_id)
                                                        if battery_info:
                                                            for sensor in sensors:
                                                                if hasattr(sensor, 'handle_state_update'):
                                                                    sensor.handle_state_update(battery_info)
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


class StorcubeFirmwareSensor(StorcubeBatterySensor):
    """Capteur pour les informations de firmware StorCube."""

    def __init__(self, config: ConfigType, coordinator=None) -> None:
        """Initialiser le capteur de firmware."""
        super().__init__(config)
        self.coordinator = coordinator
        self._attr_name = "Firmware StorCube"
        self._attr_unique_id = f"{config[CONF_DEVICE_ID]}_firmware"
        self._attr_icon = "mdi:update"
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None
        self._attr_state_class = None
        self.hass = None  # Sera défini lors de l'ajout à hass
        self._firmware_data = None  # Stockage des données firmware

    def _update_value_from_sources(self):
        """Mettre à jour la valeur du capteur."""
        # Ne pas écraser les données firmware avec les données WebSocket/REST
        # Les données firmware sont gérées par handle_state_update
        if hasattr(self, '_firmware_data') and self._firmware_data:
            current_version = self._firmware_data.get("current_version", "Inconnue")
            latest_version = self._firmware_data.get("latest_version", "Inconnue")
            upgrade_available = self._firmware_data.get("upgrade_available", False)
            
            if upgrade_available:
                self._attr_native_value = f"Mise à jour disponible ({latest_version})"
            else:
                self._attr_native_value = f"À jour ({current_version})"
            return
        
        # Récupérer les données de firmware depuis le coordinateur
        if self.hass and DOMAIN in self.hass.data:
            for entry_id, coordinator in self.hass.data[DOMAIN].items():
                if hasattr(coordinator, 'data') and 'firmware' in coordinator.data:
                    firmware_data = coordinator.data['firmware']
                    current_version = firmware_data.get("current_version", "Inconnue")
                    latest_version = firmware_data.get("latest_version", "Inconnue")
                    upgrade_available = firmware_data.get("upgrade_available", False)
                    
                    if upgrade_available:
                        self._attr_native_value = f"Mise à jour disponible ({latest_version})"
                    else:
                        self._attr_native_value = f"À jour ({current_version})"
                    return
        
        # Valeur par défaut si pas de données
        self._attr_native_value = "Inconnue"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Retourner les attributs supplémentaires."""
        # Utiliser les données stockées si disponibles
        if hasattr(self, '_firmware_data') and self._firmware_data:
            return self._firmware_data
        
        # Sinon, essayer de récupérer depuis le coordinateur
        if self.hass and DOMAIN in self.hass.data:
            for entry_id, coordinator in self.hass.data[DOMAIN].items():
                if hasattr(coordinator, 'data') and 'firmware' in coordinator.data:
                    firmware_data = coordinator.data['firmware']
                    return {
                        "current_version": firmware_data.get("current_version", "Inconnue"),
                        "latest_version": firmware_data.get("latest_version", "Inconnue"),
                        "upgrade_available": firmware_data.get("upgrade_available", False),
                        "firmware_notes": firmware_data.get("firmware_notes", []),
                        "last_check": firmware_data.get("last_check", "Jamais"),
                    }
        
        return {
            "current_version": "Inconnue",
            "latest_version": "Inconnue",
            "upgrade_available": False,
            "firmware_notes": [],
            "last_check": "Jamais",
        }

    async def async_added_to_hass(self) -> None:
        """Appelé quand l'entité est ajoutée à Home Assistant."""
        await super().async_added_to_hass()
        self.hass = self.hass  # Définir la référence hass
        
        # Si pas de coordinateur, essayer de le récupérer depuis hass.data
        if not self.coordinator and DOMAIN in self.hass.data:
            for entry_id, coordinator in self.hass.data[DOMAIN].items():
                self.coordinator = coordinator
                break
        
        if self.coordinator:
            self.async_on_remove(
                self.coordinator.async_add_listener(self.async_write_ha_state)
            )

    async def async_update(self) -> None:
        """Mettre à jour le capteur."""
        if self.coordinator:
            await self.coordinator.async_request_refresh()
        else:
            # Mise à jour manuelle si pas de coordinateur
            self._update_value_from_sources()
            self.async_write_ha_state()

    @callback
    def handle_state_update(self, payload: dict[str, Any]) -> None:
        """Gérer les mises à jour d'état depuis le coordinateur."""
        # Appeler la méthode parent pour les données WebSocket/REST
        super().handle_state_update(payload)
        
        # Mettre à jour les données firmware si disponibles
        if "firmware" in payload:
            firmware_data = payload["firmware"]
            current_version = firmware_data.get("current_version", "Inconnue")
            latest_version = firmware_data.get("latest_version", "Inconnue")
            upgrade_available = firmware_data.get("upgrade_available", False)
            firmware_notes = firmware_data.get("firmware_notes", [])
            last_check = firmware_data.get("last_check", "Jamais")
            
            # Mettre à jour l'état principal
            if upgrade_available:
                self._attr_native_value = f"Mise à jour disponible ({latest_version})"
            else:
                self._attr_native_value = f"À jour ({current_version})"
            
            # Stocker les données firmware pour les attributs
            self._firmware_data = {
                "current_version": current_version,
                "latest_version": latest_version,
                "upgrade_available": upgrade_available,
                "firmware_notes": firmware_notes,
                "last_check": last_check
            }
            
            _LOGGER.info("Capteur firmware mis à jour: %s (upgrade: %s)", 
                        self._attr_native_value, upgrade_available)
        
        # Notifier Home Assistant du changement
        self.async_write_ha_state() 
