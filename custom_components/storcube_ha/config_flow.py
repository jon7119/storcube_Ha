"""Config flow pour l'intégration Storcube Battery Monitor."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_APP_CODE,
    CONF_AUTH_PASSWORD,
    CONF_DEVICE_ID,
    CONF_LOGIN_NAME,
    DEFAULT_APP_CODE,
    DOMAIN,
    TOKEN_URL,
)

_LOGGER = logging.getLogger(__name__)

PASSWORD_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD)
)


def _schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """Construire le formulaire, éventuellement pré-rempli."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_DEVICE_ID, default=defaults.get(CONF_DEVICE_ID, vol.UNDEFINED)
            ): str,
            vol.Required(
                CONF_LOGIN_NAME, default=defaults.get(CONF_LOGIN_NAME, vol.UNDEFINED)
            ): str,
            vol.Required(CONF_AUTH_PASSWORD): PASSWORD_SELECTOR,
            vol.Optional(
                CONF_APP_CODE, default=defaults.get(CONF_APP_CODE, DEFAULT_APP_CODE)
            ): str,
        }
    )


async def _async_validate(hass, data: Mapping[str, Any]) -> None:
    """Vérifier que les identifiants permettent d'obtenir un token."""
    session = async_get_clientsession(hass)
    credentials = {
        "appCode": data.get(CONF_APP_CODE, DEFAULT_APP_CODE),
        "loginName": data[CONF_LOGIN_NAME],
        "password": data[CONF_AUTH_PASSWORD],
    }

    try:
        async with asyncio.timeout(15):
            async with session.post(
                TOKEN_URL,
                json=credentials,
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.status in (401, 403):
                    raise InvalidAuth
                if response.status >= 400:
                    _LOGGER.debug("Réponse HTTP %s de l'API", response.status)
                    raise CannotConnect
                payload = await response.json(content_type=None)
    except TimeoutError as err:
        raise CannotConnect from err
    except aiohttp.ClientError as err:
        _LOGGER.debug("Erreur de connexion à l'API : %s", err)
        raise CannotConnect from err

    # L'API répond en HTTP 200 même sur des identifiants invalides : c'est le
    # champ "code" qui fait foi.
    if payload.get("code") != 200:
        _LOGGER.debug("L'API a refusé les identifiants : %s", payload.get("message"))
        raise InvalidAuth

    if not (payload.get("data") or {}).get("token"):
        raise CannotConnect


class StorcubeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Gérer la configuration de Storcube Battery Monitor."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Première étape : saisie des identifiants."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Une batterie ne doit être configurée qu'une fois : sans cela,
            # chaque ajout crée un coordinateur et un WebSocket de plus.
            await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
            self._abort_if_unique_id_configured()

            try:
                await _async_validate(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Erreur inattendue lors de la validation")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Batterie Storcube {user_input[CONF_DEVICE_ID]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input), errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Démarrer la réauthentification d'une entrée existante."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Mettre à jour les identifiants de l'entrée existante.

        Il ne faut surtout pas créer une nouvelle entrée ici : cela
        dupliquerait le coordinateur et ses connexions.
        """
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            new_data = {**entry.data, **user_input}
            try:
                await _async_validate(self.hass, new_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Erreur inattendue lors de la réauthentification")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(entry, data=new_data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LOGIN_NAME, default=entry.data.get(CONF_LOGIN_NAME)
                    ): str,
                    vol.Required(CONF_AUTH_PASSWORD): PASSWORD_SELECTOR,
                }
            ),
            errors=errors,
            description_placeholders={"device_id": entry.data.get(CONF_DEVICE_ID, "")},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Permettre de corriger la configuration sans supprimer l'entrée."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_DEVICE_ID])
            self._abort_if_unique_id_mismatch(reason="wrong_device")

            try:
                await _async_validate(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Erreur inattendue lors de la reconfiguration")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(entry, data=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(user_input or entry.data),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Retourner le gestionnaire d'options."""
        return StorcubeOptionsFlowHandler()


class StorcubeOptionsFlowHandler(OptionsFlow):
    """Options de l'intégration.

    Les identifiants ne se modifient pas ici : ils vivent dans `data`, pas
    dans `options`. Utiliser « Reconfigurer » sur l'entrée.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Afficher et enregistrer les options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "rest_interval",
                        default=self.config_entry.options.get("rest_interval", 30),
                    ): vol.All(vol.Coerce(int), vol.Range(min=15, max=600)),
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """L'API est injoignable."""


class InvalidAuth(HomeAssistantError):
    """Les identifiants sont refusés."""
