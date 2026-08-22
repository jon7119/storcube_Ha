"""Coordinateur de données pour l'intégration Storcube Battery Monitor."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta

import aiohttp
import websockets

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_APP_CODE,
    CONF_AUTH_PASSWORD,
    CONF_DEVICE_ID,
    CONF_LOGIN_NAME,
    DEFAULT_APP_CODE,
    DOMAIN,
    FIRMWARE_URL,
    MAX_POWER,
    MIN_POWER,
    OUTPUT_URL,
    QUERY_THRESHOLD_URL,
    SET_POWER_URL,
    SET_THRESHOLD_URL,
    TOKEN_URL,
    TOPIC_BATTERY_CAPACITY,
    TOPIC_BATTERY_POWER,
    TOPIC_BATTERY_REPORT,
    TOPIC_BATTERY_SOLAR,
    TOPIC_BATTERY_STATUS,
    TOPIC_FIRMWARE,
    TOPIC_OUTPUT,
    TOPIC_OUTPUT_POWER,
    TOPIC_THRESHOLD,
    WS_URI,
)
from .firmware import StorCubeFirmwareManager

_LOGGER = logging.getLogger(__name__)

# Intervalle nominal de la boucle REST, et bornes du backoff en cas d'échec.
REST_INTERVAL = 30
REST_BACKOFF_MAX = 600
# Une vérification firmware tous les N cycles REST réussis (20 x 30 s = 10 min).
FIRMWARE_EVERY = 20
# Durée de validité supposée du token (l'API ne renvoie pas d'expiration).
TOKEN_TTL = timedelta(hours=12)
# Délai de reconnexion du WebSocket.
WS_RETRY_MIN = 5
WS_RETRY_MAX = 300
# Sans trame reçue pendant ce délai, on relance l'abonnement.
WS_HEARTBEAT = 30
# Au-delà, les données temps réel sont considérées comme périmées.
WS_FRESH_MAX = 180

STORAGE_VERSION = 1


class StorCubeDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinateur : agrège les données WebSocket et REST des batteries StorCube."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialiser le coordinateur."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            # Pas de polling : les rafraîchissements sont poussés par la boucle
            # REST et par le listener WebSocket via async_request_refresh().
            update_interval=None,
        )
        # self.config_entry est désormais posé par DataUpdateCoordinator.

        # État brut, séparé de self.data qui appartient au DataUpdateCoordinator.
        # Ne JAMAIS écrire dans self.data : la classe parente l'écrase à chaque
        # refresh avec la valeur retournée par _async_update_data().
        self._raw: dict[str, dict] = {
            "websocket": {},
            "rest_api": {},
            "firmware": {},
        }
        self._last_ws_update: str | None = None
        self._last_rest_update: str | None = None

        self._session = async_get_clientsession(hass)
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_token")

        self._auth_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._token_lock = asyncio.Lock()

        self._known_devices: set[str] = set()
        # L'API accepte le seuil sous plusieurs noms de champ selon les
        # firmwares ; on retient celui qui a fonctionné.
        self._threshold_field: str | None = None
        self._mqtt_available = False

        self._ws_task: asyncio.Task | None = None
        self._rest_task: asyncio.Task | None = None

        # Le gestionnaire de firmware réutilise l'appelant authentifié du
        # coordinateur plutôt que de refaire son propre login.
        self.firmware_manager = StorCubeFirmwareManager(
            api_call=self._async_api_call,
            device_id=config_entry.data[CONF_DEVICE_ID],
            app_code=config_entry.data.get(CONF_APP_CODE, DEFAULT_APP_CODE),
        )

        _LOGGER.debug(
            "Coordinateur StorCube initialisé (device_id=%s, login=%s)",
            config_entry.data[CONF_DEVICE_ID],
            config_entry.data[CONF_LOGIN_NAME],
        )

    # ------------------------------------------------------------------
    # Propriétés exposées aux entités
    # ------------------------------------------------------------------

    @property
    def master_equip_id(self) -> str:
        """Identifiant de la batterie maître, celle que pilote l'API."""
        return str(self.config_entry.data[CONF_DEVICE_ID])

    @property
    def firmware(self) -> dict:
        """Retourner les informations firmware courantes."""
        return self._raw["firmware"]

    @property
    def last_rest_update(self) -> str | None:
        """Horodatage ISO de la dernière mise à jour REST réussie."""
        return self._last_rest_update

    @property
    def last_ws_update(self) -> str | None:
        """Horodatage ISO de la dernière mise à jour WebSocket réussie."""
        return self._last_ws_update

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    async def async_setup(self) -> bool:
        """Démarrer les boucles WebSocket et REST, s'abonner au MQTT."""
        _LOGGER.debug("Configuration du coordinateur StorCube")

        # L'authentification doit réussir pour que quoi que ce soit fonctionne :
        # on la fait ici pour remonter une erreur propre au setup de l'entrée.
        try:
            await self._async_get_token()
        except ConfigEntryAuthFailed:
            raise
        except Exception as err:
            raise ConfigEntryNotReady(
                f"Impossible de joindre l'API StorCube : {err}"
            ) from err

        # Le broker MQTT de Home Assistant est optionnel : sans lui, on se
        # contente de ne pas republier les données.
        self._mqtt_available = await self._async_check_mqtt()

        # Vérification firmware initiale, non bloquante pour le setup.
        try:
            await self.async_check_firmware_upgrade()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Vérification firmware initiale échouée : %s", err)

        self._ws_task = self.config_entry.async_create_background_task(
            self.hass, self._websocket_loop(), name=f"{DOMAIN}_websocket"
        )
        self._rest_task = self.config_entry.async_create_background_task(
            self.hass, self._rest_loop(), name=f"{DOMAIN}_rest"
        )

        _LOGGER.debug("Coordinateur StorCube configuré")
        return True

    async def async_shutdown(self) -> None:
        """Arrêter proprement le coordinateur."""
        _LOGGER.debug("Arrêt du coordinateur StorCube")

        for task in (self._ws_task, self._rest_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._ws_task = None
        self._rest_task = None

        await super().async_shutdown()

    # ------------------------------------------------------------------
    # Agrégation des données
    # ------------------------------------------------------------------

    def _ws_is_fresh(self) -> bool:
        """Indiquer si le WebSocket a livré des données récemment."""
        if not self._last_ws_update:
            return False
        try:
            age = datetime.now() - datetime.fromisoformat(self._last_ws_update)
        except (TypeError, ValueError):
            return False
        return age.total_seconds() < WS_FRESH_MAX

    async def _async_update_data(self) -> dict[str, dict]:
        """Combiner les données REST et WebSocket, par equip_id.

        Le WebSocket est prioritaire (données plus fraîches) ; le REST comble
        les champs absents.
        """
        try:
            firmware_version = self._raw["firmware"].get("current_version")
            fresh = self._ws_is_fresh()
            combined: dict[str, dict] = {}
            for equip_id in self._known_devices:
                merged = dict(self._raw["rest_api"].get(equip_id, {}))
                merged.update(self._raw["websocket"].get(equip_id, {}))
                # La version installée n'est remontée que par l'API firmware,
                # jamais dans les trames WebSocket.
                if firmware_version and firmware_version != "Inconnue":
                    merged.setdefault("firmware_version", firmware_version)
                # Fraîcheur des données temps réel, faute de champ fgOnline
                # exploitable dans les trames.
                merged["ws_fresh"] = fresh and equip_id in self._raw["websocket"]
                combined[equip_id] = merged
            return combined
        except Exception as err:  # noqa: BLE001
            raise UpdateFailed(f"Erreur d'agrégation des données : {err}") from err

    # ------------------------------------------------------------------
    # Authentification
    # ------------------------------------------------------------------

    async def _async_get_token(self, force_refresh: bool = False) -> str:
        """Retourner un token valide, en le renouvelant si nécessaire."""
        async with self._token_lock:
            if not force_refresh and self._auth_token and not self._token_expired():
                return self._auth_token

            if not force_refresh and self._auth_token is None:
                # Tentative de restauration depuis le stockage persistant.
                stored = await self._store.async_load()
                if stored and stored.get("token"):
                    expires_raw = stored.get("expires_at")
                    try:
                        expires = (
                            datetime.fromisoformat(expires_raw) if expires_raw else None
                        )
                    except ValueError:
                        expires = None
                    if expires and expires > datetime.now():
                        self._auth_token = stored["token"]
                        self._token_expires_at = expires
                        return self._auth_token

            credentials = {
                "appCode": self.config_entry.data.get(CONF_APP_CODE, DEFAULT_APP_CODE),
                "loginName": self.config_entry.data[CONF_LOGIN_NAME],
                "password": self.config_entry.data[CONF_AUTH_PASSWORD],
            }
            headers = {"Content-Type": "application/json"}

            try:
                async with self._session.post(
                    TOKEN_URL,
                    json=credentials,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    resp.raise_for_status()
                    payload = await resp.json(content_type=None)
            except aiohttp.ClientError as err:
                raise ConfigEntryNotReady(
                    f"API StorCube injoignable : {err}"
                ) from err

            if payload.get("code") != 200:
                raise ConfigEntryAuthFailed(
                    f"Échec d'authentification : {payload.get('message', 'réponse inconnue')}"
                )

            token = (payload.get("data") or {}).get("token")
            if not token:
                raise ConfigEntryAuthFailed("Token absent de la réponse de l'API")

            self._auth_token = token
            self._token_expires_at = datetime.now() + TOKEN_TTL
            await self._store.async_save(
                {
                    "token": token,
                    "expires_at": self._token_expires_at.isoformat(),
                }
            )
            _LOGGER.debug("Token StorCube renouvelé")
            return token

    def _token_expired(self) -> bool:
        """Indiquer si le token courant est arrivé à expiration."""
        if self._token_expires_at is None:
            return True
        return datetime.now() >= self._token_expires_at

    async def _async_headers(self) -> dict[str, str]:
        """Construire les en-têtes authentifiés pour l'API REST."""
        token = await self._async_get_token()
        return {
            "Authorization": token,
            "Content-Type": "application/json",
            "appCode": self.config_entry.data.get(CONF_APP_CODE, DEFAULT_APP_CODE),
        }

    # ------------------------------------------------------------------
    # Appels API REST
    # ------------------------------------------------------------------

    async def _async_api_call(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        retry: bool = True,
    ) -> dict | None:
        """Appeler l'API en réinjectant un token frais sur un 401/403."""
        headers = await self._async_headers()
        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                if resp.status in (401, 403) and retry:
                    _LOGGER.debug("Token rejeté (%s), renouvellement", resp.status)
                    await self._async_get_token(force_refresh=True)
                    return await self._async_api_call(
                        method, url, params=params, json_body=json_body, retry=False
                    )
                resp.raise_for_status()
                return await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            _LOGGER.debug("Erreur API %s %s : %s", method, url, err)
            raise

    async def async_get_scene_data(self) -> dict | None:
        """Récupérer les données de scène (état de sortie) via l'API REST."""
        url = OUTPUT_URL + self.config_entry.data[CONF_DEVICE_ID]
        payload = await self._async_api_call("GET", url)
        if not payload or payload.get("code") != 200:
            return None
        scene_list = payload.get("data") or []
        return scene_list[0] if scene_list else None

    async def async_set_power_value(self, new_power_value) -> bool:
        """Modifier la consigne de puissance de sortie."""
        try:
            value = int(new_power_value)
        except (TypeError, ValueError):
            _LOGGER.error("Consigne de puissance invalide : %r", new_power_value)
            return False

        if not MIN_POWER <= value <= MAX_POWER:
            _LOGGER.error(
                "Consigne de puissance hors bornes (%s-%s W) : %s",
                MIN_POWER,
                MAX_POWER,
                value,
            )
            return False

        try:
            payload = await self._async_api_call(
                "GET",
                SET_POWER_URL,
                params={
                    "equipId": self.config_entry.data[CONF_DEVICE_ID],
                    "power": value,
                },
            )
        except aiohttp.ClientError as err:
            _LOGGER.error("Erreur lors de la modification de la puissance : %s", err)
            return False

        if payload and payload.get("code") == 200:
            _LOGGER.debug("Puissance mise à jour : %s W", value)
            await self.async_request_refresh()
            return True

        _LOGGER.error(
            "Échec de la mise à jour de la puissance : %s",
            (payload or {}).get("message"),
        )
        return False

    async def async_set_threshold_value(self, new_threshold_value) -> bool:
        """Modifier le seuil de décharge.

        L'API n'est pas documentée et accepte le seuil sous des noms de champ
        différents selon les firmwares. On essaie les variantes connues une
        seule fois, puis on réutilise celle qui a fonctionné.
        """
        try:
            value = int(new_threshold_value)
        except (TypeError, ValueError):
            _LOGGER.error("Seuil invalide : %r", new_threshold_value)
            return False

        if not 0 <= value <= 100:
            _LOGGER.error("Seuil hors bornes (0-100 %%) : %s", value)
            return False

        equip_id = self.config_entry.data[CONF_DEVICE_ID]
        fields = (
            [self._threshold_field]
            if self._threshold_field
            else ["reserved", "threshold", "data"]
        )

        for field in fields:
            body = {field: str(value), "equipId": equip_id}
            try:
                payload = await self._async_api_call(
                    "POST", SET_THRESHOLD_URL, json_body=body
                )
            except aiohttp.ClientError as err:
                _LOGGER.error("Erreur lors de la modification du seuil : %s", err)
                return False

            if payload and payload.get("code") == 200:
                if self._threshold_field != field:
                    _LOGGER.info("Champ de seuil retenu pour l'API : %s", field)
                self._threshold_field = field
                await self.async_request_refresh()
                return True

            _LOGGER.debug(
                "Champ de seuil %s refusé : %s", field, (payload or {}).get("message")
            )

        # La variante mémorisée a cessé de fonctionner : on repartira d'une
        # découverte complète au prochain appel.
        self._threshold_field = None
        _LOGGER.error("Aucune variante de champ acceptée pour le seuil")
        return False

    async def async_get_threshold(self) -> int | None:
        """Lire le seuil de décharge courant."""
        try:
            payload = await self._async_api_call(
                "GET",
                QUERY_THRESHOLD_URL,
                params={"equipId": self.config_entry.data[CONF_DEVICE_ID]},
            )
        except aiohttp.ClientError as err:
            _LOGGER.debug("Lecture du seuil impossible : %s", err)
            return None

        if not payload:
            return None
        try:
            return int(payload["data"])
        except (KeyError, TypeError, ValueError):
            _LOGGER.debug("Réponse de seuil inattendue : %s", payload)
            return None

    # Alias rétrocompatibles avec l'ancienne API du coordinateur.
    set_power_value = async_set_power_value
    set_threshold_value = async_set_threshold_value
    get_scene_data = async_get_scene_data

    # ------------------------------------------------------------------
    # Firmware
    # ------------------------------------------------------------------

    async def async_check_firmware_upgrade(self) -> dict | None:
        """Vérifier la disponibilité d'une mise à jour de firmware."""
        firmware_info = await self.firmware_manager.check_firmware_upgrade()
        if not firmware_info:
            _LOGGER.debug("Aucune information firmware disponible")
            return None

        self._raw["firmware"] = {
            "current_version": firmware_info.get("current_version", "Inconnue"),
            "latest_version": firmware_info.get("latest_version", "Inconnue"),
            "upgrade_available": firmware_info.get("upgrade_available", False),
            "firmware_notes": firmware_info.get("firmware_notes", []),
            "last_check": datetime.now().isoformat(),
        }
        return firmware_info

    async def async_get_firmware_info(self) -> dict:
        """Retourner le dernier état firmware connu, sans appel réseau."""
        return await self.firmware_manager.get_firmware_info()

    check_firmware_upgrade = async_check_firmware_upgrade
    get_firmware_info = async_get_firmware_info

    # ------------------------------------------------------------------
    # Boucle REST
    # ------------------------------------------------------------------

    @property
    def _rest_interval(self) -> int:
        """Intervalle de la boucle REST, réglable dans les options."""
        try:
            return int(self.config_entry.options.get("rest_interval", REST_INTERVAL))
        except (TypeError, ValueError):
            return REST_INTERVAL

    async def _rest_loop(self) -> None:
        """Interroger périodiquement l'API REST, avec backoff exponentiel."""
        firmware_counter = 0
        delay = self._rest_interval
        failures = 0

        while True:
            try:
                scene_data = await self.async_get_scene_data()
            except asyncio.CancelledError:
                raise
            except ConfigEntryAuthFailed as err:
                # Identifiants devenus invalides en cours d'exécution : on
                # déclenche le flux de ré-authentification de HA et on arrête
                # la boucle. Le rechargement de l'entrée relancera tout.
                _LOGGER.warning("Ré-authentification StorCube requise : %s", err)
                self.config_entry.async_start_reauth(self.hass)
                return
            except Exception as err:  # noqa: BLE001
                failures += 1
                delay = min(self._rest_interval * (2**failures), REST_BACKOFF_MAX)
                # Seul le premier échec d'une série est journalisé en warning :
                # évite de saturer les logs pendant une panne prolongée.
                if failures == 1:
                    _LOGGER.warning(
                        "Boucle REST en échec (%s), nouvelle tentative dans %s s",
                        err,
                        delay,
                    )
                else:
                    _LOGGER.debug(
                        "Boucle REST toujours en échec (%s tentatives) : %s",
                        failures,
                        err,
                    )
                await asyncio.sleep(delay)
                continue

            if failures:
                _LOGGER.info("Boucle REST rétablie après %s tentatives", failures)
            failures = 0
            delay = self._rest_interval

            try:
                if scene_data:
                    equip_id = scene_data.get("equipId")
                    if equip_id:
                        self._known_devices.add(equip_id)
                        self._raw["rest_api"].setdefault(equip_id, {}).update(
                            {
                                "output_type": scene_data.get("outputType"),
                                "reserved": scene_data.get("reserved"),
                                "output_power": scene_data.get("outputPower"),
                                "work_status": scene_data.get("workStatus"),
                                "rg_online": scene_data.get("rgOnline"),
                                "equip_type": scene_data.get("equipType"),
                                "main_equip_online": scene_data.get("mainEquipOnline"),
                                "equip_model": scene_data.get("equipModelCode"),
                                "last_update": scene_data.get("createTime"),
                            }
                        )
                        self._last_rest_update = datetime.now().isoformat()
                        # Le coordinateur se charge de propager aux entités.
                        await self.async_request_refresh()
                else:
                    _LOGGER.debug("Aucune donnée de scène récupérée")

                firmware_counter += 1
                if firmware_counter >= FIRMWARE_EVERY:
                    firmware_counter = 0
                    try:
                        if await self.async_check_firmware_upgrade():
                            await self.async_request_refresh()
                    except Exception as err:  # noqa: BLE001
                        _LOGGER.debug("Vérification firmware échouée : %s", err)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                _LOGGER.exception("Erreur de traitement des données REST : %s", err)

            await asyncio.sleep(delay)

    # ------------------------------------------------------------------
    # Boucle WebSocket
    # ------------------------------------------------------------------

    async def _websocket_loop(self) -> None:
        """Maintenir la connexion WebSocket et traiter les trames reçues."""
        retry = WS_RETRY_MIN
        equip_id = self.config_entry.data[CONF_DEVICE_ID]
        subscribe = json.dumps({"reportEquip": [equip_id]})

        while True:
            try:
                token = await self._async_get_token()
                # Le serveur attend le token dans le chemin de l'URL, pas
                # seulement dans les en-têtes.
                uri = f"{WS_URI}{token}"
                headers = {
                    "Authorization": token,
                    "Content-Type": "application/json",
                    "accept-language": "fr-FR",
                }

                # websockets >= 14 utilise additional_headers ; les versions
                # antérieures attendent extra_headers.
                try:
                    connection = websockets.connect(
                        uri,
                        additional_headers=headers,
                        ping_interval=15,
                        ping_timeout=5,
                    )
                except TypeError:
                    connection = websockets.connect(
                        uri,
                        extra_headers=headers,
                        ping_interval=15,
                        ping_timeout=5,
                    )

                async with connection as websocket:
                    _LOGGER.debug("WebSocket StorCube connecté")
                    retry = WS_RETRY_MIN

                    # Sans cette trame d'abonnement, le serveur accepte la
                    # connexion mais n'envoie jamais de données.
                    await websocket.send(subscribe)
                    _LOGGER.debug("Abonnement WebSocket envoyé : %s", subscribe)

                    while True:
                        try:
                            message = await asyncio.wait_for(
                                websocket.recv(), timeout=WS_HEARTBEAT
                            )
                        except TimeoutError:
                            # Silence prolongé : on relance l'abonnement pour
                            # vérifier que la session est toujours vivante.
                            _LOGGER.debug("Silence WebSocket, relance de l'abonnement")
                            await websocket.send(subscribe)
                            continue

                        try:
                            await self._async_handle_ws_message(message)
                        except asyncio.CancelledError:
                            raise
                        except Exception as err:  # noqa: BLE001
                            _LOGGER.debug("Trame WebSocket ignorée : %s", err)

            except asyncio.CancelledError:
                raise
            except ConfigEntryAuthFailed as err:
                _LOGGER.warning("Ré-authentification StorCube requise : %s", err)
                self.config_entry.async_start_reauth(self.hass)
                return
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug(
                    "WebSocket interrompu (%s), reconnexion dans %s s", err, retry
                )

            await asyncio.sleep(retry)
            retry = min(retry * 2, WS_RETRY_MAX)

    @staticmethod
    def _extract_batteries(payload) -> list[dict]:
        """Extraire les dictionnaires de batterie d'une trame WebSocket.

        L'API mélange plusieurs formes selon les trames :
          {"<equipId>": {"totalPv1power": .., "list": [{..}]}}
          {"list": [{..}]}
          {"code": 200, "data": [{..}]}
        Les totaux portés par le conteneur sont fusionnés dans chaque
        batterie afin que les capteurs les trouvent au même niveau.
        """
        batteries: list[dict] = []

        def collect(node, fallback_id=None):
            if isinstance(node, list):
                for item in node:
                    collect(item, fallback_id)
                return
            if not isinstance(node, dict):
                return

            inner = node.get("list")
            if isinstance(inner, list):
                # Les totaux (totalPv1power, totalInvPower, ...) portent sur
                # l'ensemble du stack. Ne les attacher qu'à la batterie
                # maître : recopiés sur les esclaves, ils feraient compter
                # la production plusieurs fois.
                totals = {
                    key: value
                    for key, value in node.items()
                    if key != "list" and not isinstance(value, (dict, list))
                }
                items = [item for item in inner if isinstance(item, dict)]
                solo = len(items) == 1
                for item in items:
                    equip_id = item.get("equipId") or fallback_id
                    is_master = solo or (
                        fallback_id is not None and str(equip_id) == str(fallback_id)
                    )
                    merged = {**totals, **item} if is_master else dict(item)
                    if equip_id:
                        merged.setdefault("equipId", equip_id)
                        batteries.append(merged)
                return

            if node.get("equipId") or fallback_id:
                entry = dict(node)
                if fallback_id:
                    entry.setdefault("equipId", fallback_id)
                if entry.get("equipId"):
                    batteries.append(entry)

        if not isinstance(payload, dict):
            return batteries

        if isinstance(payload.get("list"), list):
            collect(payload)
        elif payload.get("code") == 200 and isinstance(payload.get("data"), list):
            collect(payload["data"])
        else:
            for key, value in payload.items():
                if isinstance(value, (dict, list)):
                    # La clé est généralement l'equipId lui-même.
                    collect(value, key if str(key).isdigit() else None)

        return batteries

    async def _async_handle_ws_message(self, message) -> None:
        """Traiter une trame WebSocket et mettre à jour l'état brut."""
        data = json.loads(message)

        # Le serveur émet des accusés de réception textuels.
        if not data or not isinstance(data, dict):
            _LOGGER.debug("Trame WebSocket non exploitable : %r", data)
            return

        batteries = self._extract_batteries(data)
        if not batteries:
            _LOGGER.debug("Trame WebSocket sans batterie : clés=%s", list(data.keys()))
            return

        updated = False
        for battery in batteries:
            equip_id = str(battery.get("equipId"))
            if not equip_id:
                continue

            self._async_register_device(equip_id, battery)

            values = {
                "status": battery.get("fgOnline", 0),
                "power": battery.get("invPower", battery.get("power", 0)),
                "solar": battery.get("pv1power", battery.get("solarPower", 0)),
                "capacity": battery.get("soc", 0),
            }

            self._raw["websocket"][equip_id] = {
                "battery_status": values["status"],
                "battery_power": values["power"],
                "battery_solar": values["solar"],
                "battery_capacity": values["capacity"],
                # Trame brute complète : c'est elle que lisent les capteurs.
                "battery_output": battery,
                "battery_report": {"list": [battery]},
            }
            updated = True

            await self._async_publish(equip_id, values, battery)

        if updated:
            self._last_ws_update = datetime.now().isoformat()
            await self.async_request_refresh()

    # ------------------------------------------------------------------
    # MQTT (broker de Home Assistant)
    # ------------------------------------------------------------------

    async def _async_check_mqtt(self) -> bool:
        """Vérifier que l'intégration MQTT de Home Assistant est disponible."""
        try:
            await mqtt.async_wait_for_mqtt_client(self.hass)
        except Exception as err:  # noqa: BLE001
            _LOGGER.info(
                "MQTT indisponible, republication désactivée (%s)", err
            )
            return False
        return True

    @staticmethod
    def _topics_for(equip_id: str) -> dict[str, str]:
        """Construire les topics MQTT d'une batterie."""
        return {
            "status": TOPIC_BATTERY_STATUS.format(device_id=equip_id),
            "power": TOPIC_BATTERY_POWER.format(device_id=equip_id),
            "solar": TOPIC_BATTERY_SOLAR.format(device_id=equip_id),
            "capacity": TOPIC_BATTERY_CAPACITY.format(device_id=equip_id),
            "report": TOPIC_BATTERY_REPORT.format(device_id=equip_id),
            "output": TOPIC_OUTPUT.format(device_id=equip_id),
            "output_power": TOPIC_OUTPUT_POWER.format(device_id=equip_id),
            "threshold": TOPIC_THRESHOLD.format(device_id=equip_id),
            "firmware": TOPIC_FIRMWARE.format(device_id=equip_id),
        }

    async def _async_publish(
        self, equip_id: str, values: dict, battery: dict
    ) -> None:
        """Republier les données de la batterie sur le broker de HA."""
        if not self._mqtt_available:
            return

        topics = self._topics_for(equip_id)
        payloads = {
            topics["status"]: {"value": values["status"]},
            topics["power"]: {"value": values["power"]},
            topics["solar"]: {"value": values["solar"]},
            topics["capacity"]: {"value": values["capacity"]},
            topics["output"]: battery,
            topics["report"]: {"list": [battery]},
        }
        for topic, payload in payloads.items():
            try:
                await mqtt.async_publish(self.hass, topic, json.dumps(payload))
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Publication MQTT échouée sur %s : %s", topic, err)
                self._mqtt_available = False
                return

    # ------------------------------------------------------------------
    # Registre d'appareils
    # ------------------------------------------------------------------

    def _async_register_device(self, equip_id: str, battery: dict) -> None:
        """Enregistrer une nouvelle batterie dans le registre d'appareils."""
        if equip_id in self._known_devices:
            return

        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, equip_id)},
            name=f"Batterie StorCube {equip_id}",
            manufacturer="StorCube",
            model=battery.get("equipType", "Inconnu"),
            sw_version=battery.get("version"),
        )

        self._raw["rest_api"].setdefault(equip_id, {})
        self._known_devices.add(equip_id)
        _LOGGER.info("Nouvelle batterie StorCube détectée : %s", equip_id)
