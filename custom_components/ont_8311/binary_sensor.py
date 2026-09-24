"""Binary sensors for the 8311 ONT integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OntConfigEntry
from .entity import OntEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OntBinarySensorDescription(BinarySensorEntityDescription):
    """Describes an ONT binary sensor."""

    is_on_fn: Callable[[dict[str, Any]], bool | None]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


BINARY_SENSORS: tuple[OntBinarySensorDescription, ...] = (
    OntBinarySensorDescription(
        key="pon_link",
        translation_key="pon_link",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        # O5 (O5.1 / O5.2) is the operational/associated state
        is_on_fn=lambda d: (d.get("ploam_state") or "").startswith("O5"),
    ),
    OntBinarySensorDescription(
        key="alarm",
        translation_key="alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda d: bool(d.get("alarms")),
        attrs_fn=lambda d: {"alarms": d.get("alarms") or []},
    ),
    OntBinarySensorDescription(
        key="receiver_problem",
        translation_key="receiver_problem",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda d: None
        if d.get("receiver_status") is None
        else d["receiver_status"].upper() != "OK",
        attrs_fn=lambda d: {
            "receiver_status": d.get("receiver_status"),
            "transmitter_status": d.get("transmitter_status"),
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OntConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        OntBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class OntBinarySensor(OntEntity, BinarySensorEntity):
    """An ONT binary sensor."""

    entity_description: OntBinarySensorDescription

    @property
    def is_on(self) -> bool | None:
        """Return the state."""
        return self.entity_description.is_on_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.entity_description.attrs_fn:
            return self.entity_description.attrs_fn(self.coordinator.data)
        return None
