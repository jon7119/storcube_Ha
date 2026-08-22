"""Services pour l'intégration Storcube Battery Monitor."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_DEVICE_ID,
    ATTR_FIRMWARE_CURRENT,
    ATTR_FIRMWARE_LATEST,
    ATTR_FIRMWARE_NOTES,
    ATTR_FIRMWARE_UPGRADE_AVAILABLE,
    ATTR_POWER,
    ATTR_THRESHOLD,
    DOMAIN,
    MAX_POWER,
    MAX_THRESHOLD,
    MIN_POWER,
    MIN_THRESHOLD,
    SERVICE_CHECK_FIRMWARE,
    SERVICE_SET_POWER,
    SERVICE_SET_THRESHOLD,
)

_LOGGER = logging.getLogger(__name__)

SET_POWER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_POWER): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_POWER, max=MAX_POWER)
        ),
        vol.Optional(ATTR_DEVICE_ID): cv.string,
    }
)

SET_THRESHOLD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_THRESHOLD): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_THRESHOLD, max=MAX_THRESHOLD)
        ),
        vol.Optional(ATTR_DEVICE_ID): cv.string,
    }
)

CHECK_FIRMWARE_SCHEMA = vol.Schema({vol.Optional(ATTR_DEVICE_ID): cv.string})


@callback
def _get_coordinator(hass: HomeAssistant, call: ServiceCall):
    """Retourner le coordinateur visé par l'appel de service.

    Sans device_id explicite, l'unique entrée configurée est utilisée. S'il y
    en a plusieurs, le device_id devient obligatoire : choisir arbitrairement
    piloterait la mauvaise batterie.
    """
    coordinators = hass.data.get(DOMAIN, {})
    if not coordinators:
        raise HomeAssistantError("Aucune entrée Storcube n'est configurée")

    device_id = call.data.get(ATTR_DEVICE_ID)
    if device_id:
        for coordinator in coordinators.values():
            if coordinator.config_entry.data.get("device_id") == device_id:
                return coordinator
        raise HomeAssistantError(
            f"Aucune entrée Storcube ne correspond au device_id {device_id}"
        )

    if len(coordinators) > 1:
        raise HomeAssistantError(
            "Plusieurs entrées Storcube sont configurées : précisez device_id"
        )

    return next(iter(coordinators.values()))


async def async_setup_services(hass: HomeAssistant) -> None:
    """Enregistrer les services de l'intégration."""
    if hass.services.has_service(DOMAIN, SERVICE_SET_POWER):
        return

    async def handle_set_power(call: ServiceCall) -> None:
        """Appliquer une consigne de puissance."""
        coordinator = _get_coordinator(hass, call)
        if not await coordinator.async_set_power_value(call.data[ATTR_POWER]):
            raise HomeAssistantError(
                f"La consigne de puissance {call.data[ATTR_POWER]} W a été refusée"
            )

    async def handle_set_threshold(call: ServiceCall) -> None:
        """Appliquer un seuil de décharge."""
        coordinator = _get_coordinator(hass, call)
        if not await coordinator.async_set_threshold_value(call.data[ATTR_THRESHOLD]):
            raise HomeAssistantError(
                f"Le seuil {call.data[ATTR_THRESHOLD]} %% a été refusé"
            )

    async def handle_check_firmware(call: ServiceCall) -> ServiceResponse:
        """Vérifier la disponibilité d'une mise à jour et retourner le résultat."""
        coordinator = _get_coordinator(hass, call)
        info = await coordinator.async_check_firmware_upgrade() or {}
        return {
            ATTR_FIRMWARE_CURRENT: info.get("current_version", "Inconnue"),
            ATTR_FIRMWARE_LATEST: info.get("latest_version", "Inconnue"),
            ATTR_FIRMWARE_UPGRADE_AVAILABLE: info.get("upgrade_available", False),
            ATTR_FIRMWARE_NOTES: info.get("firmware_notes", []),
        }

    hass.services.async_register(
        DOMAIN, SERVICE_SET_POWER, handle_set_power, schema=SET_POWER_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_THRESHOLD, handle_set_threshold, schema=SET_THRESHOLD_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CHECK_FIRMWARE,
        handle_check_firmware,
        schema=CHECK_FIRMWARE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Retirer les services de l'intégration."""
    for service in (SERVICE_SET_POWER, SERVICE_SET_THRESHOLD, SERVICE_CHECK_FIRMWARE):
        hass.services.async_remove(DOMAIN, service)
