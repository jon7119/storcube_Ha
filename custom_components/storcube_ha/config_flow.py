"""Config flow for Storcube Battery Monitor integration."""
from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol
import aiohttp

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
    NAME,
    CONF_DEVICE_ID,
    CONF_APP_CODE,
    CONF_LOGIN_NAME,
    CONF_AUTH_PASSWORD,
    DEFAULT_PORT,
    DEFAULT_APP_CODE,
    TOKEN_URL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Optional(CONF_APP_CODE, default=DEFAULT_APP_CODE): str,
        vol.Required(CONF_LOGIN_NAME): str,
        vol.Required(CONF_AUTH_PASSWORD): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

class StorcubeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Storcube Battery Monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._test_credentials(user_input)

                # Vérifier si l'appareil est déjà configuré
                await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Batterie Storcube {user_input[CONF_DEVICE_ID]}",
                    data=user_input,
                )

            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as ex:
                _LOGGER.exception("Erreur inattendue: %s", str(ex))
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def _test_credentials(self, data: dict) -> bool:
        """Test if we can authenticate with the host."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TOKEN_URL,
                    json={
                        "appCode": data[CONF_APP_CODE],
                        "loginName": data[CONF_LOGIN_NAME],
                        "password": data[CONF_AUTH_PASSWORD],
                    },
                    timeout=10,
                ) as response:
                    if response.status != 200:
                        raise InvalidAuth

                    json_response = await response.json()
                    if json_response.get("code") != 200:
                        raise CannotConnect

                    return True

        except aiohttp.ClientError as ex:
            _LOGGER.error("Erreur de connexion: %s", str(ex))
            raise CannotConnect from ex
        except Exception as ex:
            _LOGGER.error("Erreur inattendue lors du test des identifiants: %s", str(ex))
            raise InvalidAuth from ex

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth.""" 