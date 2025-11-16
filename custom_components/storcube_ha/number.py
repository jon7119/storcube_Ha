"""Number platform for Storcube Battery Monitor."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE_ID,
    UnitOfPower,
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfElectricCurrent,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    DOMAIN,
    NAME,
    SET_POWER_URL,
    SET_THRESHOLD_URL,
    TOKEN_URL,
    CONF_APP_CODE,
    CONF_LOGIN_NAME,
    CONF_AUTH_PASSWORD,
    DEVICE_SETTINGS_URL,
    POWER_SETTINGS_URL,
    CONF_DEVICE_ID,
)


_LOGGER = logging.getLogger(__name__)


class StorcubeBaseNumber(NumberEntity):
    """Classe de base pour tous les numbers Storcube."""
    
    def __init__(self, config: ConfigType, device_id: str) -> None:
        """Initialize base number."""
        self._config = config
        self._device_id = device_id
    
    @property
    def device_info(self) -> DeviceInfo:
        """Retourner les informations de l'appareil."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name="StorCube Battery Monitor",
            manufacturer="StorCube",
            model="S1000",
        )


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

    # Créer les entités de contrôle
    entities = [
        StorcubePowerNumber(
            config,
            device_id,
            app_code,
            login_name,
            auth_password,
        ),
        StorcubeThresholdNumber(
            config,
            device_id,
            app_code,
            login_name,
            auth_password,
        ),
        StorcubeChargeLimitNumber(
            config,
            device_id,
            app_code,
            login_name,
            auth_password,
        ),
        StorcubeDischargeLimitNumber(
            config,
            device_id,
            app_code,
            login_name,
            auth_password,
        ),
        StorcubeVoltageSetpointNumber(
            config,
            device_id,
            app_code,
            login_name,
            auth_password,
        ),
        StorcubeCurrentSetpointNumber(
            config,
            device_id,
            app_code,
            login_name,
            auth_password,
        ),
        StorcubePowerLimitNumber(
            config,
            device_id,
            app_code,
            login_name,
            auth_password,
        ),
        StorcubeTemperatureLimitNumber(
            config,
            device_id,
            app_code,
            login_name,
            auth_password,
        ),
    ]

    async_add_entities(entities)


class StorcubePowerNumber(StorcubeBaseNumber):
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
        super().__init__(config, device_id)
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


