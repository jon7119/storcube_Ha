"""Config flow for Storcube Battery Monitor integration."""
from __future__ import annotations

import logging
from typing import Any
import voluptuous as vol
import aiohttp
import asyncio
import async_timeout

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

class CannotConnect(HomeAssistantError):
    """Erreur indiquant l'impossibilité de se connecter."""

class InvalidAuth(HomeAssistantError):
    """Erreur indiquant une authentification invalide."""

class StorcubeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Storcube Battery Monitor."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data_schema = vol.Schema(
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        _LOGGER.debug("Démarrage de async_step_user avec user_input: %s", user_input)

        if user_input is None:
            _LOGGER.debug("Pas d'entrée utilisateur, affichage du formulaire")
            return self.async_show_form(
                step_id="user",
                data_schema=self.data_schema,
            )

        try:
            _LOGGER.debug("Test des identifiants")
            await self._test_credentials(user_input)

            _LOGGER.debug("Configuration de l'ID unique")
            await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
            self._abort_if_unique_id_configured()

            _LOGGER.debug("Création de l'entrée de configuration")
            return self.async_create_entry(
                title=f"Batterie Storcube {user_input[CONF_DEVICE_ID]}",
                data=user_input,
            )

        except CannotConnect as ex:
            _LOGGER.error("Erreur de connexion: %s", str(ex))
            errors["base"] = "cannot_connect"
        except InvalidAuth as ex:
            _LOGGER.error("Erreur d'authentification: %s", str(ex))
            errors["base"] = "invalid_auth"
        except Exception as ex:
            _LOGGER.exception("Erreur inattendue lors de la configuration: %s", str(ex))
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=self.data_schema,
            errors=errors,
        )

    async def _test_credentials(self, data: dict) -> bool:
        """Test if we can authenticate with the host."""
        try:
            _LOGGER.debug("Tentative de connexion au broker MQTT: %s:%s", data[CONF_HOST], data[CONF_PORT])
            
            # Test de la connexion MQTT
            if not await self.hass.async_add_executor_job(self._test_mqtt_connection, data):
                raise CannotConnect("Échec de la connexion MQTT")

            _LOGGER.debug("Test de l'authentification Baterway")
            async with aiohttp.ClientSession() as session:
                async with async_timeout.timeout(10):
                    async with session.post(
                        TOKEN_URL,
                        json={
                            "appCode": data[CONF_APP_CODE],
                            "loginName": data[CONF_LOGIN_NAME],
                            "password": data[CONF_AUTH_PASSWORD],
                        },
                    ) as response:
                        if response.status != 200:
                            _LOGGER.error("Erreur HTTP: %s", response.status)
                            raise InvalidAuth("Erreur d'authentification Baterway")

                        json_response = await response.json()
                        if json_response.get("code") != 200:
                            _LOGGER.error("Erreur API: %s", json_response)
                            raise CannotConnect("Erreur de réponse API")

            return True

        except aiohttp.ClientError as ex:
            _LOGGER.error("Erreur client HTTP: %s", str(ex))
            raise CannotConnect from ex
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout de la connexion")
            raise CannotConnect("Timeout de la connexion")
        except Exception as ex:
            _LOGGER.exception("Erreur inattendue: %s", str(ex))
            raise InvalidAuth from ex

    def _test_mqtt_connection(self, data: dict) -> bool:
        """Test MQTT connection."""
        try:
            import paho.mqtt.client as mqtt
            client = mqtt.Client()
            client.username_pw_set(data[CONF_USERNAME], data[CONF_PASSWORD])
            client.connect(data[CONF_HOST], data[CONF_PORT], 5)
            client.disconnect()
            return True
        except Exception as ex:
            _LOGGER.error("Erreur de connexion MQTT: %s", str(ex))
            return False 