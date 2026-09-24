"""The 8311 ONT integration."""

from __future__ import annotations

import aiohttp
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import OntAuthError, OntClient, OntError
from .const import CONF_VERIFY_SSL
from .coordinator import OntConfigEntry, OntCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR]


def create_client(hass: HomeAssistant, data: dict) -> OntClient:
    """Create an API client from config entry data."""
    session = async_create_clientsession(
        hass,
        verify_ssl=data.get(CONF_VERIFY_SSL, False),
        cookie_jar=aiohttp.DummyCookieJar(),
    )
    return OntClient(
        session, data[CONF_HOST], data[CONF_USERNAME], data.get(CONF_PASSWORD, "")
    )


async def async_setup_entry(hass: HomeAssistant, entry: OntConfigEntry) -> bool:
    """Set up 8311 ONT from a config entry."""
    client = create_client(hass, dict(entry.data))
    try:
        device_info = await client.get_device_info()
    except OntAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except OntError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = OntCoordinator(hass, entry, client, device_info)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OntConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
