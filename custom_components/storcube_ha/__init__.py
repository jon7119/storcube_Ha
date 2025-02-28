"""L'intégration Storcube Battery Monitor."""
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL,
)
from .coordinator import StorcubeDataUpdateCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)  # Activer le logging détaillé

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configurer l'intégration à partir d'une entrée de configuration."""
    _LOGGER.debug("Démarrage de l'initialisation de StorCube Battery Monitor")

    try:
        coordinator = StorcubeDataUpdateCoordinator(
            hass,
            config_entry=entry,
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )

        # Premier rafraîchissement des données
        _LOGGER.debug("Tentative de premier rafraîchissement des données")
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.debug("Premier rafraîchissement réussi")

        # Stocker le coordinateur
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = coordinator

        # Configuration des plateformes
        _LOGGER.debug("Configuration des plateformes: %s", PLATFORMS)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        
        # Configuration des services
        await async_setup_services(hass)

        _LOGGER.info("Intégration StorCube Battery Monitor configurée avec succès")
        return True

    except Exception as err:
        _LOGGER.error("Erreur lors de l'initialisation: %s", err)
        raise ConfigEntryNotReady from err

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Décharger une entrée de configuration."""
    _LOGGER.debug("Déchargement de l'intégration StorCube Battery Monitor")
    
    try:
        # Décharger les plateformes
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        
        if unload_ok:
            # Nettoyage
            coordinator = hass.data[DOMAIN][entry.entry_id]
            await coordinator.async_shutdown()
            hass.data[DOMAIN].pop(entry.entry_id)
            
            # Déchargement des services si c'est la dernière entrée
            if not hass.data[DOMAIN]:
                await async_unload_services(hass)
                hass.data.pop(DOMAIN)

            _LOGGER.info("Intégration déchargée avec succès")
        
        return unload_ok

    except Exception as err:
        _LOGGER.error("Erreur lors du déchargement: %s", err)
        return False 