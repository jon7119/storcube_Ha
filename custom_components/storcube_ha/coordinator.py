"""Coordinateur de données pour l'intégration Storcube Battery Monitor."""
import asyncio
import logging
from datetime import timedelta
import requests
import json
import websockets

import paho.mqtt.client as mqtt
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
)
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers import device_registry as dr
from homeassistant.components import mqtt

from .const import (
    DOMAIN,
    CONF_APP_CODE,
    CONF_LOGIN_NAME,
    CONF_DEVICE_PASSWORD,
    TOPIC_BASE,
    TOPIC_BATTERY_STATUS,
    TOPIC_BATTERY_POWER,
    TOPIC_BATTERY_SOLAR,
    TOPIC_BATTERY_CAPACITY,
    TOPIC_BATTERY_OUTPUT,
    TOPIC_BATTERY_REPORT,
    TOPIC_BATTERY_COMMAND,
    TOPIC_BATTERY_SET_POWER,
    TOPIC_BATTERY_SET_THRESHOLD,
    MQTT_TOPIC_PREFIX,
    MQTT_TOPIC_STATUS,
    MQTT_TOPIC_POWER,
    MQTT_TOPIC_SOLAR,
)

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)  # Activer le logging détaillé

# URLs de l'API
TOKEN_URL = "http://baterway.com/api/user/app/login"
FIRMWARE_URL = "http://baterway.com/api/equip/version/need/upgrade"
OUTPUT_URL = "http://baterway.com/api/scene/user/list/V2"
SET_POWER_URL = "http://baterway.com/api/slb/equip/set/power"
SET_THRESHOLD_URL = "http://baterway.com/api/scene/threshold/set"
WS_URI = "ws://baterway.com:9501/equip/info/"

# Codes d'erreur MQTT
MQTT_ERROR_CODES = {
    0: "Connexion acceptée",
    1: "Version du protocole MQTT non supportée",
    2: "Identifiant client invalide",
    3: "Serveur indisponible",
    4: "Nom d'utilisateur ou mot de passe incorrect",
    5: "Non autorisé",
}

class StorCubeDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching StorCube data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.config_entry = config_entry
        self._topics = {
            "status": MQTT_TOPIC_STATUS,
            "power": MQTT_TOPIC_POWER,
            "solar": MQTT_TOPIC_SOLAR,
        }
        self.data = {
            "battery_level": 0,
            "battery_power": 0,
            "solar_power": 0,
            "temperature": 0,
            "status": "unknown",
        }
        self.hass = hass
        self.mqtt_client = None
        self.ws = None
        self._connection_error = None
        self._auth_token = None
        self._ws_task = None
        self._known_devices = set()  # Ensemble des equipIds connus
        
        _LOGGER.info(
            "Initialisation du coordinateur Storcube avec les paramètres: host=%s, port=%s, username=%s",
            config_entry.data[CONF_HOST],
            config_entry.data[CONF_PORT],
            config_entry.data[CONF_USERNAME],
        )

    def _get_device_info(self, equip_id, battery_data):
        """Créer les informations de l'appareil pour une batterie."""
        return {
            "identifiers": {(DOMAIN, equip_id)},
            "name": f"Batterie StorCube {equip_id}",
            "manufacturer": "StorCube",
            "model": battery_data.get("equipType", "Unknown"),
            "sw_version": battery_data.get("version", "Unknown"),
        }

    def _register_device(self, equip_id, battery_data):
        """Enregistrer un nouvel appareil dans Home Assistant."""
        if equip_id not in self._known_devices:
            device_registry = dr.async_get(self.hass)
            device_info = self._get_device_info(equip_id, battery_data)
            
            device_registry.async_get_or_create(
                config_entry_id=self.config_entry.entry_id,
                **device_info,
            )
            
            # Initialiser les données pour cette batterie
            if equip_id not in self.data:
                self.data[equip_id] = {
                    "battery_status": "{}",
                    "battery_power": "{}",
                    "battery_solar": "{}",
                    "battery_capacity": "{}",
                    "battery_output": "{}",
                    "battery_report": "{}",
                }
            
            self._known_devices.add(equip_id)
            _LOGGER.info("Nouvelle batterie détectée et enregistrée: %s", equip_id)

    def _get_mqtt_topics(self, equip_id):
        """Obtenir les topics MQTT pour une batterie spécifique."""
        return {
            "status": TOPIC_BATTERY_STATUS.format(device_id=equip_id),
            "power": TOPIC_BATTERY_POWER.format(device_id=equip_id),
            "solar": TOPIC_BATTERY_SOLAR.format(device_id=equip_id),
            "capacity": TOPIC_BATTERY_CAPACITY.format(device_id=equip_id),
            "output": TOPIC_BATTERY_OUTPUT.format(device_id=equip_id),
            "report": TOPIC_BATTERY_REPORT.format(device_id=equip_id),
        }

    def get_auth_token(self):
        """Récupérer le token d'authentification."""
        try:
            token_credentials = {
                "appCode": self.config_entry.data[CONF_APP_CODE],
                "loginName": self.config_entry.data[CONF_LOGIN_NAME],
                "password": self.config_entry.data[CONF_DEVICE_PASSWORD]
            }
            _LOGGER.debug("Tentative d'authentification avec: appCode=%s, loginName=%s",
                         self.config_entry.data[CONF_APP_CODE],
                         self.config_entry.data[CONF_LOGIN_NAME])
            
            headers = {'Content-Type': 'application/json'}
            response = requests.post(TOKEN_URL, json=token_credentials, headers=headers)
            response.raise_for_status()
            data = response.json()
            if data.get('code') == 200:
                _LOGGER.info("Token récupéré avec succès")
                self._auth_token = data['data']['token']
                return self._auth_token
            raise Exception(f"Erreur d'authentification: {data.get('message', 'Réponse inconnue')}")
        except requests.RequestException as e:
            _LOGGER.error("Erreur lors de la récupération du token: %s", e)
            return None

    async def set_power_value(self, new_power_value):
        """Modifier la puissance de sortie."""
        if not self._auth_token:
            self._auth_token = self.get_auth_token()
            if not self._auth_token:
                return False

        headers = {
            "Authorization": self._auth_token,
            "Content-Type": "application/json",
            "appCode": self.config_entry.data[CONF_APP_CODE]
        }
        params = {
            "equipId": list(self._known_devices)[0] if self._known_devices else None,  # Utilise la première batterie détectée
            "power": new_power_value
        }

        if not params["equipId"]:
            _LOGGER.error("Aucune batterie détectée")
            return False

        try:
            response = requests.get(SET_POWER_URL, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 200:
                    _LOGGER.info("Puissance mise à jour à %sW", new_power_value)
                    return True
                _LOGGER.error("Échec API: %s", data.get('message', 'Réponse inconnue'))
            response.raise_for_status()
        except requests.RequestException as e:
            _LOGGER.error("Erreur lors de la modification de la puissance: %s", e)
        return False

    async def set_threshold_value(self, new_threshold_value):
        """Modifier le seuil de batterie."""
        if not self._auth_token:
            self._auth_token = self.get_auth_token()
            if not self._auth_token:
                return False

        headers = {
            "Authorization": self._auth_token,
            "Content-Type": "application/json",
            "appCode": self.config_entry.data[CONF_APP_CODE]
        }

        equip_id = list(self._known_devices)[0] if self._known_devices else None
        if not equip_id:
            _LOGGER.error("Aucune batterie détectée")
            return False

        payloads = [
            {"reserved": str(new_threshold_value), "equipId": equip_id},
            {"data": str(new_threshold_value), "equipId": equip_id},
            {"threshold": str(new_threshold_value), "equipId": equip_id}
        ]

        for payload in payloads:
            try:
                response = requests.post(SET_THRESHOLD_URL, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                if data.get("code") == 200:
                    _LOGGER.info("Seuil modifié à %s%%", new_threshold_value)
                    return True
                _LOGGER.warning("API a renvoyé un échec : %s", data.get('message', 'Réponse inconnue'))
            except requests.RequestException as e:
                _LOGGER.error("Erreur lors de la modification du seuil: %s", e)
        return False

    async def _async_update_data(self):
        """Update data via MQTT."""
        return self.data

    async def async_mqtt_message_received(self, msg):
        """Handle received MQTT message."""
        topic = msg.topic
        payload = msg.payload
        try:
            data = json.loads(payload)
            if "status" in topic:
                self.data["status"] = "online" if data.get("value") == 1 else "offline"
            elif "power" in topic:
                self.data["battery_power"] = float(data.get("value", 0))
            elif "solar" in topic:
                self.data["solar_power"] = float(data.get("value", 0))
            
            # Notifier Home Assistant que les données ont changé
            self.async_set_updated_data(self.data)
        except json.JSONDecodeError:
            _LOGGER.error("Erreur lors du décodage du message MQTT: %s", payload)
        except ValueError:
            _LOGGER.error("Valeur invalide dans le message MQTT: %s", payload)

    async def async_setup(self):
        """Set up the coordinator."""
        try:
            # S'abonner aux topics MQTT
            for topic in self._topics.values():
                await mqtt.async_subscribe(
                    self.hass,
                    topic,
                    self.async_mqtt_message_received,
                    0,
                )
            return True
        except Exception as err:
            _LOGGER.error("Erreur lors de la configuration MQTT: %s", err)
            raise ConfigEntryNotReady from err

    async def _websocket_listener(self):
        """Écouter les données WebSocket et les publier sur MQTT."""
        while True:
            try:
                _LOGGER.info("Connexion au WebSocket...")
                headers = {"Authorization": self._auth_token}
                async with websockets.connect(WS_URI, extra_headers=headers) as websocket:
                    _LOGGER.info("Connecté au WebSocket")
                    while True:
                        try:
                            message = await websocket.recv()
                            data = json.loads(message)
                            _LOGGER.debug("Données WebSocket reçues: %s", data)

                            if "list" in data:
                                for battery in data["list"]:
                                    equip_id = battery.get("equipId")
                                    if not equip_id:
                                        continue

                                    # Enregistrer la batterie si elle est nouvelle
                                    self._register_device(equip_id, battery)
                                    
                                    # Obtenir les topics pour cette batterie
                                    topics = self._get_mqtt_topics(equip_id)
                                    
                                    # Publier les données sur MQTT
                                    if self.mqtt_client and self.mqtt_client.is_connected():
                                        # Status
                                        self.mqtt_client.publish(topics["status"], json.dumps({
                                            "value": battery.get("fgOnline", 0)
                                        }))
                                        
                                        # Power
                                        self.mqtt_client.publish(topics["power"], json.dumps({
                                            "value": battery.get("power", 0)
                                        }))
                                        
                                        # Solar
                                        self.mqtt_client.publish(topics["solar"], json.dumps({
                                            "value": battery.get("solarPower", 0)
                                        }))
                                        
                                        # Capacity
                                        self.mqtt_client.publish(topics["capacity"], json.dumps({
                                            "value": battery.get("soc", 0)
                                        }))
                                        
                                        # Output
                                        self.mqtt_client.publish(topics["output"], json.dumps(battery))
                                        
                                        # Report (données complètes pour cette batterie)
                                        battery_report = {"list": [battery]}
                                        self.mqtt_client.publish(topics["report"], json.dumps(battery_report))
                                        
                                        # Mettre à jour les données dans le coordinateur
                                        self.data[equip_id] = {
                                            "battery_status": json.dumps({"value": battery.get("fgOnline", 0)}),
                                            "battery_power": json.dumps({"value": battery.get("power", 0)}),
                                            "battery_solar": json.dumps({"value": battery.get("solarPower", 0)}),
                                            "battery_capacity": json.dumps({"value": battery.get("soc", 0)}),
                                            "battery_output": json.dumps(battery),
                                            "battery_report": json.dumps(battery_report),
                                        }
                                    
                                    _LOGGER.debug("Données publiées pour la batterie %s", equip_id)
                                
                                # Mettre à jour toutes les entités
                                self.async_set_updated_data(self.data)

                        except json.JSONDecodeError as e:
                            _LOGGER.error("Erreur de décodage JSON: %s", e)
                        except Exception as e:
                            _LOGGER.error("Erreur lors du traitement des données WebSocket: %s", e)
                            break

            except websockets.exceptions.ConnectionClosed:
                _LOGGER.warning("Connexion WebSocket fermée, tentative de reconnexion...")
            except Exception as e:
                _LOGGER.error("Erreur WebSocket: %s", e)
            
            await asyncio.sleep(5)  # Attendre avant de réessayer

    async def _setup_mqtt(self):
        """Configurer la connexion MQTT."""
        if self.mqtt_client:
            _LOGGER.info("Déconnexion du client MQTT existant")
            self.mqtt_client.disconnect()

        self.mqtt_client = mqtt.Client(client_id=f"ha-storcube-{self.config_entry.entry_id}")
        
        def on_connect(client, userdata, flags, rc):
            """Callback lors de la connexion."""
            if rc == 0:
                _LOGGER.info("Connecté au broker MQTT avec succès")
                # Les abonnements seront gérés dynamiquement lors de la détection des batteries
            else:
                error_msg = MQTT_ERROR_CODES.get(rc, f"Erreur inconnue (code {rc})")
                self._connection_error = f"Échec de connexion MQTT : {error_msg}"
                _LOGGER.error(self._connection_error)
                
                if rc in [4, 5]:
                    _LOGGER.error("Vérifiez vos identifiants MQTT (nom d'utilisateur: %s)", 
                                self.config_entry.data[CONF_USERNAME])

        def on_disconnect(client, userdata, rc):
            """Callback lors de la déconnexion."""
            if rc != 0:
                _LOGGER.error("Déconnexion MQTT inattendue avec le code %s", rc)
            else:
                _LOGGER.info("Déconnexion MQTT normale")

        def on_message(client, userdata, msg):
            """Callback lors de la réception d'un message."""
            try:
                payload = msg.payload.decode()
                _LOGGER.debug("Message MQTT reçu sur %s: %s", msg.topic, payload)
                
                # Extraire l'equipId du topic
                parts = msg.topic.split('/')
                if len(parts) >= 2:
                    equip_id = parts[1]
                    if equip_id in self.data:
                        # Déterminer le type de données à partir du topic
                        data_type = parts[-1]  # Dernier segment du topic
                        if data_type in ["status", "power", "solar", "capacity", "output", "report"]:
                            self.data[equip_id][f"battery_{data_type}"] = payload
                            _LOGGER.debug("Données %s mises à jour pour la batterie %s", data_type, equip_id)
                            self.async_set_updated_data(self.data)
                
            except Exception as err:
                _LOGGER.error("Erreur lors du traitement du message MQTT: %s", err)

        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_disconnect = on_disconnect
        self.mqtt_client.on_message = on_message

        # Configuration de l'authentification MQTT
        try:
            _LOGGER.debug("Configuration de l'authentification MQTT")
            self.mqtt_client.username_pw_set(
                self.config_entry.data[CONF_USERNAME],
                self.config_entry.data[CONF_PASSWORD],
            )
            
            _LOGGER.info("Tentative de connexion à %s:%s avec l'utilisateur %s",
                       self.config_entry.data[CONF_HOST],
                       self.config_entry.data[CONF_PORT],
                       self.config_entry.data[CONF_USERNAME])
            
            self.mqtt_client.connect(
                self.config_entry.data[CONF_HOST],
                self.config_entry.data[CONF_PORT],
            )
            self.mqtt_client.loop_start()
            _LOGGER.info("Boucle MQTT démarrée")
        except Exception as err:
            self._connection_error = f"Erreur de connexion MQTT : {str(err)}"
            _LOGGER.error(self._connection_error)
            raise ConfigEntryAuthFailed(self._connection_error)

    async def async_shutdown(self):
        """Arrêter proprement le coordinateur."""
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

        if self.mqtt_client:
            _LOGGER.info("Arrêt du coordinateur Storcube")
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect() 