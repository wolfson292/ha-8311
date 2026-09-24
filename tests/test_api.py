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

_LIST_KEYS = {
    "ploam_onu_id_assignments",
    "ploam_ranging",
    "ploam_deactivations",
    "queue_drops",
    "queues",
    "allocations",
    "gem_ports",
}


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

    slow = await client.get_slow_data()
    assert slow["ploam_onu_id_assignments"] == 16
    assert slow["ploam_ranging"] == 2
    assert slow["ploam_deactivations"] == 0
    assert slow["queue_drops"] == 1756
    assert slow["allocations"] == [
        {"alloc_id": 40, "status": "LINKED"},
        {"alloc_id": 1026, "status": "LINKED"},
    ]
    assert slow["gem_ports"][1] == {
        "gem_id": 2306,
        "alloc_id": 1026,
        "alloc_state": "Valid",
        "type": "Ethernet",
        "encryption": "None",
        "direction": "DS + US",
    }

    assert {k: v for k, v in slow.items() if k not in _LIST_KEYS} == {
        "olt_tol": 5.4,
        "odn_class": "N1",
        "pon_id": "0x00000000",
        "pon_ip_hw_version": "7",
        "pon_ip_fw_version": "3.21.0.3.16-1674463172",
        "pon_ip_sw_version": "1.22.9",
        "pontop_version": "1.7.2",
        "inactive_firmware": "v2.8.3",
        "inactive_firmware_bank": "B",
        "inactive_firmware_revision": "7d89440",
        "inactive_firmware_variant": "basic",
        "pon_serial_number": "TEST00000001",
        "vendor_id": "AXON",
        "equipment_id": "XGSPONST2001",
        "fix_vlans": "Enabled",
        "dying_gasp": False,
        "rx_los": False,
        "ping_daemon": True,
        "iphost_mac": "02:00:00:00:00:01",
        "lct_mac": "02:00:00:00:00:02",
    }

    info = await client.get_device_info()
    assert info.serial_number == "TESTSERIAL0001"
    assert info.model == "XGSPONST2001"
    assert info.firmware_version == "v2.8.3"
    assert info.firmware_variant == "basic"
