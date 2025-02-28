"""Config flow pour l'intégration Storcube Battery Monitor."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
)
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_APP_CODE,
    CONF_LOGIN_NAME,
    CONF_DEVICE_PASSWORD,
    DEFAULT_PORT,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_APP_CODE): str,
        vol.Required(CONF_LOGIN_NAME): str,
        vol.Required(CONF_DEVICE_PASSWORD): str,
    }
)

class StorCubeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gérer le flux de configuration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, any] | None = None
    ) -> FlowResult:
        """Gérer le flux de configuration initié par l'utilisateur."""
        errors = {}

        if user_input is not None:
            try:
                # Créer l'entrée de configuration
                return self.async_create_entry(
                    title=f"StorCube Battery Monitor ({user_input[CONF_HOST]})",
                    data=user_input,
                )

            except Exception as err:
                _LOGGER.error("Erreur lors de la configuration: %s", err)
                errors["base"] = "unknown"

        # Afficher le formulaire
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        ) 