"""Buttons for the 8311 ONT integration."""

from __future__ import annotations

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import OntError
from .coordinator import OntConfigEntry
from .entity import OntEntity

PARALLEL_UPDATES = 1

REBOOT = ButtonEntityDescription(
    key="reboot",
    device_class=ButtonDeviceClass.RESTART,
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OntConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons."""
    async_add_entities([OntRebootButton(entry.runtime_data, REBOOT)])


class OntRebootButton(OntEntity, ButtonEntity):
    """Reboots the ONT. This interrupts the internet connection."""

    async def async_press(self) -> None:
        """Reboot the ONT."""
        try:
            await self.coordinator.client.reboot()
        except OntError as err:
            raise HomeAssistantError(f"Failed to reboot ONT: {err}") from err
