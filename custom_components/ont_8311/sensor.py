"""Sensors for the 8311 ONT integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfDataRate,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import OntConfigEntry
from .entity import OntEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OntSensorDescription(SensorEntityDescription):
    """Describes an ONT sensor."""

    value_fn: Callable[[dict[str, Any]], Any] | None = None
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def _counter(key: str, **kwargs: Any) -> OntSensorDescription:
    return OntSensorDescription(
        key=key,
        translation_key=key,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        **kwargs,
    )


def _temperature(key: str, **kwargs: Any) -> OntSensorDescription:
    return OntSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        **kwargs,
    )


def _diagnostic(key: str, **kwargs: Any) -> OntSensorDescription:
    return OntSensorDescription(
        key=key, translation_key=key, entity_category=EntityCategory.DIAGNOSTIC, **kwargs
    )


def _boot_time(data: dict[str, Any]) -> datetime | None:
    if data.get("uptime") is None:
        return None
    # Round to the minute so the state doesn't change on every poll due to jitter
    boot = dt_util.utcnow() - timedelta(seconds=data["uptime"])
    return boot.replace(second=0, microsecond=0)


SENSORS: tuple[OntSensorDescription, ...] = (
    OntSensorDescription(
        key="rx_power",
        translation_key="rx_power",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        suggested_display_precision=2,
    ),
    OntSensorDescription(
        key="tx_power",
        translation_key="tx_power",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        suggested_display_precision=2,
    ),
    OntSensorDescription(
        key="tx_bias",
        translation_key="tx_bias",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    OntSensorDescription(
        key="voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _temperature("optic_temperature"),
    _temperature("cpu1_temperature"),
    _temperature("cpu2_temperature"),
    OntSensorDescription(
        key="ploam_state",
        translation_key="ploam_state",
        attrs_fn=lambda d: {"description": d.get("ploam_state_description")},
    ),
    OntSensorDescription(
        key="pon_mode",
        translation_key="pon_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    OntSensorDescription(
        key="eth_speed",
        translation_key="eth_speed",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    OntSensorDescription(
        key="active_bank",
        translation_key="active_bank",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    OntSensorDescription(
        key="downstream_throughput",
        translation_key="downstream_throughput",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=1,
    ),
    OntSensorDescription(
        key="upstream_throughput",
        translation_key="upstream_throughput",
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        suggested_display_precision=1,
    ),
    OntSensorDescription(
        key="downstream_bytes",
        translation_key="downstream_bytes",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
    ),
    OntSensorDescription(
        key="upstream_bytes",
        translation_key="upstream_bytes",
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIGABYTES,
        suggested_display_precision=2,
    ),
    _counter("bip_errors"),
    _counter("fec_codewords_corrected"),
    _counter("fec_codewords_uncorrected"),
    _counter("fec_errored_seconds"),
    _counter("psbd_hec_errors_uncorrected", entity_registry_enabled_default=False),
    _counter("fs_hec_errors_uncorrected", entity_registry_enabled_default=False),
    _counter("hec_lost_words", entity_registry_enabled_default=False),
    _counter("ploam_mic_errors", entity_registry_enabled_default=False),
    _counter("ploam_onu_id_assignments"),
    _counter("ploam_ranging"),
    _counter("ploam_deactivations"),
    OntSensorDescription(
        key="queue_drops",
        translation_key="queue_drops",
        state_class=SensorStateClass.TOTAL_INCREASING,
        attrs_fn=lambda d: {
            "queues": [
                q for q in d.get("queues") or [] if q["wred_drops"] or q["codel_drops"]
            ]
        },
    ),
    _diagnostic(
        "olt_tol",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ),
    _diagnostic("odn_class"),
    _diagnostic("pon_id"),
    _diagnostic(
        "pon_ip_fw_version",
        attrs_fn=lambda d: {
            "hw_version": d.get("pon_ip_hw_version"),
            "sw_version": d.get("pon_ip_sw_version"),
            "pontop_version": d.get("pontop_version"),
        },
    ),
    _diagnostic(
        "inactive_firmware",
        attrs_fn=lambda d: {
            "bank": d.get("inactive_firmware_bank"),
            "revision": d.get("inactive_firmware_revision"),
            "variant": d.get("inactive_firmware_variant"),
        },
    ),
    _diagnostic("pon_serial_number"),
    _diagnostic("vendor_id"),
    _diagnostic("equipment_id"),
    _diagnostic("fix_vlans"),
    _diagnostic("iphost_mac"),
    _diagnostic("lct_mac"),
    OntSensorDescription(
        key="boot_time",
        translation_key="boot_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_boot_time,
    ),
    OntSensorDescription(
        key="memory_usage",
        translation_key="memory_usage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    OntSensorDescription(
        key="load_1m",
        translation_key="load_1m",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    OntSensorDescription(
        key="load_5m",
        translation_key="load_5m",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OntConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    async_add_entities(OntSensor(coordinator, description) for description in SENSORS)


class OntSensor(OntEntity, SensorEntity):
    """An ONT sensor."""

    entity_description: OntSensorDescription

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        data = self.coordinator.data
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(data)
        return data.get(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.entity_description.attrs_fn:
            return self.entity_description.attrs_fn(self.coordinator.data)
        return None
