"""Data update coordinator for the 8311 ONT integration."""

from __future__ import annotations

from datetime import timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OntAuthError, OntClient, OntDeviceInfo, OntError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type OntConfigEntry = ConfigEntry[OntCoordinator]


class OntCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the ONT."""

    config_entry: OntConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: OntConfigEntry,
        client: OntClient,
        device_info: OntDeviceInfo,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.device_info = device_info
        self._last_sample: tuple[float, int, int] | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.client.get_data()
        except OntAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except OntError as err:
            raise UpdateFailed(str(err)) from err

        # Derive throughput from the GEM byte counters
        now = time.monotonic()
        up, down = data["upstream_bytes"], data["downstream_bytes"]
        data["upstream_throughput"] = data["downstream_throughput"] = None
        if self._last_sample is not None:
            last_time, last_up, last_down = self._last_sample
            elapsed = now - last_time
            if elapsed > 0 and up >= last_up and down >= last_down:
                data["upstream_throughput"] = round((up - last_up) * 8 / elapsed / 1e6, 2)
                data["downstream_throughput"] = round(
                    (down - last_down) * 8 / elapsed / 1e6, 2
                )
        self._last_sample = (now, up, down)
        return data
