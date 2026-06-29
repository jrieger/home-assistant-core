"""The GPSD integration."""

from gpsd_client_async import GpsdClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.SENSOR]

type GPSDConfigEntry = ConfigEntry[GpsdClient]


async def async_setup_entry(hass: HomeAssistant, entry: GPSDConfigEntry) -> bool:
    """Set up GPSD from a config entry."""
    client = GpsdClient(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT])
    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GPSDConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
