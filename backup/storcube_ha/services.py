"""Services pour l'intégration Storcube Battery Monitor."""
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

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

async def async_unload_services(hass: HomeAssistant) -> None:
    """Décharger les services de l'intégration."""
    hass.services.async_remove(DOMAIN, SERVICE_SET_POWER)
    hass.services.async_remove(DOMAIN, SERVICE_SET_THRESHOLD) 