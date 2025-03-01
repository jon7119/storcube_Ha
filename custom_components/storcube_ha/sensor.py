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
        
        # Capteurs solaires
        StorcubeSolarPowerSensor(config),
        StorcubeSolarVoltageSensor(config),
        StorcubeSolarCurrentSensor(config),
        StorcubeSolarEnergySensor(config),
        
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

    # Start websocket connection
    asyncio.create_task(websocket_to_mqtt(hass, config))

class StorcubeBatteryLevelSensor(SensorEntity):
    """Représentation du niveau de batterie."""

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
            self._attr_native_value = payload.get("battery_level")
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
            self._attr_native_value = payload.get("battery_power")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery power: %s", e)

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
            self._attr_native_value = payload.get("battery_threshold")
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
            self._attr_native_value = payload.get("battery_voltage")
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
            self._attr_native_value = payload.get("battery_current")
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
            self._attr_native_value = payload.get("battery_temperature")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery temperature: %s", e)

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
            self._attr_native_value = payload.get("battery_capacity")
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
            self._attr_native_value = payload.get("battery_health")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating battery health: %s", e)

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
            self._attr_native_value = payload.get("solar_power")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating solar power: %s", e)

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
            self._attr_native_value = payload.get("output_power")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating output power: %s", e)

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
            self._attr_native_value = payload.get("status")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Error updating status: %s", e)

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

async def websocket_to_mqtt(hass: HomeAssistant, config: ConfigType) -> None:
    """Handle websocket connection and forward data to MQTT."""
    while True:
        try:
            # Get authentication token
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "okhttp/3.12.11"
            }
            payload = {
                "appCode": config[CONF_APP_CODE],
                "loginName": config[CONF_LOGIN_NAME],
                "password": config[CONF_AUTH_PASSWORD]
            }
            
            timeout = aiohttp.ClientTimeout(total=30, connect=20)
            connector = aiohttp.TCPConnector(verify_ssl=False)
            
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                _LOGGER.debug("Tentative de connexion à %s avec timeout=%s", TOKEN_URL, timeout)
                try:
                    # Force HTTP
                    login_url = TOKEN_URL.replace("https://", "http://")
                    async with session.post(
                        login_url,
                        json=payload,
                        headers=headers
                    ) as response:
                        _LOGGER.debug("Statut de la réponse: %d", response.status)
                        response_text = await response.text()
                        _LOGGER.debug("Réponse brute: %s", response_text)
                        
                        if response.status != 200:
                            _LOGGER.error("Erreur serveur: %d - %s", response.status, response_text)
                            raise Exception(f"Erreur serveur: {response.status}")
                        
                        token_data = json.loads(response_text)
                        if token_data.get("code") != 200:
                            _LOGGER.error("Échec de l'authentification: %s", token_data.get("message", "Erreur inconnue"))
                            raise Exception("Échec de l'authentification")
                        token = token_data["data"]["token"]
                        _LOGGER.info("Token obtenu avec succès")

                    # Get initial data
                    headers = {
                        "Authorization": token,
                        "Content-Type": "application/json",
                        "appCode": config[CONF_APP_CODE]
                    }

                    # Get output info
                    output_url = OUTPUT_URL.replace("https://", "http://")
                    async with session.get(output_url, headers=headers) as response:
                        if response.status == 200:
                            output_data = await response.json()
                            if output_data.get("data"):
                                await mqtt.async_publish(
                                    hass,
                                    TOPIC_OUTPUT,
                                    json.dumps(output_data["data"]),
                                    config[CONF_PORT],
                                    False,
                                )

                    # Get firmware info
                    firmware_url = f"{FIRMWARE_URL.replace('https://', 'http://')}?equipId={config[CONF_DEVICE_ID]}"
                    async with session.get(firmware_url, headers=headers) as response:
                        if response.status == 200:
                            firmware_data = await response.json()
                            if firmware_data.get("data"):
                                await mqtt.async_publish(
                                    hass,
                                    TOPIC_FIRMWARE,
                                    json.dumps(firmware_data["data"]),
                                    config[CONF_PORT],
                                    False,
                                )

                    # Connect to websocket
                    uri = f"{WS_URI}{token}"
                    _LOGGER.debug("Connexion WebSocket à %s", uri)
                    
                    ws_headers = {
                        "Authorization": token,
                        "Content-Type": "application/json",
                        "User-Agent": "okhttp/3.12.11"
                    }

                    async with session.ws_connect(
                        uri,
                        headers=ws_headers,
                        heartbeat=30
                    ) as websocket:
                        _LOGGER.info("Connexion WebSocket établie")

                        request_data = {"reportEquip": [config[CONF_DEVICE_ID]]}
                        await websocket.send_json(request_data)
                        _LOGGER.debug("Requête envoyée: %s", request_data)

                        while True:
                            try:
                                msg = await websocket.receive(timeout=60)
                                
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    try:
                                        message = msg.data
                                        _LOGGER.debug("Message WebSocket reçu: %s", message)
                                        
                                        if message.strip():
                                            json_data = json.loads(message)
                                            
                                            if isinstance(json_data, dict):
                                                equip_data = next(iter(json_data.values()), {})
                                                clean_message = json.dumps(equip_data)
                                                
                                                await mqtt.async_publish(
                                                    hass,
                                                    TOPIC_BATTERY,
                                                    clean_message,
                                                    config[CONF_PORT],
                                                    False,
                                                )
                                                _LOGGER.debug("Données batterie publiées sur MQTT: %s", clean_message)

                                                # Update output and firmware info periodically
                                                async with session.get(output_url, headers=headers) as response:
                                                    if response.status == 200:
                                                        output_data = await response.json()
                                                        if output_data.get("data"):
                                                            await mqtt.async_publish(
                                                                hass,
                                                                TOPIC_OUTPUT,
                                                                json.dumps(output_data["data"]),
                                                                config[CONF_PORT],
                                                                False,
                                                            )

                                                async with session.get(firmware_url, headers=headers) as response:
                                                    if response.status == 200:
                                                        firmware_data = await response.json()
                                                        if firmware_data.get("data"):
                                                            await mqtt.async_publish(
                                                                hass,
                                                                TOPIC_FIRMWARE,
                                                                json.dumps(firmware_data["data"]),
                                                                config[CONF_PORT],
                                                                False,
                                                            )
                                    
                                    except json.JSONDecodeError as e:
                                        _LOGGER.error("Message JSON invalide reçu: %s", str(e))
                                        continue
                                        
                                elif msg.type == aiohttp.WSMsgType.CLOSED:
                                    _LOGGER.warning("Connexion WebSocket fermée")
                                    break
                                elif msg.type == aiohttp.WSMsgType.ERROR:
                                    _LOGGER.error("Erreur WebSocket: %s", str(msg.data))
                                    break
                                    
                            except asyncio.TimeoutError:
                                _LOGGER.warning("Timeout WebSocket, envoi heartbeat...")
                                await websocket.send_json(request_data)
                                continue

                except asyncio.TimeoutError as te:
                    _LOGGER.error("Timeout lors de la connexion: %s", str(te))
                    await asyncio.sleep(5)
                    continue
                except aiohttp.ClientError as ce:
                    _LOGGER.error("Erreur de connexion: %s", str(ce))
                    await asyncio.sleep(5)
                    continue
                except Exception as e:
                    _LOGGER.error("Erreur inattendue: %s", str(e))
                    await asyncio.sleep(5)
                    continue

        except Exception as e:
            _LOGGER.error("Erreur de connexion: %s", str(e))
            await asyncio.sleep(5) 