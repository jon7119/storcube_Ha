"""Services pour l'intégration Storcube Battery Monitor."""
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

ATTR_POWER = "power"
ATTR_THRESHOLD = "threshold"
ATTR_EQUIP_ID = "equip_id"

SERVICE_SET_POWER = "set_power"
SERVICE_SET_THRESHOLD = "set_threshold"
SERVICE_GET_SCENE_INFO = "get_scene_info"
SERVICE_REFRESH_DATA = "refresh_data"

SET_POWER_SCHEMA = vol.Schema({
    vol.Required(ATTR_POWER): cv.positive_int,
})

SET_THRESHOLD_SCHEMA = vol.Schema({
    vol.Required(ATTR_THRESHOLD): vol.All(
        vol.Coerce(int),
        vol.Range(min=0, max=100)
    ),
})

GET_SCENE_INFO_SCHEMA = vol.Schema({
    vol.Optional(ATTR_EQUIP_ID): cv.string,
})

REFRESH_DATA_SCHEMA = vol.Schema({})

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
        
    async def handle_get_scene_info(call: ServiceCall) -> None:
        """Gérer le service get_scene_info."""
        equip_id = call.data.get(ATTR_EQUIP_ID)
        result = await coordinator.get_scene_user_list(equip_id)
        
        # Stocker le résultat dans les données du coordinateur pour qu'il soit accessible
        if result:
            coordinator.data["scene_info"] = result
            # Notifier Home Assistant que les données ont changé
            coordinator.async_set_updated_data(coordinator.data)
    
    async def handle_refresh_data(call: ServiceCall) -> None:
        """Gérer le service refresh_data."""
        await coordinator.async_refresh()

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
        SERVICE_GET_SCENE_INFO,
        handle_get_scene_info,
        schema=GET_SCENE_INFO_SCHEMA,
    )
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_DATA,
        handle_refresh_data,
        schema=REFRESH_DATA_SCHEMA,
    )

async def async_unload_services(hass: HomeAssistant) -> None:
    """Décharger les services de l'intégration."""
    hass.services.async_remove(DOMAIN, SERVICE_SET_POWER)
    hass.services.async_remove(DOMAIN, SERVICE_SET_THRESHOLD)
    hass.services.async_remove(DOMAIN, SERVICE_GET_SCENE_INFO)
    hass.services.async_remove(DOMAIN, SERVICE_REFRESH_DATA) 