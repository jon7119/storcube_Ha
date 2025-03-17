"""Config flow for Storcube Battery Monitor integration."""
from __future__ import annotations

import logging
import voluptuous as vol
import aiohttp
import async_timeout
import asyncio

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

class StorcubeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Storcube Battery Monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        
        if user_input is not None:
            try:
                # Validate the data can be used to set up the integration
                await self._test_credentials(user_input)

                # Create the config entry
                return self.async_create_entry(
                    title=f"Batterie Storcube {user_input[CONF_DEVICE_ID]}",
                    data=user_input,
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as e:
                _LOGGER.exception("Unexpected exception: %s", str(e))
                errors["base"] = "unknown"

        # Show the form to the user
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
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
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return StorcubeOptionsFlowHandler(config_entry)

    async def _test_credentials(self, data: dict) -> bool:
        """Test if we can authenticate with the host."""
        try:
            timeout = async_timeout.timeout(10)
            async with timeout:
                async with aiohttp.ClientSession() as session:
                    _LOGGER.debug("Testing connection to %s with device ID %s", TOKEN_URL, data[CONF_DEVICE_ID])
                    
                    auth_data = {
                        "appCode": data[CONF_APP_CODE],
                        "loginName": data[CONF_LOGIN_NAME],
                        "password": data[CONF_AUTH_PASSWORD],
                    }
                    _LOGGER.debug("Authentication data: %s", auth_data)
                    
                    async with session.post(TOKEN_URL, json=auth_data) as response:
                        _LOGGER.debug("Response status: %s", response.status)
                        
                        if response.status != 200:
                            _LOGGER.error("Authentication failed with status %s", response.status)
                            raise InvalidAuth
                        
                        json_response = await response.json()
                        _LOGGER.debug("Response data: %s", json_response)
                        
                        if json_response.get("code") != 200:
                            error_msg = json_response.get("message", "Unknown error")
                            _LOGGER.error("API error: %s", error_msg)
                            raise CannotConnect
                        
                        return True

        except asyncio.TimeoutError:
            _LOGGER.error("Connection timeout")
            raise CannotConnect
        except aiohttp.ClientError as e:
            _LOGGER.error("Connection error: %s", str(e))
            raise CannotConnect
        except Exception as e:
            _LOGGER.error("Unexpected error: %s", str(e))
            raise

    async def async_step_reauth(self, entry_data):
        """Handle reauth flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Handle reauth confirmation."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({})
            )
        return await self.async_step_user()

class StorcubeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Storcube options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        errors = {}

        if user_input is not None:
            try:
                # Validate the new credentials
                await self._test_credentials(user_input)
                
                # Update the config entry
                return self.async_create_entry(title="", data=user_input)
            
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception as e:
                _LOGGER.exception("Unexpected exception: %s", str(e))
                errors["base"] = "unknown"

        # Préparer les valeurs par défaut à partir de la configuration existante
        current_config = self.config_entry.data
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=current_config.get(CONF_HOST)): str,
                    vol.Optional(CONF_PORT, default=current_config.get(CONF_PORT, DEFAULT_PORT)): int,
                    vol.Required(CONF_DEVICE_ID, default=current_config.get(CONF_DEVICE_ID)): str,
                    vol.Optional(CONF_APP_CODE, default=current_config.get(CONF_APP_CODE, DEFAULT_APP_CODE)): str,
                    vol.Required(CONF_LOGIN_NAME, default=current_config.get(CONF_LOGIN_NAME)): str,
                    vol.Required(CONF_AUTH_PASSWORD, default=current_config.get(CONF_AUTH_PASSWORD)): str,
                    vol.Required(CONF_USERNAME, default=current_config.get(CONF_USERNAME)): str,
                    vol.Required(CONF_PASSWORD, default=current_config.get(CONF_PASSWORD)): str,
                }
            ),
            errors=errors,
        )

    async def _test_credentials(self, data: dict) -> bool:
        """Test if we can authenticate with the host."""
        try:
            timeout = async_timeout.timeout(10)
            async with timeout:
                async with aiohttp.ClientSession() as session:
                    auth_data = {
                        "appCode": data[CONF_APP_CODE],
                        "loginName": data[CONF_LOGIN_NAME],
                        "password": data[CONF_AUTH_PASSWORD],
                    }
                    
                    async with session.post(TOKEN_URL, json=auth_data) as response:
                        if response.status != 200:
                            raise InvalidAuth
                        
                        json_response = await response.json()
                        if json_response.get("code") != 200:
                            raise CannotConnect
                        
                        return True

        except asyncio.TimeoutError:
            raise CannotConnect
        except aiohttp.ClientError:
            raise CannotConnect
        except Exception as e:
            raise

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth.""" 