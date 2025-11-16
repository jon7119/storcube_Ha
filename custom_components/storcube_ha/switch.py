"""Support for Storcube Battery Monitor switches."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    DOMAIN,
    CONF_DEVICE_ID,
    CONF_APP_CODE,
    CONF_LOGIN_NAME,
    CONF_AUTH_PASSWORD,
    TOKEN_URL,
    DEVICE_CONTROL_URL,
    SCENE_EXECUTE_URL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches from a config entry."""
    config = config_entry.data
    
    switches = [
        StorcubeDevicePowerSwitch(config),
        StorcubeGridConnectionSwitch(config),
        StorcubeBatteryChargeSwitch(config),
        StorcubeBatteryDischargeSwitch(config),
        StorcubePvEnableSwitch(config),
        StorcubeLoadEnableSwitch(config),
        StorcubeSceneEnableSwitch(config),
    ]

    async_add_entities(switches)


class StorcubeBaseSwitch(SwitchEntity):
    """Base class for Storcube switches."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the switch."""
        self._config = config
        self._device_id = config[CONF_DEVICE_ID]
        self._app_code = config.get(CONF_APP_CODE, "Storcube")
        self._login_name = config[CONF_LOGIN_NAME]
        self._auth_password = config[CONF_AUTH_PASSWORD]
        self._attr_is_on = False
        self._attr_available = True
    
    @property
    def device_info(self) -> DeviceInfo:
        """Retourner les informations de l'appareil."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name="StorCube Battery Monitor",
            manufacturer="StorCube",
            model="S1000",
        )

    async def _get_auth_token(self) -> str | None:
        """Récupérer le token d'authentification."""
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

    async def _control_device(self, action: str, value: bool) -> bool:
        """Contrôler l'appareil via l'API."""
        token = await self._get_auth_token()
        if not token:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    DEVICE_CONTROL_URL,
                    json={
                        "device_id": self._device_id,
                        "action": action,
                        "value": value
                    },
                    headers={
                        "Authorization": token,
                        "Content-Type": "application/json",
                        "appCode": self._app_code
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("code") == 200
        except Exception as e:
            _LOGGER.error(f"Erreur lors du contrôle de l'appareil: {e}")
        return False


class StorcubeDevicePowerSwitch(StorcubeBaseSwitch):
    """Switch pour allumer/éteindre l'appareil."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the switch."""
        super().__init__(config)
        self._attr_name = "Alimentation Appareil Storcube"
        self._attr_unique_id = f"{self._device_id}_device_power"
        self._attr_icon = "mdi:power"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        if await self._control_device("device_power", True):
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        if await self._control_device("device_power", False):
            self._attr_is_on = False
            self.async_write_ha_state()


class StorcubeGridConnectionSwitch(StorcubeBaseSwitch):
    """Switch pour la connexion au réseau."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the switch."""
        super().__init__(config)
        self._attr_name = "Connexion Réseau Storcube"
        self._attr_unique_id = f"{self._device_id}_grid_connection"
        self._attr_icon = "mdi:transmission-tower"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on grid connection."""
        if await self._control_device("grid_connection", True):
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off grid connection."""
        if await self._control_device("grid_connection", False):
            self._attr_is_on = False
            self.async_write_ha_state()


class StorcubeBatteryChargeSwitch(StorcubeBaseSwitch):
    """Switch pour activer la charge de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the switch."""
        super().__init__(config)
        self._attr_name = "Charge Batterie Storcube"
        self._attr_unique_id = f"{self._device_id}_battery_charge"
        self._attr_icon = "mdi:battery-charging"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on battery charge."""
        if await self._control_device("battery_charge", True):
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off battery charge."""
        if await self._control_device("battery_charge", False):
            self._attr_is_on = False
            self.async_write_ha_state()


class StorcubeBatteryDischargeSwitch(StorcubeBaseSwitch):
    """Switch pour activer la décharge de la batterie."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the switch."""
        super().__init__(config)
        self._attr_name = "Décharge Batterie Storcube"
        self._attr_unique_id = f"{self._device_id}_battery_discharge"
        self._attr_icon = "mdi:battery-arrow-down"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on battery discharge."""
        if await self._control_device("battery_discharge", True):
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off battery discharge."""
        if await self._control_device("battery_discharge", False):
            self._attr_is_on = False
            self.async_write_ha_state()


class StorcubePvEnableSwitch(StorcubeBaseSwitch):
    """Switch pour activer le PV."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the switch."""
        super().__init__(config)
        self._attr_name = "Activation PV Storcube"
        self._attr_unique_id = f"{self._device_id}_pv_enable"
        self._attr_icon = "mdi:solar-power"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on PV."""
        if await self._control_device("pv_enable", True):
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off PV."""
        if await self._control_device("pv_enable", False):
            self._attr_is_on = False
            self.async_write_ha_state()


class StorcubeLoadEnableSwitch(StorcubeBaseSwitch):
    """Switch pour activer la charge."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the switch."""
        super().__init__(config)
        self._attr_name = "Activation Charge Storcube"
        self._attr_unique_id = f"{self._device_id}_load_enable"
        self._attr_icon = "mdi:home-lightning-bolt"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on load."""
        if await self._control_device("load_enable", True):
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off load."""
        if await self._control_device("load_enable", False):
            self._attr_is_on = False
            self.async_write_ha_state()


class StorcubeSceneEnableSwitch(StorcubeBaseSwitch):
    """Switch pour activer une scène."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the switch."""
        super().__init__(config)
        self._attr_name = "Activation Scène Storcube"
        self._attr_unique_id = f"{self._device_id}_scene_enable"
        self._attr_icon = "mdi:play-circle"

    async def _execute_scene(self, scene_id: str, enable: bool) -> bool:
        """Exécuter une scène."""
        token = await self._get_auth_token()
        if not token:
            return False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    SCENE_EXECUTE_URL,
                    json={
                        "device_id": self._device_id,
                        "scene_id": scene_id,
                        "enable": enable
                    },
                    headers={
                        "Authorization": token,
                        "Content-Type": "application/json",
                        "appCode": self._app_code
                    }
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("code") == 200
        except Exception as e:
            _LOGGER.error(f"Erreur lors de l'exécution de la scène: {e}")
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on scene."""
        scene_id = kwargs.get("scene_id", "default")
        if await self._execute_scene(scene_id, True):
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off scene."""
        scene_id = kwargs.get("scene_id", "default")
        if await self._execute_scene(scene_id, False):
            self._attr_is_on = False
            self.async_write_ha_state()

