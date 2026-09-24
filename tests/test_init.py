"""Tests for the 8311 ONT config flow and setup."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.ont_8311.api import OntAuthError, OntConnectionError
from custom_components.ont_8311.const import CONF_VERIFY_SSL, DOMAIN

USER_INPUT = {
    CONF_HOST: "192.168.11.1",
    CONF_USERNAME: "root",
    CONF_PASSWORD: "",
    CONF_VERIFY_SSL: False,
}


async def _create_entry(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    await hass.async_block_till_done()
    return result


async def test_user_flow_and_setup(hass: HomeAssistant, mock_ont) -> None:
    """Configuring the ONT creates entities."""
    result = await _create_entry(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "prx126-sfp-pon"
    entry = result["result"]
    assert entry.unique_id == "TESTSERIAL0001"
    assert entry.state is ConfigEntryState.LOADED

    assert hass.states.get("sensor.prx126_sfp_pon_rx_power").state == "-15.33"
    assert hass.states.get("sensor.prx126_sfp_pon_ploam_state").state == "O5.1"
    assert hass.states.get("binary_sensor.prx126_sfp_pon_pon_link").state == "on"
    assert hass.states.get("binary_sensor.prx126_sfp_pon_alarm").state == "off"
    assert hass.states.get("binary_sensor.prx126_sfp_pon_optical_receiver").state == "off"
    assert hass.states.get("button.prx126_sfp_pon_restart") is not None
    assert hass.states.get("binary_sensor.prx126_sfp_pon_t_cont_link").state == "on"
    assert hass.states.get("binary_sensor.prx126_sfp_pon_dying_gasp_enabled").state == "off"
    assert hass.states.get("binary_sensor.prx126_sfp_pon_ping_daemon_enabled").state == "on"
    assert hass.states.get("sensor.prx126_sfp_pon_ranging_events").state == "2"
    assert hass.states.get("sensor.prx126_sfp_pon_qos_queue_drops").state == "1756"
    assert hass.states.get("sensor.prx126_sfp_pon_odn_class").state == "N1"
    assert hass.states.get("sensor.prx126_sfp_pon_inactive_bank_firmware").state == "v2.8.3"
    assert hass.states.get("sensor.prx126_sfp_pon_pon_serial_number").state == "TEST00000001"
    assert hass.states.get("sensor.prx126_sfp_pon_fix_vlans").state == "Enabled"
    assert hass.states.get("sensor.prx126_sfp_pon_lct_mac").state == "02:00:00:00:00:02"

    # Same ONT again is rejected
    result = await _create_entry(hass)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Options flow
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_SCAN_INTERVAL: 60}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.runtime_data.update_interval.total_seconds() == 60

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_user_flow_errors(hass: HomeAssistant, mock_ont) -> None:
    """Errors are shown on the form."""
    for exc, error in ((OntAuthError, "invalid_auth"), (OntConnectionError, "cannot_connect")):
        mock_ont.side_effect = exc("boom")
        result = await _create_entry(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": error}
