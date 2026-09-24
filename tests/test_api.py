"""Tests for the 8311 ONT API parsing."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.ont_8311.api import (
    OntClient,
    parse_alarms,
    parse_key_values,
    parse_temperatures,
)

from .conftest import load


def test_parse_key_values() -> None:
    """Key/value pages are parsed."""
    optical = parse_key_values(load("pontop_optical.txt"))
    assert optical["Receive power"] == "-15.33 dBm"
    assert optical["Receiver status"] == "OK"


def test_parse_temperatures() -> None:
    """Temperatures are parsed in Celsius."""
    assert parse_temperatures(
        "76.01 °C (168.8 °F) / 75.13 °C (167.2 °F) / 65.48 °C (149.9 °F)"
    ) == [76.01, 75.13, 65.48]


def test_parse_alarms() -> None:
    """Alarm tables are parsed."""
    assert parse_alarms(load("pontop_alarms.txt")) == []
    text = (
        "Page: Active alarms\n"
        "Alarm type       Alarm                     Description                   \n"
        "ONU              LOS                       Loss of signal\n"
    )
    assert parse_alarms(text) == [
        {"type": "ONU", "alarm": "LOS", "description": "Loss of signal"}
    ]


async def test_get_data(mock_ont) -> None:
    """All data is parsed from fixtures."""
    client = OntClient(MagicMock(), "192.168.11.1", "root", "")
    data = await client.get_data()
    assert data["ploam_state"] == "O5.1"
    assert data["ploam_state_description"] == "Associated state"
    assert data["pon_mode"] == "XGS-PON"
    assert data["eth_speed"] == 10000
    assert data["rx_power"] == -15.33
    assert data["tx_power"] == 5.6
    assert data["optic_temperature"] == 66.23
    assert data["fec_codewords_uncorrected"] == 0
    assert data["downstream_bytes"] > data["upstream_bytes"] > 0
    assert data["uptime"] == 977194
    assert data["load_1m"] == 0.63
    assert data["alarms"] == []

    info = await client.get_device_info()
    assert info.serial_number == "TESTSERIAL0001"
    assert info.model == "XGSPONST2001"
    assert info.firmware_version == "v2.8.3"
    assert info.firmware_variant == "basic"
