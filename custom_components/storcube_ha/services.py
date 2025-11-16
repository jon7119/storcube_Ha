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
    DEVICE_CONTROL_URL,
    SCENE_EXECUTE_URL,
    FIRMWARE_UPGRADE_URL,
    TOKEN_URL,
    CONF_DEVICE_ID,
    CONF_APP_CODE,
    CONF_LOGIN_NAME,
    CONF_AUTH_PASSWORD,
)

ATTR_POWER = "power"
ATTR_THRESHOLD = "threshold"
ATTR_SCENE_ID = "scene_id"

SERVICE_SET_POWER = "set_power"
SERVICE_SET_THRESHOLD = "set_threshold"
SERVICE_START_CHARGE = "start_charge"
SERVICE_STOP_CHARGE = "stop_charge"
SERVICE_START_DISCHARGE = "start_discharge"
SERVICE_STOP_DISCHARGE = "stop_discharge"
SERVICE_ENABLE_SCENE = "enable_scene"
SERVICE_DISABLE_SCENE = "disable_scene"
SERVICE_FIRMWARE_UPGRADE = "firmware_upgrade"

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

    async def handle_start_charge(call: ServiceCall) -> None:
        """Gérer le service start_charge."""
        await _control_device(hass, coordinator, "start_charge", True)

    async def handle_stop_charge(call: ServiceCall) -> None:
        """Gérer le service stop_charge."""
        await _control_device(hass, coordinator, "stop_charge", False)

    async def handle_start_discharge(call: ServiceCall) -> None:
        """Gérer le service start_discharge."""
        await _control_device(hass, coordinator, "start_discharge", True)

    async def handle_stop_discharge(call: ServiceCall) -> None:
        """Gérer le service stop_discharge."""
        await _control_device(hass, coordinator, "stop_discharge", False)

    async def handle_enable_scene(call: ServiceCall) -> None:
        """Gérer le service enable_scene."""
        scene_id = call.data.get(ATTR_SCENE_ID, "default")
        await _execute_scene(hass, coordinator, scene_id, True)

    async def handle_disable_scene(call: ServiceCall) -> None:
        """Gérer le service disable_scene."""
        scene_id = call.data.get(ATTR_SCENE_ID, "default")
        await _execute_scene(hass, coordinator, scene_id, False)

    async def handle_firmware_upgrade(call: ServiceCall) -> None:
        """Gérer le service firmware_upgrade."""
        await _upgrade_firmware(hass, coordinator)

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_CHARGE,
        handle_start_charge,
        schema=vol.Schema({}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_CHARGE,
        handle_stop_charge,
        schema=vol.Schema({}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_DISCHARGE,
        handle_start_discharge,
        schema=vol.Schema({}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_DISCHARGE,
        handle_stop_discharge,
        schema=vol.Schema({}),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_ENABLE_SCENE,
        handle_enable_scene,
        schema=vol.Schema({
            vol.Optional(ATTR_SCENE_ID): cv.string,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DISABLE_SCENE,
        handle_disable_scene,
        schema=vol.Schema({
            vol.Optional(ATTR_SCENE_ID): cv.string,
        }),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_FIRMWARE_UPGRADE,
        handle_firmware_upgrade,
        schema=vol.Schema({}),
    )


async def _control_device(hass: HomeAssistant, coordinator, action: str, value: bool) -> None:
    """Contrôler l'appareil via l'API."""
    import aiohttp
    import logging
    
    _LOGGER = logging.getLogger(__name__)
    
    config_entry = coordinator.config_entry
    config = config_entry.data
    
    try:
        # Récupérer le token
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TOKEN_URL,
                json={
                    "appCode": config[CONF_APP_CODE],
                    "loginName": config[CONF_LOGIN_NAME],
                    "password": config[CONF_AUTH_PASSWORD]
                },
                headers={'Content-Type': 'application/json'}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('code') == 200:
                        token = data['data']['token']
                        
                        # Contrôler l'appareil
                        async with session.post(
                            DEVICE_CONTROL_URL,
                            json={
                                "device_id": config[CONF_DEVICE_ID],
                                "action": action,
                                "value": value
                            },
                            headers={
                                "Authorization": token,
                                "Content-Type": "application/json",
                                "appCode": config[CONF_APP_CODE]
                            }
                        ) as control_response:
                            if control_response.status == 200:
                                control_data = await control_response.json()
                                if control_data.get("code") == 200:
                                    _LOGGER.info(f"Action {action} réussie")
                                else:
                                    _LOGGER.error(f"Échec de l'action {action}: {control_data.get('message')}")
    except Exception as e:
        _LOGGER.error(f"Erreur lors du contrôle de l'appareil: {e}")


async def _execute_scene(hass: HomeAssistant, coordinator, scene_id: str, enable: bool) -> None:
    """Exécuter une scène via l'API."""
    import aiohttp
    import logging
    
    _LOGGER = logging.getLogger(__name__)
    
    config_entry = coordinator.config_entry
    config = config_entry.data
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TOKEN_URL,
                json={
                    "appCode": config[CONF_APP_CODE],
                    "loginName": config[CONF_LOGIN_NAME],
                    "password": config[CONF_AUTH_PASSWORD]
                },
                headers={'Content-Type': 'application/json'}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('code') == 200:
                        token = data['data']['token']
                        
                        async with session.post(
                            SCENE_EXECUTE_URL,
                            json={
                                "device_id": config[CONF_DEVICE_ID],
                                "scene_id": scene_id,
                                "enable": enable
                            },
                            headers={
                                "Authorization": token,
                                "Content-Type": "application/json",
                                "appCode": config[CONF_APP_CODE]
                            }
                        ) as scene_response:
                            if scene_response.status == 200:
                                scene_data = await scene_response.json()
                                if scene_data.get("code") == 200:
                                    _LOGGER.info(f"Scène {scene_id} {'activée' if enable else 'désactivée'}")
    except Exception as e:
        _LOGGER.error(f"Erreur lors de l'exécution de la scène: {e}")


async def _upgrade_firmware(hass: HomeAssistant, coordinator) -> None:
    """Mettre à jour le firmware via l'API."""
    import aiohttp
    import logging
    
    _LOGGER = logging.getLogger(__name__)
    
    config_entry = coordinator.config_entry
    config = config_entry.data
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                TOKEN_URL,
                json={
                    "appCode": config[CONF_APP_CODE],
                    "loginName": config[CONF_LOGIN_NAME],
                    "password": config[CONF_AUTH_PASSWORD]
                },
                headers={'Content-Type': 'application/json'}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('code') == 200:
                        token = data['data']['token']
                        
                        async with session.post(
                            FIRMWARE_UPGRADE_URL,
                            json={"device_id": config[CONF_DEVICE_ID]},
                            headers={
                                "Authorization": token,
                                "Content-Type": "application/json",
                                "appCode": config[CONF_APP_CODE]
                            }
                        ) as upgrade_response:
                            if upgrade_response.status == 200:
                                upgrade_data = await upgrade_response.json()
                                if upgrade_data.get("code") == 200:
                                    _LOGGER.info("Mise à jour du firmware démarrée")
                                else:
                                    _LOGGER.error(f"Échec de la mise à jour: {upgrade_data.get('message')}")
    except Exception as e:
        _LOGGER.error(f"Erreur lors de la mise à jour du firmware: {e}")

async def async_unload_services(hass: HomeAssistant) -> None:
    """Décharger les services de l'intégration."""
    hass.services.async_remove(DOMAIN, SERVICE_SET_POWER)
    hass.services.async_remove(DOMAIN, SERVICE_SET_THRESHOLD)
    hass.services.async_remove(DOMAIN, SERVICE_CHECK_FIRMWARE)
    hass.services.async_remove(DOMAIN, SERVICE_START_CHARGE)
    hass.services.async_remove(DOMAIN, SERVICE_STOP_CHARGE)
    hass.services.async_remove(DOMAIN, SERVICE_START_DISCHARGE)
    hass.services.async_remove(DOMAIN, SERVICE_STOP_DISCHARGE)
    hass.services.async_remove(DOMAIN, SERVICE_ENABLE_SCENE)
    hass.services.async_remove(DOMAIN, SERVICE_DISABLE_SCENE)
    hass.services.async_remove(DOMAIN, SERVICE_FIRMWARE_UPGRADE) 