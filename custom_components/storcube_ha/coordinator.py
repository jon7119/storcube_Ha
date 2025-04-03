"""Coordinateur de données pour l'intégration Storcube Battery Monitor."""
import asyncio
import logging
from datetime import timedelta, datetime
import requests
import json
import websockets
import aiohttp

import paho.mqtt.client as mqtt
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
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
from homeassistant.helpers import storage

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
            update_interval=timedelta(seconds=10),  # Réduit à 10 secondes
        )
        self.config_entry = config_entry
        self._topics = {
            "status": MQTT_TOPIC_STATUS,
            "power": MQTT_TOPIC_POWER,
            "solar": MQTT_TOPIC_SOLAR,
        }
        self.data = {
            "websocket": {},
            "rest_api": {},
            "combined": {
                "battery_level": 0,
                "battery_power": 0,
                "solar_power": 0,
                "temperature": 0,
                "status": "unknown",
            },
            "last_ws_update": None,
            "last_rest_update": None,
            "connection_status": {
                "websocket": False,
                "rest_api": False,
                "mqtt": False,
            }
        }
        self.hass = hass
        self.mqtt_client = None
        self.ws = None
        self._connection_error = None
        self._auth_token = None
        self._ws_task = None
        self._known_devices = set()
        self._rest_update_task = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 5  # Délai initial de 5 secondes

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
            if equip_id not in self.data["rest_api"]:
                self.data["rest_api"][equip_id] = {}
            
            self.data["rest_api"][equip_id].update({
                "battery_status": "{}",
                "battery_power": "{}",
                "battery_solar": "{}",
                "battery_capacity": "{}",
                "battery_output": "{}",
                "battery_report": "{}",
            })
            
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

    async def get_auth_token(self):
        """Récupérer le token d'authentification."""
        # Utilisez le stockage sécurisé pour stocker le token
        storage_key = f"{DOMAIN}_auth_token"
        token = await storage.async_get(self.hass, storage_key)
        if token:
            return token

        # Si le token n'existe pas, effectuez l'authentification
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
                await storage.async_set(self.hass, storage_key, self._auth_token)
                return self._auth_token
            raise Exception(f"Erreur d'authentification: {data.get('message', 'Réponse inconnue')}")
        except requests.RequestException as e:
            _LOGGER.error("Erreur lors de la récupération du token: %s", e)
            return None

    def token_is_expired(self):
        """Vérifier si le token est expiré."""
        # Implémentez votre logique pour vérifier l'expiration
        return False  # Remplacez par votre logique

    async def set_power_value(self, new_power_value):
        """Modifier la puissance de sortie."""
        if not self._auth_token:
            self._auth_token = await self.get_auth_token()
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
            self._auth_token = await self.get_auth_token()
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

    async def get_scene_data(self):
        """Récupérer les données de scène depuis l'API REST."""
        if not self._auth_token:
            self._auth_token = await self.get_auth_token()
            if not self._auth_token:
                _LOGGER.error("Impossible d'obtenir le token pour l'API REST")
                return None

        headers = {
            "Authorization": self._auth_token,
            "Content-Type": "application/json",
            "appCode": self.config_entry.data[CONF_APP_CODE]
        }

        try:
            _LOGGER.debug("Tentative d'appel API REST: %s avec headers: %s", OUTPUT_URL, headers)
            async with self.hass.async_add_executor_job(requests.get, OUTPUT_URL, headers=headers) as response:
                _LOGGER.debug("Réponse API REST - Status: %s", response.status_code)
                _LOGGER.debug("Réponse API REST - Headers: %s", response.headers)
                _LOGGER.debug("Réponse API REST - Contenu brut: %s", response.text)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 200:
                        _LOGGER.info("Données API REST reçues avec succès")
                        _LOGGER.debug("Données API REST: %s", data.get("data"))
                        self.data["last_rest_update"] = datetime.now().isoformat()
                        self.data["data_source"] = "rest_api"
                        return data.get("data")
                    _LOGGER.error("Erreur API REST: %s", data.get('message', 'Réponse inconnue'))
                response.raise_for_status()
        except requests.RequestException as e:
            _LOGGER.error("Erreur lors de la récupération des données REST: %s", str(e))
        except Exception as e:
            _LOGGER.error("Erreur inattendue lors de l'appel REST: %s", str(e))
        return None

    async def async_setup(self):
        """Set up the coordinator."""
        try:
            # Démarrer la tâche de mise à jour REST périodique
            self._rest_update_task = asyncio.create_task(self._rest_update_loop())
            
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
            _LOGGER.error("Erreur lors de la configuration: %s", err)
            raise ConfigEntryNotReady from err

    async def _handle_connection_error(self, service_name, error):
        """Gérer les erreurs de connexion avec tentatives de reconnexion."""
        self._reconnect_attempts += 1
        self.data["connection_status"][service_name] = False
        
        if self._reconnect_attempts <= self._max_reconnect_attempts:
            delay = min(self._reconnect_delay * self._reconnect_attempts, 60)  # Max 60 secondes
            _LOGGER.warning(
                "Tentative de reconnexion %s/%s pour %s dans %s secondes. Erreur: %s",
                self._reconnect_attempts,
                self._max_reconnect_attempts,
                service_name,
                delay,
                str(error)
            )
            await asyncio.sleep(delay)
            if service_name == "websocket":
                await self._start_websocket()
            elif service_name == "rest_api":
                await self._rest_update_loop()
            elif service_name == "mqtt":
                await self.async_setup()
        else:
            _LOGGER.error(
                "Échec de reconnexion après %s tentatives pour %s. Erreur: %s",
                self._max_reconnect_attempts,
                service_name,
                str(error)
            )
            self._reconnect_attempts = 0  # Réinitialiser pour la prochaine série

    async def _rest_update_loop(self):
        """Boucle de mise à jour périodique pour l'API REST."""
        while True:
            try:
                scene_data = await self.get_scene_data()
                if scene_data:
                    self.data["connection_status"]["rest_api"] = True
                    self._reconnect_attempts = 0  # Réinitialiser si succès
                    
                    equip_id = scene_data.get("equipId")
                    if equip_id:
                        if equip_id not in self.data["rest_api"]:
                            self.data["rest_api"][equip_id] = {}
                        
                        self.data["rest_api"][equip_id].update({
                            "output_type": scene_data.get("outputType"),
                            "reserved": scene_data.get("reserved"),
                            "output_power": scene_data.get("outputPower"),
                            "work_status": scene_data.get("workStatus"),
                            "rg_online": scene_data.get("rgOnline"),
                            "equip_type": scene_data.get("equipType"),
                            "main_equip_online": scene_data.get("mainEquipOnline"),
                            "equip_model": scene_data.get("equipModelCode"),
                            "last_update": scene_data.get("createTime")
                        })
                        
                        self.data["last_rest_update"] = datetime.now().isoformat()
                        
                        await self._update_sensors(equip_id)
                        
                        _LOGGER.debug("Données REST mises à jour pour l'équipement %s", equip_id)
            except Exception as e:
                await self._handle_connection_error("rest_api", e)
            
            await asyncio.sleep(10)  # Mise à jour toutes les 10 secondes

    async def _update_sensors(self, equip_id):
        """Mettre à jour les capteurs avec les nouvelles données."""
        try:
            if DOMAIN in self.hass.data and self.config_entry.entry_id in self.hass.data[DOMAIN]:
                for sensor in self.hass.data[DOMAIN][self.config_entry.entry_id]["sensors"]:
                    await self.hass.async_add_executor_job(
                        sensor.handle_state_update,
                        {
                            "rest_data": self.data["rest_api"][equip_id],
                            "connection_status": self.data["connection_status"]
                        }
                    )
        except Exception as e:
            _LOGGER.error("Erreur lors de la mise à jour des capteurs: %s", str(e))

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

    async def _start_websocket(self):
        """Démarrer la connexion WebSocket avec gestion de reconnexion."""
        while True:
            try:
                if not self._auth_token:
                    self._auth_token = await self.get_auth_token()
                    if not self._auth_token:
                        raise Exception("Impossible d'obtenir le token d'authentification")

                uri = f"{WS_URI}?token={self._auth_token}"
                _LOGGER.debug("Tentative de connexion WebSocket à %s", uri)

                async with websockets.connect(uri) as websocket:
                    self.ws = websocket
                    self.data["connection_status"]["websocket"] = True
                    self._reconnect_attempts = 0  # Réinitialiser le compteur
                    _LOGGER.info("Connexion WebSocket établie")

                    while True:
                        try:
                            message = await websocket.recv()
                            await self._handle_ws_message(message)
                        except websockets.ConnectionClosed:
                            _LOGGER.warning("Connexion WebSocket fermée, tentative de reconnexion...")
                            break
                        except Exception as e:
                            _LOGGER.error("Erreur lors de la réception du message WebSocket: %s", str(e))
                            break

            except Exception as e:
                await self._handle_connection_error("websocket", e)
                if self._reconnect_attempts >= self._max_reconnect_attempts:
                    _LOGGER.error("Échec de la connexion WebSocket après %s tentatives", self._max_reconnect_attempts)
                    break
            
            await asyncio.sleep(5)  # Attendre avant de réessayer

    async def _handle_ws_message(self, message):
        """Gérer les messages WebSocket reçus."""
        try:
            data = json.loads(message)
            equip_id = data.get("equipId")
            
            if equip_id:
                if equip_id not in self.data["websocket"]:
                    self.data["websocket"][equip_id] = {}
                
                # Mettre à jour les données WebSocket
                self.data["websocket"][equip_id].update({
                    "battery_level": data.get("batteryLevel"),
                    "battery_power": data.get("batteryPower"),
                    "solar_power": data.get("solarPower"),
                    "temperature": data.get("temperature"),
                    "status": data.get("status"),
                    "last_update": datetime.now().isoformat()
                })
                
                # Mettre à jour les capteurs
                await self._update_sensors(equip_id)
                
                _LOGGER.debug("Données WebSocket mises à jour pour l'équipement %s", equip_id)
        except json.JSONDecodeError as e:
            _LOGGER.error("Erreur de décodage JSON du message WebSocket: %s", str(e))
        except Exception as e:
            _LOGGER.error("Erreur lors du traitement du message WebSocket: %s", str(e))

    async def async_start(self):
        """Démarrer toutes les connexions."""
        try:
            # Démarrer la connexion WebSocket
            self._ws_task = asyncio.create_task(self._start_websocket())
            
            # Démarrer la mise à jour REST
            self._rest_update_task = asyncio.create_task(self._rest_update_loop())
            
            # Configurer MQTT
            await self.async_setup()
            
            return True
        except Exception as e:
            _LOGGER.error("Erreur lors du démarrage des connexions: %s", str(e))
            return False

    async def async_shutdown(self):
        """Arrêter proprement le coordinateur."""
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass

        if self._rest_update_task:
            self._rest_update_task.cancel()
            try:
                await self._rest_update_task
            except asyncio.CancelledError:
                pass

        if self.mqtt_client:
            _LOGGER.info("Arrêt du coordinateur Storcube")
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect() 

