"""Config flow for GPSD integration."""

import asyncio
from typing import Any, override

from gpsd_client_async import GpsdClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 2947

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_HOST, default=DEFAULT_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


class GPSDConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GPSD."""

    VERSION = 1

    async def _test_connection(self, host: str, port: int) -> bool:
        """Test socket connection."""
        try:
            async with asyncio.timeout(3):
                async with GpsdClient(host=host, port=port):
                    return True
        except TimeoutError, OSError:
            return False

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._async_abort_entries_match(user_input)

            connected = await self._test_connection(
                user_input[CONF_HOST], user_input[CONF_PORT]
            )

            if not connected:
                return self.async_abort(reason="cannot_connect")

            port = ""
            if user_input[CONF_PORT] != DEFAULT_PORT:
                port = f":{user_input[CONF_PORT]}"

            return self.async_create_entry(
                title=user_input.get(CONF_NAME, f"GPS {user_input[CONF_HOST]}{port}"),
                data=user_input,
            )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)
