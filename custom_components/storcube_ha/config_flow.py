"""Config flow pour l'intégration Storcube Battery Monitor."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    CONF_APP_CODE,
    CONF_LOGIN_NAME,
    CONF_DEVICE_PASSWORD,
    DEFAULT_PORT,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
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

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Storcube Battery Monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Vous pouvez ajouter ici une validation si nécessaire
                return self.async_create_entry(
                    title=f"StorCube Battery Monitor ({user_input[CONF_HOST]})",
                    data=user_input,
                )
            except Exception as error:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception: %s", error)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        ) 