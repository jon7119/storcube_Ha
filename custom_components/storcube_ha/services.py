"""Services pour l'intégration Storcube Battery Monitor."""
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_CHECK_FIRMWARE,
    ATTR_FIRMWARE_CURRENT,
    ATTR_FIRMWARE_LATEST,
    ATTR_FIRMWARE_UPGRADE_AVAILABLE,
    ATTR_FIRMWARE_NOTES,
)

ATTR_POWER = "power"
ATTR_THRESHOLD = "threshold"

SERVICE_SET_POWER = "set_power"
SERVICE_SET_THRESHOLD = "set_threshold"

SET_POWER_SCHEMA = vol.Schema({
    vol.Required(ATTR_POWER): cv.positive_int,
})

SET_THRESHOLD_SCHEMA = vol.Schema({
    vol.Required(ATTR_THRESHOLD): vol.All(
        vol.Coerce(int),
        vol.Range(min=0, max=100)
    ),
})

async def async_setup_services(hass: HomeAssistant) -> None:
    """Configurer les services pour l'intégration."""
    coordinator = None
    for entry_id, data in hass.data[DOMAIN].items():
        coordinator = data
        break

    if not coordinator:
        return

    async def handle_set_power(call: ServiceCall) -> None:
        """Gérer le service set_power."""
        power = call.data[ATTR_POWER]
        await coordinator.set_power_value(power)

    async def handle_set_threshold(call: ServiceCall) -> None:
        """Gérer le service set_threshold."""
        threshold = call.data[ATTR_THRESHOLD]
        await coordinator.set_threshold_value(threshold)

    async def handle_check_firmware(call: ServiceCall) -> None:
        """Gérer le service check_firmware."""
        firmware_info = await coordinator.check_firmware_upgrade()
        if firmware_info:
            # Retourner les informations dans les attributs du service
            call.data.update({
                ATTR_FIRMWARE_CURRENT: firmware_info.get("current_version", "Inconnue"),
                ATTR_FIRMWARE_LATEST: firmware_info.get("latest_version", "Inconnue"),
                ATTR_FIRMWARE_UPGRADE_AVAILABLE: firmware_info.get("upgrade_available", False),
                ATTR_FIRMWARE_NOTES: firmware_info.get("firmware_notes", [])
            })

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_POWER,
        handle_set_power,
        schema=SET_POWER_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_THRESHOLD,
        handle_set_threshold,
        schema=SET_THRESHOLD_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CHECK_FIRMWARE,
        handle_check_firmware,
        schema=vol.Schema({}),  # Pas de paramètres requis
    )

async def async_unload_services(hass: HomeAssistant) -> None:
    """Décharger les services de l'intégration."""
    hass.services.async_remove(DOMAIN, SERVICE_SET_POWER)
    hass.services.async_remove(DOMAIN, SERVICE_SET_THRESHOLD)
    hass.services.async_remove(DOMAIN, SERVICE_CHECK_FIRMWARE) 