"""Gestion des mises à jour de firmware pour StorCube."""
import logging
import json
import aiohttp
from typing import Dict, Optional, List
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import (
    FIRMWARE_URL,
    TOKEN_URL,
    DEFAULT_APP_CODE,
)

_LOGGER = logging.getLogger(__name__)

class StorCubeFirmwareManager:
    """Gestionnaire des mises à jour de firmware StorCube."""

    def __init__(self, hass: HomeAssistant, device_id: str, login_name: str, 
                 auth_password: str, app_code: str = DEFAULT_APP_CODE):
        """Initialiser le gestionnaire de firmware."""
        self.hass = hass
        self.device_id = device_id
        self.login_name = login_name
        self.auth_password = auth_password
        self.app_code = app_code
        self._auth_token = None

    async def get_auth_token(self) -> Optional[str]:
        """Obtenir le token d'authentification."""
        credentials = {
            "appCode": self.app_code,
            "loginName": self.login_name,
            "password": self.auth_password
        }
        headers = {"Content-Type": "application/json"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(TOKEN_URL, json=credentials, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 200:
                            _LOGGER.debug("Authentification réussie pour la vérification firmware")
                            return data["data"]["token"]
                        else:
                            _LOGGER.error(f"Erreur d'authentification: {data.get('message', 'Réponse inconnue')}")
                            return None
                    else:
                        _LOGGER.error(f"Erreur HTTP lors de l'authentification: {response.status}")
                        return None
        except Exception as e:
            _LOGGER.error(f"Erreur lors de l'authentification: {e}")
            return None

    async def check_firmware_upgrade(self) -> Optional[Dict]:
        """Vérifier si une mise à jour de firmware est disponible."""
        token = await self.get_auth_token()
        if not token:
            raise HomeAssistantError("Impossible d'obtenir le token d'authentification")

        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
            "appCode": self.app_code,
            "accept-language": "fr-FR",
            "user-agent": "Mozilla/5.0 (Linux; Android 11; SM-A202F Build/RP1A.200720.012; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/136.0.7103.60 Mobile Safari/537.36 uni-app Html5Plus/1.0 (Immersed/24.0)"
        }

        try:
            # Construire l'URL avec le device_id
            firmware_url = FIRMWARE_URL + self.device_id
            async with aiohttp.ClientSession() as session:
                async with session.get(firmware_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 200:
                            firmware_data = data.get("data", {})
                            
                            latest_version = firmware_data.get("currentBigVersion", "")
                            current_version = firmware_data.get("lastBigVersion", "Inconnue")
                            upgrade_available = firmware_data.get("upgread", False)
                            
                            # Si currentBigVersion est vide, on utilise lastBigVersion comme version actuelle
                            if not latest_version:
                                latest_version = current_version
                            
                            remark_list = firmware_data.get("remarkList", [])
                            firmware_notes = []
                            
                            if upgrade_available and remark_list:
                                for remark in remark_list:
                                    remark_content = remark.get("remark", "")
                                    try:
                                        # Essayer de parser le JSON dans remark
                                        remark_json = json.loads(remark_content)
                                        french_notes = remark_json.get("fr", "Notes non disponibles en français")
                                        firmware_notes.append(french_notes)
                                    except json.JSONDecodeError:
                                        # Si ce n'est pas du JSON, afficher tel quel
                                        firmware_notes.append(remark_content)
                            
                            result = {
                                "upgrade_available": upgrade_available,
                                "current_version": current_version,
                                "latest_version": latest_version,
                                "firmware_notes": firmware_notes
                            }
                            
                            _LOGGER.info(f"Vérification firmware terminée: {result}")
                            return result
                        else:
                            _LOGGER.error(f"Erreur API firmware: {data.get('message', 'Réponse inconnue')}")
                            return None
                    else:
                        _LOGGER.error(f"Erreur HTTP lors de la vérification firmware: {response.status}")
                        return None
        except Exception as e:
            _LOGGER.error(f"Erreur lors de la vérification du firmware: {e}")
            raise HomeAssistantError(f"Erreur lors de la vérification du firmware: {e}")

    async def get_firmware_info(self) -> Dict:
        """Obtenir les informations de firmware actuelles."""
        try:
            firmware_data = await self.check_firmware_upgrade()
            if firmware_data:
                return {
                    "current_version": firmware_data.get("current_version", "Inconnue"),
                    "latest_version": firmware_data.get("latest_version", "Inconnue"),
                    "upgrade_available": firmware_data.get("upgrade_available", False),
                    "firmware_notes": firmware_data.get("firmware_notes", []),
                    "last_check": "now"
                }
            else:
                return {
                    "current_version": "Inconnue",
                    "latest_version": "Inconnue",
                    "upgrade_available": False,
                    "firmware_notes": [],
                    "last_check": "error"
                }
        except Exception as e:
            _LOGGER.error(f"Erreur lors de l'obtention des informations firmware: {e}")
            return {
                "current_version": "Inconnue",
                "latest_version": "Inconnue",
                "upgrade_available": False,
                "firmware_notes": [],
                "last_check": "error"
            } 