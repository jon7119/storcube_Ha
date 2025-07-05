"""Number platform for Storcube Battery Monitor."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    DOMAIN,
    NAME,
    SET_POWER_URL,
    TOKEN_URL,
    CONF_APP_CODE,
    CONF_LOGIN_NAME,
    CONF_AUTH_PASSWORD,
)


_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Storcube number platform."""
    # Récupérer les données de configuration
    config = config_entry.data
    device_id = config.get(CONF_DEVICE_ID)
    app_code = config.get(CONF_APP_CODE, "Storcube")
    login_name = config.get(CONF_LOGIN_NAME)
    auth_password = config.get(CONF_AUTH_PASSWORD)

    if not device_id:
        _LOGGER.error("Device ID manquant dans la configuration")
        return

    # Créer l'entité de contrôle de puissance
    entities = [
        StorcubePowerNumber(
            config,
            device_id,
            app_code,
            login_name,
            auth_password,
        )
    ]

    async_add_entities(entities)


class StorcubePowerNumber(NumberEntity):
    """Représente le contrôle de puissance de sortie StorCube."""

    def __init__(
        self,
        config: ConfigType,
        device_id: str,
        app_code: str,
        login_name: str,
        auth_password: str,
    ) -> None:
        """Initialize the Storcube Power Number."""
        self._config = config
        self._device_id = device_id
        self._app_code = app_code
        self._login_name = login_name
        self._auth_password = auth_password
        self._attr_name = f"Puissance de Sortie StorCube"
        self._attr_unique_id = f"{device_id}_output_power"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 800.0
        self._attr_native_step = 1.0
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_value = 100.0  # Valeur par défaut

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True  # Toujours disponible pour le contrôle

    @property
    def should_poll(self) -> bool:
        """No need to poll."""
        return False

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Pas besoin de listener car c'est un contrôle, pas un capteur

    async def async_will_remove_from_hass(self) -> None:
        """When entity will be removed from hass."""
        await super().async_will_remove_from_hass()
        # Pas de nettoyage nécessaire

    async def async_set_native_value(self, value: float) -> None:
        """Set the power value."""
        try:
            # Récupérer le token d'authentification
            token = await self._get_auth_token()
            if not token:
                _LOGGER.error("Impossible de récupérer le token d'authentification")
                return

            # Appeler l'API pour modifier la puissance
            success = await self._set_power_value(token, int(value))
            if success:
                self._attr_native_value = value
                self.async_write_ha_state()
                _LOGGER.info(f"Puissance mise à jour avec succès: {value}W")
            else:
                _LOGGER.error(f"Échec de la mise à jour de la puissance: {value}W")

        except Exception as e:
            _LOGGER.error(f"Erreur lors de la modification de la puissance: {e}")

    async def _get_auth_token(self) -> str | None:
        """Récupérer le token d'authentification."""
        import aiohttp

        token_credentials = {
            "appCode": self._app_code,
            "loginName": self._login_name,
            "password": self._auth_password
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TOKEN_URL,
                    json=token_credentials,
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('code') == 200:
                            return data['data']['token']
                        else:
                            _LOGGER.error(f"Erreur d'authentification: {data.get('message')}")
                    else:
                        _LOGGER.error(f"Erreur HTTP lors de l'authentification: {response.status}")
        except Exception as e:
            _LOGGER.error(f"Erreur lors de la récupération du token: {e}")

        return None

    async def _set_power_value(self, token: str, power_value: int) -> bool:
        """Modifier la valeur de puissance via l'API."""
        import aiohttp

        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
            "appCode": self._app_code
        }
        params = {
            "equipId": self._device_id,
            "power": power_value
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    SET_POWER_URL,
                    headers=headers,
                    params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 200:
                            return True
                        else:
                            _LOGGER.error(f"Échec de la mise à jour: {data.get('message')}")
                    else:
                        _LOGGER.error(f"Erreur HTTP: {response.status}")
        except Exception as e:
            _LOGGER.error(f"Erreur lors de la modification de la puissance: {e}")

        return False 