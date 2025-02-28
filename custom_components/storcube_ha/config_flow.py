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
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    CONF_APP_CODE,
    CONF_LOGIN_NAME,
    CONF_DEVICE_PASSWORD,
    DEFAULT_PORT,
)

_LOGGER = logging.getLogger(__name__)

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

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

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    # TODO: Validate the data can be used to set up a connection.
    return {"title": f"StorCube Battery Monitor ({data[CONF_HOST]})"}

class StorCubeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gérer le flux de configuration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Gérer le flux de configuration initié par l'utilisateur."""
        errors = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        ) 