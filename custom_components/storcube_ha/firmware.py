"""Gestion des mises à jour de firmware pour StorCube."""
from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from .const import DEFAULT_APP_CODE, FIRMWARE_URL

_LOGGER = logging.getLogger(__name__)

# Appelant fourni par le coordinateur :
# (method, url, *, params=None, json_body=None) -> dict | None
ApiCall = Callable[..., Awaitable[dict | None]]

UNKNOWN = "Inconnue"


class StorCubeFirmwareManager:
    """Interroge l'API StorCube au sujet du firmware.

    Le gestionnaire ne s'authentifie pas lui-même : il réutilise l'appelant
    du coordinateur, qui gère le token, son renouvellement et les timeouts.
    """

    def __init__(
        self,
        api_call: ApiCall,
        device_id: str,
        app_code: str = DEFAULT_APP_CODE,
    ) -> None:
        """Initialiser le gestionnaire."""
        self._api_call = api_call
        self.device_id = device_id
        self.app_code = app_code
        self._last_result: dict[str, Any] | None = None

    async def check_firmware_upgrade(self) -> dict[str, Any] | None:
        """Interroger l'API et retourner l'état du firmware.

        Retourne None si l'API répond une erreur ; les exceptions réseau
        remontent à l'appelant, qui décide de la suite.
        """
        payload = await self._api_call("GET", FIRMWARE_URL + self.device_id)

        if not payload or payload.get("code") != 200:
            _LOGGER.debug(
                "Réponse firmware inexploitable : %s", (payload or {}).get("message")
            )
            return None

        data = payload.get("data") or {}

        # Nommage de l'API conservé tel quel : "lastBigVersion" désigne la
        # version installée et "currentBigVersion" la version disponible.
        # Contre-intuitif, mais c'est ce que renvoie Baterway.
        current_version = data.get("lastBigVersion") or UNKNOWN
        latest_version = data.get("currentBigVersion") or current_version
        upgrade_available = bool(data.get("upgread", False))

        notes: list[str] = []
        if upgrade_available:
            for remark in data.get("remarkList") or []:
                content = remark.get("remark", "")
                if not content:
                    continue
                try:
                    parsed = json.loads(content)
                except (json.JSONDecodeError, TypeError):
                    notes.append(content)
                    continue
                if isinstance(parsed, dict):
                    notes.append(
                        parsed.get("fr")
                        or parsed.get("en")
                        or "Notes indisponibles en français"
                    )
                else:
                    notes.append(str(parsed))

        self._last_result = {
            "upgrade_available": upgrade_available,
            "current_version": current_version,
            "latest_version": latest_version,
            "firmware_notes": notes,
            "last_check": datetime.now().isoformat(),
        }
        return self._last_result

    async def get_firmware_info(self) -> dict[str, Any]:
        """Retourner le dernier état connu, sans refaire d'appel réseau."""
        if self._last_result is not None:
            return dict(self._last_result)
        return {
            "current_version": UNKNOWN,
            "latest_version": UNKNOWN,
            "upgrade_available": False,
            "firmware_notes": [],
            "last_check": "Jamais",
        }
