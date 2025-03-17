"""The Storcube Battery Monitor Integration."""
from __future__ import annotations

import logging
import asyncio
import json
import aiohttp
import async_timeout
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    NAME,
    CONF_DEVICE_ID,
    CONF_APP_CODE,
    CONF_LOGIN_NAME,
    CONF_AUTH_PASSWORD,
    DEFAULT_PORT,
)
from .version import __version__

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Storcube Battery Monitor integration."""
    if DOMAIN not in config:
        return True

    # Créer la vue Lovelace après un délai pour s'assurer que le service est disponible
    async def create_lovelace_view():
        await asyncio.sleep(5)  # Attendre 5 secondes
        try:
            await hass.services.async_call(
                "lovelace",
                "save_config",
                {
                    "config": {
                        "views": [
                            {
                                "title": "Storcube",
                                "path": "storcube",
                                "type": "custom:grid-layout",
                                "layout": {
                                    "grid-template-columns": "repeat(2, 1fr)",
                                    "grid-gap": "16px",
                                    "padding": "16px"
                                },
                                "cards": [
                                    {
                                        "type": "custom:mini-graph-card",
                                        "title": "État de la Batterie",
                                        "entities": [
                                            "sensor.etat_batterie_storcube",
                                            "sensor.capacite_batterie_storcube"
                                        ],
                                        "hours_to_show": 24,
                                        "points_per_hour": 2,
                                        "show": {
                                            "legend": True,
                                            "labels": True
                                        }
                                    },
                                    {
                                        "type": "custom:mini-graph-card",
                                        "title": "Puissance",
                                        "entities": [
                                            "sensor.puissance_charge_storcube",
                                            "sensor.puissance_decharge_storcube"
                                        ],
                                        "hours_to_show": 24,
                                        "points_per_hour": 2,
                                        "show": {
                                            "legend": True,
                                            "labels": True
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                }
            )
            _LOGGER.info("Vue Lovelace créée avec succès")
        except Exception as e:
            _LOGGER.error("Erreur lors de la création de la vue Lovelace: %s", str(e))

    # Lancer la création de la vue Lovelace en arrière-plan
    hass.async_create_task(create_lovelace_view())

    # Configuration de l'intégration
    for entry in config[DOMAIN]:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=entry,
            )
        )

    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Storcube Battery Monitor from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN].get(entry.entry_id)
        if coordinator:
            await coordinator.async_unsubscribe_mqtt()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)

async def async_unsubscribe_mqtt(self):
    """Se désabonner des topics MQTT."""
    if self.mqtt_client:
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect() 