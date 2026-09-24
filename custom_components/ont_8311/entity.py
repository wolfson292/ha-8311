"""Base entity for the 8311 ONT integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import OntCoordinator


class OntEntity(CoordinatorEntity[OntCoordinator]):
    """Entity backed by the ONT coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OntCoordinator, description: EntityDescription) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        info = coordinator.device_info
        unique = coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
        self._attr_unique_id = f"{unique}_{description.key}"
        firmware = info.firmware_version
        if firmware and info.firmware_variant:
            firmware = f"{firmware} ({info.firmware_variant})"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique)},
            name=info.hostname or "8311 ONT",
            manufacturer=MANUFACTURER,
            model=info.model,
            hw_version=info.hw_version,
            sw_version=firmware,
            serial_number=info.serial_number,
            configuration_url=f"https://{coordinator.client.host}/cgi-bin/luci/admin/8311/pon_status",
        )