class StorcubeThresholdNumber(StorcubeBaseNumber):
    """Représente le contrôle du seuil de batterie StorCube."""

    def __init__(
        self,
        config: ConfigType,
        device_id: str,
        app_code: str,
        login_name: str,
        auth_password: str,
    ) -> None:
        """Initialize the Storcube Threshold Number."""
        super().__init__(config, device_id)
        self._app_code = app_code
        self._login_name = login_name
        self._auth_password = auth_password
        self._attr_name = f"Seuil de Batterie StorCube"
        self._attr_unique_id = f"{device_id}_battery_threshold"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 100.0
        self._attr_native_step = 1.0
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_value = 80.0  # Valeur par défaut

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
        # Synchroniser la valeur du seuil avec l'API au démarrage
        await self._update_current_threshold()

    async def _update_current_threshold(self):
        """Récupérer la valeur actuelle du seuil depuis l'API."""
        try:
            token = await self._get_auth_token()
            if not token:
                _LOGGER.warning("Impossible de récupérer le token pour la synchronisation initiale")
                return

            current_value = await self._get_current_threshold(token)
            if current_value is not None:
                self._attr_native_value = float(current_value)
                self.async_write_ha_state()
                _LOGGER.info(f"Seuil synchronisé avec la valeur actuelle: {current_value}%")
            else:
                _LOGGER.warning("Impossible de récupérer la valeur actuelle du seuil")
        except Exception as e:
            _LOGGER.error(f"Erreur lors de la synchronisation du seuil: {e}")

    async def _get_current_threshold(self, token: str) -> int | None:
        """Récupérer la valeur actuelle du seuil depuis l'API."""
        import aiohttp

        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
            "appCode": self._app_code
        }
        params = {"equipId": self._device_id}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "http://baterway.com/api/scene/threshold/query",
                    headers=headers,
                    params=params
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "data" in data:
                            return int(data["data"])
                        else:
                            _LOGGER.debug(f"Réponse inattendue pour le seuil: {data}")
                    else:
                        _LOGGER.debug(f"Erreur HTTP {response.status} lors de la récupération du seuil")
        except Exception as e:
            _LOGGER.error(f"Erreur lors de la récupération du seuil actuel: {e}")

        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the threshold value."""
        try:
            # Récupérer le token d'authentification
            token = await self._get_auth_token()
            if not token:
                _LOGGER.error("Impossible de récupérer le token d'authentification")
                return

            # Appeler l'API pour modifier le seuil
            success = await self._set_threshold_value(token, int(value))
            if success:
                self._attr_native_value = value
                self.async_write_ha_state()
                _LOGGER.info(f"Seuil de batterie mis à jour avec succès: {value}%")
            else:
                _LOGGER.error(f"Échec de la mise à jour du seuil: {value}%")

        except Exception as e:
            _LOGGER.error(f"Erreur lors de la modification du seuil: {e}")

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

    async def _set_threshold_value(self, token: str, threshold_value: int) -> bool:
        """Modifier la valeur du seuil via l'API."""
        import aiohttp

        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
            "appCode": self._app_code
        }

        # Essayer différents paramètres possibles pour le seuil
        payloads = [
            {"reserved": str(threshold_value), "equipId": self._device_id},
            {"data": str(threshold_value), "equipId": self._device_id},
            {"threshold": str(threshold_value), "equipId": self._device_id}
        ]

        try:
            async with aiohttp.ClientSession() as session:
                for payload in payloads:
                    _LOGGER.debug(f"Tentative avec payload: {payload}")
                    async with session.post(
                        SET_THRESHOLD_URL,
                        headers=headers,
                        json=payload
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("code") == 200:
                                _LOGGER.info(f"Seuil mis à jour avec succès avec {list(payload.keys())[0]}")
                                return True
                            else:
                                _LOGGER.debug(f"Échec avec {list(payload.keys())[0]}: {data.get('message')}")
                        else:
                            _LOGGER.debug(f"Erreur HTTP {response.status} avec {list(payload.keys())[0]}")

            _LOGGER.error("Aucun des paramètres testés n'a fonctionné pour le seuil")
            return False

        except Exception as e:
            _LOGGER.error(f"Erreur lors de la modification du seuil: {e}")
            return False


class StorcubeChargeLimitNumber(StorcubeBaseNumber):
    """Représente le contrôle de la limite de charge."""

    def __init__(
        self,
        config: ConfigType,
        device_id: str,
        app_code: str,
        login_name: str,
        auth_password: str,
    ) -> None:
        """Initialize the Storcube Charge Limit Number."""
        super().__init__(config, device_id)
        self._app_code = app_code
        self._login_name = login_name
        self._auth_password = auth_password
        self._attr_name = f"Limite de Charge StorCube"
        self._attr_unique_id = f"{device_id}_charge_limit"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 100.0
        self._attr_native_step = 1.0
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_value = 80.0

    async def async_set_native_value(self, value: float) -> None:
        """Set the charge limit value."""
        token = await self._get_auth_token()
        if not token:
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    DEVICE_SETTINGS_URL,
                    json={"device_id": self._device_id, "charge_limit": int(value)},
                    headers={
                        "Authorization": token,
                        "Content-Type": "application/json",
                        "appCode": self._app_code
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 200:
                            self._attr_native_value = value
                            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Erreur lors de la modification de la limite de charge: {e}")

    async def _get_auth_token(self) -> str | None:
        """Récupérer le token d'authentification."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TOKEN_URL,
                    json={
                        "appCode": self._app_code,
                        "loginName": self._login_name,
                        "password": self._auth_password
                    },
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('code') == 200:
                            return data['data']['token']
        except Exception as e:
            _LOGGER.error(f"Erreur lors de la récupération du token: {e}")
        return None


class StorcubeDischargeLimitNumber(StorcubeBaseNumber):
    """Représente le contrôle de la limite de décharge."""

    def __init__(
        self,
        config: ConfigType,
        device_id: str,
        app_code: str,
        login_name: str,
        auth_password: str,
    ) -> None:
        """Initialize the Storcube Discharge Limit Number."""
        super().__init__(config, device_id)
        self._app_code = app_code
        self._login_name = login_name
        self._auth_password = auth_password
        self._attr_name = f"Limite de Décharge StorCube"
        self._attr_unique_id = f"{device_id}_discharge_limit"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 100.0
        self._attr_native_step = 1.0
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_value = 20.0

    async def async_set_native_value(self, value: float) -> None:
        """Set the discharge limit value."""
        token = await self._get_auth_token()
        if not token:
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    DEVICE_SETTINGS_URL,
                    json={"device_id": self._device_id, "discharge_limit": int(value)},
                    headers={
                        "Authorization": token,
                        "Content-Type": "application/json",
                        "appCode": self._app_code
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 200:
                            self._attr_native_value = value
                            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Erreur lors de la modification de la limite de décharge: {e}")

    async def _get_auth_token(self) -> str | None:
        """Récupérer le token d'authentification."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TOKEN_URL,
                    json={
                        "appCode": self._app_code,
                        "loginName": self._login_name,
                        "password": self._auth_password
                    },
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('code') == 200:
                            return data['data']['token']
        except Exception as e:
            _LOGGER.error(f"Erreur lors de la récupération du token: {e}")
        return None


class StorcubeVoltageSetpointNumber(StorcubeBaseNumber):
    """Représente le contrôle de la consigne de tension."""

    def __init__(
        self,
        config: ConfigType,
        device_id: str,
        app_code: str,
        login_name: str,
        auth_password: str,
    ) -> None:
        """Initialize the Storcube Voltage Setpoint Number."""
        super().__init__(config, device_id)
        self._app_code = app_code
        self._login_name = login_name
        self._auth_password = auth_password
        self._attr_name = f"Consigne Tension StorCube"
        self._attr_unique_id = f"{device_id}_voltage_setpoint"
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 500.0
        self._attr_native_step = 1.0
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_value = 230.0

    async def async_set_native_value(self, value: float) -> None:
        """Set the voltage setpoint value."""
        token = await self._get_auth_token()
        if not token:
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    POWER_SETTINGS_URL,
                    json={"device_id": self._device_id, "voltage_setpoint": float(value)},
                    headers={
                        "Authorization": token,
                        "Content-Type": "application/json",
                        "appCode": self._app_code
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 200:
                            self._attr_native_value = value
                            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Erreur lors de la modification de la consigne de tension: {e}")

    async def _get_auth_token(self) -> str | None:
        """Récupérer le token d'authentification."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TOKEN_URL,
                    json={
                        "appCode": self._app_code,
                        "loginName": self._login_name,
                        "password": self._auth_password
                    },
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('code') == 200:
                            return data['data']['token']
        except Exception as e:
            _LOGGER.error(f"Erreur lors de la récupération du token: {e}")
        return None


class StorcubeCurrentSetpointNumber(StorcubeBaseNumber):
    """Représente le contrôle de la consigne de courant."""

    def __init__(
        self,
        config: ConfigType,
        device_id: str,
        app_code: str,
        login_name: str,
        auth_password: str,
    ) -> None:
        """Initialize the Storcube Current Setpoint Number."""
        super().__init__(config, device_id)
        self._app_code = app_code
        self._login_name = login_name
        self._auth_password = auth_password
        self._attr_name = f"Consigne Courant StorCube"
        self._attr_unique_id = f"{device_id}_current_setpoint"
        self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 100.0
        self._attr_native_step = 0.1
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_value = 10.0

    async def async_set_native_value(self, value: float) -> None:
        """Set the current setpoint value."""
        token = await self._get_auth_token()
        if not token:
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    POWER_SETTINGS_URL,
                    json={"device_id": self._device_id, "current_setpoint": float(value)},
                    headers={
                        "Authorization": token,
                        "Content-Type": "application/json",
                        "appCode": self._app_code
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 200:
                            self._attr_native_value = value
                            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Erreur lors de la modification de la consigne de courant: {e}")

    async def _get_auth_token(self) -> str | None:
        """Récupérer le token d'authentification."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TOKEN_URL,
                    json={
                        "appCode": self._app_code,
                        "loginName": self._login_name,
                        "password": self._auth_password
                    },
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('code') == 200:
                            return data['data']['token']
        except Exception as e:
            _LOGGER.error(f"Erreur lors de la récupération du token: {e}")
        return None


class StorcubePowerLimitNumber(StorcubeBaseNumber):
    """Représente le contrôle de la limite de puissance."""

    def __init__(
        self,
        config: ConfigType,
        device_id: str,
        app_code: str,
        login_name: str,
        auth_password: str,
    ) -> None:
        """Initialize the Storcube Power Limit Number."""
        super().__init__(config, device_id)
        self._app_code = app_code
        self._login_name = login_name
        self._auth_password = auth_password
        self._attr_name = f"Limite de Puissance StorCube"
        self._attr_unique_id = f"{device_id}_power_limit"
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_native_min_value = 0.0
        self._attr_native_max_value = 10000.0
        self._attr_native_step = 100.0
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_value = 5000.0

    async def async_set_native_value(self, value: float) -> None:
        """Set the power limit value."""
        token = await self._get_auth_token()
        if not token:
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    POWER_SETTINGS_URL,
                    json={"device_id": self._device_id, "power_limit": int(value)},
                    headers={
                        "Authorization": token,
                        "Content-Type": "application/json",
                        "appCode": self._app_code
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 200:
                            self._attr_native_value = value
                            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Erreur lors de la modification de la limite de puissance: {e}")

    async def _get_auth_token(self) -> str | None:
        """Récupérer le token d'authentification."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TOKEN_URL,
                    json={
                        "appCode": self._app_code,
                        "loginName": self._login_name,
                        "password": self._auth_password
                    },
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('code') == 200:
                            return data['data']['token']
        except Exception as e:
            _LOGGER.error(f"Erreur lors de la récupération du token: {e}")
        return None


class StorcubeTemperatureLimitNumber(StorcubeBaseNumber):
    """Représente le contrôle de la limite de température."""

    def __init__(
        self,
        config: ConfigType,
        device_id: str,
        app_code: str,
        login_name: str,
        auth_password: str,
    ) -> None:
        """Initialize the Storcube Temperature Limit Number."""
        super().__init__(config, device_id)
        self._app_code = app_code
        self._login_name = login_name
        self._auth_password = auth_password
        self._attr_name = f"Limite de Température StorCube"
        self._attr_unique_id = f"{device_id}_temperature_limit"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_native_min_value = -20.0
        self._attr_native_max_value = 80.0
        self._attr_native_step = 1.0
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_value = 60.0

    async def async_set_native_value(self, value: float) -> None:
        """Set the temperature limit value."""
        token = await self._get_auth_token()
        if not token:
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    DEVICE_SETTINGS_URL,
                    json={"device_id": self._device_id, "temperature_limit": float(value)},
                    headers={
                        "Authorization": token,
                        "Content-Type": "application/json",
                        "appCode": self._app_code
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("code") == 200:
                            self._attr_native_value = value
                            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Erreur lors de la modification de la limite de température: {e}")

    async def _get_auth_token(self) -> str | None:
        """Récupérer le token d'authentification."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TOKEN_URL,
                    json={
                        "appCode": self._app_code,
                        "loginName": self._login_name,
                        "password": self._auth_password
                    },
                    headers={'Content-Type': 'application/json'}
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('code') == 200:
                            return data['data']['token']
        except Exception as e:
            _LOGGER.error(f"Erreur lors de la récupération du token: {e}")
        return None 
