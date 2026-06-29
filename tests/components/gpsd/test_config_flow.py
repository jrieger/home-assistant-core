"""Test the GPSD config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.gpsd.config_flow import DEFAULT_HOST, DEFAULT_PORT
from homeassistant.components.gpsd.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form and create an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch("homeassistant.components.gpsd.config_flow.GpsdClient") as mock_client:
        mock_client.return_value.__aenter__.return_value = AsyncMock()
        mock_client.return_value.__aexit__.return_value = None

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: DEFAULT_HOST,
                CONF_PORT: DEFAULT_PORT,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["data"] == {
        CONF_HOST: DEFAULT_HOST,
        CONF_PORT: DEFAULT_PORT,
    }
    mock_setup_entry.assert_called_once()


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test connection to host error."""
    with patch("homeassistant.components.gpsd.config_flow.GpsdClient") as mock_client:
        mock_client.return_value.__aenter__.side_effect = OSError

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_HOST: DEFAULT_HOST, CONF_PORT: DEFAULT_PORT},
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "cannot_connect"
