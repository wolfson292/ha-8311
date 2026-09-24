"""Diagnostics for the 8311 ONT integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import OntConfigEntry

TO_REDACT = {CONF_PASSWORD, "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OntConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "device_info": async_redact_data(asdict(coordinator.device_info), TO_REDACT),
        "data": coordinator.data,
    }
