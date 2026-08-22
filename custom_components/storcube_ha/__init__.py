"""The Storcube Battery Monitor Integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import StorCubeDataUpdateCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configurer Storcube Battery Monitor depuis une entrée de configuration."""
    coordinator = StorCubeDataUpdateCoordinator(hass, entry)

    try:
        await coordinator.async_setup()
    except ConfigEntryNotReady:
        raise
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Échec de configuration du coordinateur StorCube : {err}"
        ) from err

    # Premier rafraîchissement : peuple coordinator.data avant la création
    # des entités par les plateformes.
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_setup_services(hass)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Décharger une entrée de configuration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
    if coordinator:
        await coordinator.async_shutdown()

    # Les services sont globaux : ne les retirer qu'avec la dernière entrée.
    if not hass.data[DOMAIN]:
        await async_unload_services(hass)
        hass.data.pop(DOMAIN, None)

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recharger l'entrée de configuration."""
    await hass.config_entries.async_reload(entry.entry_id)
