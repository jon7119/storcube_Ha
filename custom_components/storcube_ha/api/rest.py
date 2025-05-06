"""REST API client for Storcube Battery Monitor integration."""
from __future__ import annotations

import logging
import aiohttp
import async_timeout
from typing import Any, Dict, Optional

from ..const import (
    TOKEN_URL,
    FIRMWARE_URL,
    OUTPUT_URL,
    SET_POWER_URL,
    SET_THRESHOLD_URL,
)

_LOGGER = logging.getLogger(__name__)

class StorcubeRestClient:
    """REST API client for Storcube Battery Monitor."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        app_code: str,
        login_name: str,
        auth_password: str,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        """Initialize the REST API client."""
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._app_code = app_code
        self._login_name = login_name
        self._auth_password = auth_password
        self._session = session
        self._token = None

    async def async_get_token(self) -> str:
        """Get authentication token."""
        if self._token:
            return self._token

        auth_data = {
            "appCode": self._app_code,
            "loginName": self._login_name,
            "password": self._auth_password,
        }

        try:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.post(TOKEN_URL, json=auth_data) as response:
                        if response.status != 200:
                            raise Exception(f"Authentication failed with status {response.status}")
                        
                        json_response = await response.json()
                        if json_response.get("code") != 200:
                            raise Exception(f"API error: {json_response.get('message', 'Unknown error')}")
                        
                        self._token = json_response.get("data", {}).get("token")
                        return self._token

        except Exception as e:
            _LOGGER.error("Error getting token: %s", str(e))
            raise

    async def async_get_firmware_info(self) -> Dict[str, Any]:
        """Get firmware information."""
        token = await self.async_get_token()
        headers = {"Authorization": f"Bearer {token}"}

        try:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.get(FIRMWARE_URL, headers=headers) as response:
                        if response.status != 200:
                            raise Exception(f"Failed to get firmware info with status {response.status}")
                        
                        json_response = await response.json()
                        if json_response.get("code") != 200:
                            raise Exception(f"API error: {json_response.get('message', 'Unknown error')}")
                        
                        return json_response.get("data", {})

        except Exception as e:
            _LOGGER.error("Error getting firmware info: %s", str(e))
            raise

    async def async_get_output_info(self) -> Dict[str, Any]:
        """Get output information."""
        token = await self.async_get_token()
        headers = {"Authorization": f"Bearer {token}"}

        try:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.get(OUTPUT_URL, headers=headers) as response:
                        if response.status != 200:
                            raise Exception(f"Failed to get output info with status {response.status}")
                        
                        json_response = await response.json()
                        if json_response.get("code") != 200:
                            raise Exception(f"API error: {json_response.get('message', 'Unknown error')}")
                        
                        return json_response.get("data", {})

        except Exception as e:
            _LOGGER.error("Error getting output info: %s", str(e))
            raise

    async def async_set_power(self, equip_id: str, power_on: bool) -> None:
        """Set power state."""
        token = await self.async_get_token()
        headers = {"Authorization": f"Bearer {token}"}
        data = {
            "equipId": equip_id,
            "powerOn": power_on,
        }

        try:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.post(SET_POWER_URL, headers=headers, json=data) as response:
                        if response.status != 200:
                            raise Exception(f"Failed to set power with status {response.status}")
                        
                        json_response = await response.json()
                        if json_response.get("code") != 200:
                            raise Exception(f"API error: {json_response.get('message', 'Unknown error')}")

        except Exception as e:
            _LOGGER.error("Error setting power: %s", str(e))
            raise

    async def async_set_threshold(self, equip_id: str, threshold: int) -> None:
        """Set threshold value."""
        token = await self.async_get_token()
        headers = {"Authorization": f"Bearer {token}"}
        data = {
            "equipId": equip_id,
            "threshold": threshold,
        }

        try:
            async with async_timeout.timeout(10):
                async with aiohttp.ClientSession() as session:
                    async with session.post(SET_THRESHOLD_URL, headers=headers, json=data) as response:
                        if response.status != 200:
                            raise Exception(f"Failed to set threshold with status {response.status}")
                        
                        json_response = await response.json()
                        if json_response.get("code") != 200:
                            raise Exception(f"API error: {json_response.get('message', 'Unknown error')}")

        except Exception as e:
            _LOGGER.error("Error setting threshold: %s", str(e))
            raise 