async def websocket_to_mqtt(hass: HomeAssistant, config: ConfigType, config_entry: ConfigEntry) -> None:
    """Handle websocket connection and forward data to MQTT."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id].get("coordinator")
    if not coordinator:
        _LOGGER.error("Coordinateur non trouvé")
        return

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

            _LOGGER.debug("Tentative de connexion WebSocket - URL Token: %s", TOKEN_URL)
            _LOGGER.debug("Payload de connexion: %s", {k: '***' if k == 'password' else v for k, v in payload.items()})
            
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
                        _LOGGER.debug("Réponse token WebSocket brute: %s", response_text)
                        
                        token_data = json.loads(response_text)
                        if token_data.get("code") != 200:
                            _LOGGER.error("Échec de l'authentification WebSocket: %s", token_data.get("message", "Erreur inconnue"))
                            raise Exception("Échec de l'authentification WebSocket")
                        token = token_data["data"]["token"]
                        _LOGGER.info("Token WebSocket obtenu avec succès")

                        uri = f"{WS_URI}{token}"
                        _LOGGER.debug("URI WebSocket: %s", uri)

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
                            
                            request_data = {"reportEquip": [config[CONF_DEVICE_ID]]}
                            await websocket.send(json.dumps(request_data))
                            _LOGGER.debug("Requête WebSocket envoyée: %s", request_data)

                            last_heartbeat = datetime.now()
                            while True:
                                try:
                                    message = await asyncio.wait_for(websocket.recv(), timeout=30)
                                    last_heartbeat = datetime.now()
                                    _LOGGER.debug("Message WebSocket reçu - Timestamp: %s", last_heartbeat.isoformat())
                                    _LOGGER.debug("Message WebSocket brut: %s", message)

                                    if message.strip():
                                        try:
                                            json_data = json.loads(message)
                                            
                                            if json_data == "SUCCESS":
                                                _LOGGER.debug("Message de confirmation WebSocket 'SUCCESS' reçu")
                                                continue
                                                
                                            if not json_data:
                                                _LOGGER.debug("Message WebSocket vide reçu")
                                                continue
                                            
                                            if isinstance(json_data, dict):
                                                _LOGGER.debug("Structure du message WebSocket: %s", list(json_data.keys()))
                                                
                                                equip_data = next(iter(json_data.values()), {})
                                                
                                                if equip_data and isinstance(equip_data, dict) and "list" in equip_data:
                                                    _LOGGER.info("Mise à jour WebSocket - Données: %s", equip_data)
                                                    
                                                    # Mettre à jour uniquement les données WebSocket
                                                    equip_id = equip_data.get("equipId")
                                                    if equip_id:
                                                        if equip_id not in coordinator.data["websocket"]:
                                                            coordinator.data["websocket"][equip_id] = {}
                                                        
                                                        coordinator.data["websocket"][equip_id].update(equip_data)
                                                        coordinator.data["last_ws_update"] = last_heartbeat.isoformat()
                                                        
                                                        # Mettre à jour les capteurs avec les nouvelles données WebSocket
                                                        for sensor in hass.data[DOMAIN][config_entry.entry_id]["sensors"]:
                                                            sensor.handle_state_update({"websocket_data": equip_data})
                                                else:
                                                    _LOGGER.warning("Message WebSocket sans données d'équipement valides")
                                            else:
                                                _LOGGER.warning("Message WebSocket format inattendu: %s", type(json_data))
                                        except json.JSONDecodeError as e:
                                            _LOGGER.warning("Impossible de décoder le message WebSocket JSON: %s", e)
                                            continue

                                except asyncio.TimeoutError:
                                    time_since_last = (datetime.now() - last_heartbeat).total_seconds()
                                    _LOGGER.debug("Timeout WebSocket après %d secondes, envoi heartbeat...", time_since_last)
                                    try:
                                        await websocket.send(json.dumps(request_data))
                                        _LOGGER.debug("Heartbeat WebSocket envoyé avec succès")
                                    except Exception as e:
                                        _LOGGER.warning("Échec de l'envoi du heartbeat WebSocket: %s", str(e))
                                        break
                                    continue

            except Exception as e:
                _LOGGER.error("Erreur WebSocket inattendue: %s", str(e))
                await asyncio.sleep(5)
                continue

        except Exception as e:
            _LOGGER.error("Erreur de connexion WebSocket: %s", str(e))
            await asyncio.sleep(5) 