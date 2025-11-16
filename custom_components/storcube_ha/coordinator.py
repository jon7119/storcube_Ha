"""Coordinateur de données pour l'intégration Storcube Battery Monitor."""
import asyncio
import logging
from datetime import timedelta, datetime
import requests
import json
import websockets
import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import storage

from .const import (
    DOMAIN,
    NAME,
    CONF_DEVICE_ID,
    CONF_APP_CODE,
    CONF_LOGIN_NAME,
    CONF_AUTH_PASSWORD,
    DEFAULT_APP_CODE,
    WS_URI,
    TOKEN_URL,
    FIRMWARE_URL,
    OUTPUT_URL,
    SET_POWER_URL,
    SET_THRESHOLD_URL,
    DEVICE_LIST_URL,
    DEVICE_INFO_URL,
    DEVICE_STATUS_URL,
)
from .firmware import StorCubeFirmwareManager
from .battery_manager import StorCubeBatteryManager

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)  # Activer le logging détaillé

# URLs de l'API
TOKEN_URL = "http://baterway.com/api/user/app/login"
FIRMWARE_URL = "http://baterway.com/api/equip/version/need/upgrade"
OUTPUT_URL = "http://baterway.com/api/scene/user/list/V2"
SET_POWER_URL = "http://baterway.com/api/slb/equip/set/power"
SET_THRESHOLD_URL = "http://baterway.com/api/scene/threshold/set"
WS_URI = "ws://baterway.com:9501/equip/info/"

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
        # Séparer clairement les données des différentes sources
        self.data = {
            "websocket": {},  # Données du WebSocket
            "rest_api": {},   # Données de l'API REST
            "combined": {},   # Données combinées (par equip_id)
            "firmware": {},   # Données firmware
            "last_ws_update": None,
            "last_rest_update": None,
        }
        self.hass = hass
        self.ws = None
        self._connection_error = None
        self._auth_token = None
        self._ws_task = None
        self._known_devices = set()
        self._rest_update_task = None  # Nouvelle tâche pour l'API REST
        
        # Initialiser le gestionnaire de firmware
        self.firmware_manager = StorCubeFirmwareManager(
            hass=hass,
            device_id=config_entry.data[CONF_DEVICE_ID],
            login_name=config_entry.data[CONF_LOGIN_NAME],
            auth_password=config_entry.data[CONF_AUTH_PASSWORD],
            app_code=config_entry.data.get(CONF_APP_CODE, DEFAULT_APP_CODE)
        )
        
        # Initialiser le gestionnaire de batteries (sera partagé avec sensor.py)
        self.battery_manager = StorCubeBatteryManager()
        self.global_sensors = []
        self.individual_sensors = {}
        self.async_add_entities = None
        
        _LOGGER.info(
            "Initialisation du coordinateur Storcube avec les paramètres: device_id=%s, login_name=%s",
            config_entry.data[CONF_DEVICE_ID],
            config_entry.data[CONF_LOGIN_NAME],
        )
        
        # S'assurer que la structure des données est correcte dès l'initialisation
        self._ensure_data_structure()

    def _ensure_data_structure(self):
        """S'assurer que la structure des données est correctement initialisée."""
        _LOGGER.debug("Vérification de la structure des données...")
        
        if not hasattr(self, 'data') or self.data is None:
            _LOGGER.warning("self.data est None, réinitialisation...")
            self.data = {}
        
        required_keys = ["websocket", "rest_api", "combined", "firmware"]
        for key in required_keys:
            if key not in self.data:
                _LOGGER.debug("Ajout de la clé manquante: %s", key)
                self.data[key] = {}
        
        # S'assurer que les timestamps existent
        if "last_ws_update" not in self.data:
            self.data["last_ws_update"] = None
        if "last_rest_update" not in self.data:
            self.data["last_rest_update"] = None
        
        _LOGGER.debug("Structure des données après vérification: %s", list(self.data.keys()))

    def _get_device_info(self, equip_id, battery_data):
        """Créer les informations de l'appareil pour une batterie."""
        # Déterminer le rôle de la batterie depuis le battery_manager
        role = ""
        if hasattr(self, 'battery_manager') and self.battery_manager:
            battery_info = self.battery_manager.get_battery_info(equip_id)
            if battery_info:
                role = " (Maître)" if battery_info.is_master else " (Esclave)"
        
        return {
            "identifiers": {(DOMAIN, equip_id)},
            "name": f"Batterie StorCube {equip_id}{role}",
            "manufacturer": "StorCube",
            "model": battery_data.get("equipType", "S1000"),
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

    async def get_auth_token(self):
        """Récupérer le token d'authentification."""
        # Utilisez le stockage sécurisé pour stocker le token
        store = storage.Store(self.hass, 1, f"{DOMAIN}_auth_token")
        try:
            token_data = await store.async_load()
            if token_data and "token" in token_data:
                return token_data["token"]
        except Exception:
            pass  # Token n'existe pas ou erreur de lecture

        # Si le token n'existe pas, effectuez l'authentification
        try:
            token_credentials = {
                "appCode": self.config_entry.data[CONF_APP_CODE],
                "loginName": self.config_entry.data[CONF_LOGIN_NAME],
                "password": self.config_entry.data[CONF_AUTH_PASSWORD]
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
                # Sauvegarder le token
                await store.async_save({"token": self._auth_token})
                return self._auth_token
            raise Exception(f"Erreur d'authentification: {data.get('message', 'Réponse inconnue')}")
        except Exception as e:
            _LOGGER.error("Erreur lors de la récupération du token: %s", str(e))
            raise ConfigEntryAuthFailed(f"Échec d'authentification: {str(e)}")

    def token_is_expired(self):
        """Vérifier si le token est expiré."""
        # Pour simplifier, on considère que le token n'expire jamais
        return False

    async def set_power_value(self, new_power_value):
        """Modifier la valeur de puissance via l'API."""
        try:
            # Récupérer le token d'authentification
            token = await self.get_auth_token()
            if not token:
                _LOGGER.error("Impossible de récupérer le token d'authentification")
                return False

            # Préparer les paramètres de la requête
            headers = {
                "Authorization": token,
                "Content-Type": "application/json",
                "appCode": self.config_entry.data[CONF_APP_CODE]
            }
            params = {
                "equipId": self.config_entry.data[CONF_DEVICE_ID],
                "power": new_power_value
            }

            # Appeler l'API
            response = requests.get(SET_POWER_URL, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 200:
                _LOGGER.info("Puissance mise à jour avec succès: %sW", new_power_value)
                return True
            else:
                _LOGGER.error("Échec de la mise à jour de la puissance: %s", data.get('message'))
                return False

        except Exception as e:
            _LOGGER.error("Erreur lors de la modification de la puissance: %s", str(e))
            return False

    async def set_threshold_value(self, new_threshold_value):
        """Modifier la valeur de seuil via l'API."""
        try:
            # Récupérer le token d'authentification
            token = await self.get_auth_token()
            if not token:
                _LOGGER.error("Impossible de récupérer le token d'authentification")
                return False

            # Préparer les paramètres de la requête
            headers = {
                "Authorization": token,
                "Content-Type": "application/json",
                "appCode": self.config_entry.data[CONF_APP_CODE]
            }
            params = {
                "equipId": self.config_entry.data[CONF_DEVICE_ID],
                "threshold": new_threshold_value
            }

            # Appeler l'API
            response = requests.get(SET_THRESHOLD_URL, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            if data.get("code") == 200:
                _LOGGER.info("Seuil mis à jour avec succès: %s%%", new_threshold_value)
                return True
            else:
                _LOGGER.error("Échec de la mise à jour du seuil: %s", data.get('message'))
                return False

        except Exception as e:
            _LOGGER.error("Erreur lors de la modification du seuil: %s", str(e))
            return False

    async def get_scene_data(self):
        """Récupérer les données de scène via l'API REST."""
        try:
            # Récupérer le token d'authentification
            token = await self.get_auth_token()
            if not token:
                _LOGGER.error("Impossible de récupérer le token d'authentification")
                return None

            # Préparer les paramètres de la requête
            headers = {
                "Authorization": token,
                "Content-Type": "application/json",
                "appCode": self.config_entry.data[CONF_APP_CODE]
            }

            # Construire l'URL avec le device_id
            output_url = OUTPUT_URL + self.config_entry.data[CONF_DEVICE_ID]

            # Appeler l'API de manière asynchrone
            async with aiohttp.ClientSession() as session:
                async with session.get(output_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get("code") == 200 and data.get("data"):
                            scene_list = data["data"]
                            if scene_list:
                                # Retourner le premier élément de la liste
                                return scene_list[0]
                        
                        _LOGGER.debug("Aucune donnée de scène trouvée")
                        return None
                    else:
                        _LOGGER.error(f"Erreur HTTP lors de la récupération des données de scène: {response.status}")
                        return None

        except Exception as e:
            _LOGGER.error("Erreur lors de la récupération des données de scène: %s", str(e))
            return None

    async def check_firmware_upgrade(self):
        """Vérifier les mises à jour de firmware."""
        try:
            firmware_info = await self.firmware_manager.check_firmware_upgrade()
            if firmware_info:
                # Mettre à jour les données avec les informations de firmware
                if "firmware" not in self.data:
                    self.data["firmware"] = {}
                
                self.data["firmware"].update({
                    "current_version": firmware_info.get("current_version", "Inconnue"),
                    "latest_version": firmware_info.get("latest_version", "Inconnue"),
                    "upgrade_available": firmware_info.get("upgrade_available", False),
                    "firmware_notes": firmware_info.get("firmware_notes", []),
                    "last_check": datetime.now().isoformat()
                })
                
                _LOGGER.info("Vérification firmware terminée: %s", firmware_info)
                return firmware_info
            else:
                _LOGGER.warning("Aucune information firmware disponible")
                return None
        except Exception as e:
            _LOGGER.error("Erreur lors de la vérification du firmware: %s", str(e))
            return None

    async def get_firmware_info(self):
        """Obtenir les informations de firmware actuelles."""
        try:
            return await self.firmware_manager.get_firmware_info()
        except Exception as e:
            _LOGGER.error("Erreur lors de l'obtention des informations firmware: %s", str(e))
            return None

    async def async_setup(self):
        """Set up the coordinator."""
        try:
            _LOGGER.info("Configuration du coordinateur StorCube...")
            
            # Vérification firmware initiale
            _LOGGER.info("Vérification firmware initiale...")
            firmware_result = await self.check_firmware_upgrade()
            if firmware_result:
                _LOGGER.info("Vérification firmware initiale réussie")
            else:
                _LOGGER.warning("Vérification firmware initiale échouée")
            
            # Démarrer la tâche de mise à jour REST périodique
            _LOGGER.info("Démarrage de la boucle de mise à jour REST...")
            self._rest_update_task = asyncio.create_task(self._rest_update_loop())
            _LOGGER.info("Boucle de mise à jour REST démarrée")
            
            _LOGGER.info("Configuration du coordinateur terminée")
            
            # Récupérer les infos détaillées du device principal au démarrage
            asyncio.create_task(self.get_device_info())
            
            return True
        except Exception as err:
            _LOGGER.error("Erreur lors de la configuration: %s", err)
            raise ConfigEntryNotReady from err

    async def discover_devices(self):
        """Découvre automatiquement toutes les batteries sur le réseau."""
        try:
            token = await self.get_auth_token()
            if not token:
                _LOGGER.warning("Impossible de récupérer le token pour la découverte")
                return []
            
            headers = {
                "Authorization": token,
                "Content-Type": "application/json",
                "appCode": self.config_entry.data[CONF_APP_CODE]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    DEVICE_LIST_URL,
                    headers=headers,
                    params={"device_id": self.config_entry.data[CONF_DEVICE_ID]}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 200:
                            devices = data.get("data", {}).get("devices", [])
                            if not devices and isinstance(data.get("data"), list):
                                devices = data.get("data", [])
                            
                            _LOGGER.info("Découverte de %d appareil(s) StorCube", len(devices))
                            
                            # Enregistrer les nouveaux appareils
                            for device in devices:
                                device_id = device.get("deviceid") or device.get("equipId") or device.get("device_id")
                                if device_id and device_id not in self._known_devices:
                                    self._register_device(device_id, device)
                                    _LOGGER.info("Nouvelle batterie découverte: %s", device_id)
                            
                            return devices
                        else:
                            _LOGGER.warning("Erreur lors de la découverte: %s", data.get("message"))
                    else:
                        _LOGGER.warning("Erreur HTTP lors de la découverte: %d", response.status)
        except Exception as e:
            _LOGGER.error("Erreur lors de la découverte automatique: %s", str(e))
        
        return []

    async def get_device_info(self, device_id: str = None):
        """Récupère les informations détaillées d'un appareil via /api/device/info."""
        try:
            if not device_id:
                device_id = self.config_entry.data[CONF_DEVICE_ID]
            
            token = await self.get_auth_token()
            if not token:
                return None
            
            headers = {
                "Authorization": token,
                "Content-Type": "application/json",
                "appCode": self.config_entry.data[CONF_APP_CODE]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    DEVICE_INFO_URL,
                    json={"device_id": device_id},
                    headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 200:
                            device_info = data.get("data", {})
                            
                            # Stocker les données dans rest_api
                            if device_id not in self.data["rest_api"]:
                                self.data["rest_api"][device_id] = {}
                            
                            self.data["rest_api"][device_id].update(device_info)
                            
                            # Mettre à jour les capteurs
                            if self.config_entry.entry_id in self.hass.data[DOMAIN]:
                                coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
                                if hasattr(coordinator, 'global_sensors'):
                                    for sensor in coordinator.global_sensors:
                                        if hasattr(sensor, 'handle_state_update'):
                                            sensor.handle_state_update({"device_info": device_info})
                            
                            return device_info
        except Exception as e:
            _LOGGER.error("Erreur lors de la récupération des infos appareil: %s", str(e))
        
        return None

    async def _rest_update_loop(self):
        """Boucle de mise à jour périodique pour l'API REST."""
        firmware_check_counter = 0  # Compteur pour les vérifications firmware
        discovery_counter = 0  # Compteur pour la découverte automatique
        _LOGGER.info("Démarrage de la boucle de mise à jour REST")
        
        while True:
            try:
                _LOGGER.debug("Cycle de mise à jour REST (compteur firmware: %d/20)", firmware_check_counter)
                
                # Découverte automatique toutes les 5 minutes (10 cycles)
                discovery_counter += 1
                if discovery_counter >= 10:
                    _LOGGER.info("Découverte automatique des batteries...")
                    discovered_devices = await self.discover_devices()
                    if discovered_devices:
                        # Récupérer les infos détaillées pour chaque nouveau device
                        for device in discovered_devices:
                            device_id = device.get("deviceid") or device.get("equipId") or device.get("device_id")
                            if device_id:
                                await self.get_device_info(device_id)
                    discovery_counter = 0
                
                scene_data = await self.get_scene_data()
                if scene_data:
                    equip_id = scene_data.get("equipId")
                    if equip_id:
                        # Mettre à jour uniquement les données REST
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
                        
                        # Mettre à jour les capteurs avec les nouvelles données REST
                        if self.config_entry.entry_id in self.hass.data[DOMAIN]:
                            sensors = self.hass.data[DOMAIN][self.config_entry.entry_id].get("sensors", [])
                            for sensor in sensors:
                                await self.hass.async_add_executor_job(
                                    sensor.handle_state_update,
                                    {"rest_data": self.data["rest_api"][equip_id]}
                                )
                        
                        _LOGGER.info("Données REST mises à jour pour l'équipement %s", equip_id)
                else:
                    _LOGGER.debug("Aucune donnée de scène récupérée")
                
                # Vérification firmware toutes les 10 minutes (20 cycles de 30 secondes)
                firmware_check_counter += 1
                _LOGGER.debug("Compteur firmware: %d/20", firmware_check_counter)
                
                if firmware_check_counter >= 20:
                    _LOGGER.info("Vérification automatique du firmware...")
                    firmware_info = await self.check_firmware_upgrade()
                    if firmware_info:
                        # Mettre à jour les capteurs avec les données firmware
                        if self.config_entry.entry_id in self.hass.data[DOMAIN]:
                            sensors = self.hass.data[DOMAIN][self.config_entry.entry_id].get("sensors", [])
                            for sensor in sensors:
                                if hasattr(sensor, 'handle_state_update'):
                                    await self.hass.async_add_executor_job(
                                        sensor.handle_state_update,
                                        {"firmware": self.data["firmware"]}
                                    )
                        _LOGGER.info("Données firmware mises à jour")
                    else:
                        _LOGGER.warning("Échec de la vérification firmware automatique")
                    firmware_check_counter = 0  # Réinitialiser le compteur
                    
            except Exception as e:
                _LOGGER.error("Erreur dans la boucle de mise à jour REST: %s", str(e))
            
            _LOGGER.debug("Attente de 30 secondes avant le prochain cycle...")
            await asyncio.sleep(30)  # Attendre 30 secondes avant la prochaine mise à jour

    async def _async_update_data(self):
        """Mettre à jour les données combinées."""
        try:
            # S'assurer que la structure des données est initialisée
            self._ensure_data_structure()
            
            # Vérifier que les données sont correctement initialisées
            if not hasattr(self, 'data') or self.data is None:
                _LOGGER.error("self.data est None ou non défini")
                self.data = {}
                self._ensure_data_structure()
            
            if "combined" not in self.data:
                _LOGGER.error("Clé 'combined' manquante dans self.data: %s", list(self.data.keys()) if self.data else "None")
                self._ensure_data_structure()
            
            _LOGGER.debug("Structure des données avant mise à jour: %s", list(self.data.keys()))
            
            # Combiner les données des deux sources
            for equip_id in self._known_devices:
                if equip_id not in self.data["combined"]:
                    self.data["combined"][equip_id] = {}
                
                # Copier les données WebSocket
                if equip_id in self.data["websocket"]:
                    self.data["combined"][equip_id].update(self.data["websocket"][equip_id])
                
                # Copier les données REST sans écraser les données WebSocket existantes
                if equip_id in self.data["rest_api"]:
                    rest_data = self.data["rest_api"][equip_id]
                    for key, value in rest_data.items():
                        if key not in self.data["combined"][equip_id]:
                            self.data["combined"][equip_id][key] = value

            _LOGGER.debug("Mise à jour des données combinées terminée")
            return self.data["combined"]

        except Exception as e:
            _LOGGER.error("Erreur lors de la mise à jour des données combinées: %s", e)
            _LOGGER.error("État de self.data: %s", self.data if hasattr(self, 'data') else "Non défini")
            raise UpdateFailed(f"Erreur de mise à jour: {str(e)}")

    async def _websocket_listener(self):
        """Écouter les données WebSocket."""
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
                                    
                                    # Mettre à jour les données dans le coordinateur
                                    self.data["websocket"][equip_id] = battery
                                    
                                    _LOGGER.debug("Données reçues pour la batterie %s", equip_id)
                                
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

    async def async_shutdown(self):
        """Arrêter le coordinateur proprement."""
        _LOGGER.info("Arrêt du coordinateur Storcube")
        
        # Arrêter la tâche de mise à jour REST
        if self._rest_update_task and not self._rest_update_task.done():
            self._rest_update_task.cancel()
            try:
                await self._rest_update_task
            except asyncio.CancelledError:
                pass
        
        # Arrêter la tâche WebSocket
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        
        _LOGGER.info("Coordinateur Storcube arrêté")
