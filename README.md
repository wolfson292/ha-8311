# 8311 ONT for Home Assistant

A Home Assistant integration for XGS-PON / GPON SFP+ ONT sticks running the
[8311 community firmware](https://github.com/djGrrr/8311-was-110-firmware-builder)
(WAS-110, PRX126, and similar). It logs in to the ONT's LuCI web interface
and polls optical levels, PON link state, error counters and traffic.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=wolfson292&repository=ha-8311&category=integration)

## Installation

### HACS (recommended)

1. In HACS, open the ⋮ menu → **Custom repositories**.
2. Add `https://github.com/wolfson292/ha-8311` with type **Integration**.
3. Search for **8311 ONT**, download it, and restart Home Assistant.

### Manual

Copy `custom_components/ont_8311` into your Home Assistant `config/custom_components/`
directory and restart.

## Configuration

**Settings → Devices & services → Add integration → 8311 ONT**

| Field | Default | Notes |
| --- | --- | --- |
| Host | `192.168.11.1` | IP or hostname of the ONT. Home Assistant must be able to route to it. |
| Username | `root` | LuCI username. |
| Password | *(blank)* | LuCI password. Leave blank if none is set. |
| Verify SSL | off | The ONT ships with a self-signed certificate. |

The polling interval (default 30 s) can be changed from the integration's **Configure** button.
Host and credentials can be changed later with **Reconfigure**.

> **Routing tip:** the ONT's management IP (usually `192.168.11.1`) lives on its own subnet.
> Most routers need a static route or an extra IP on the WAN interface before other LAN
> hosts can reach it. See the [8311 wiki](https://pon.wiki/) for details.

## Entities

| Entity | Notes |
| --- | --- |
| RX power, TX power (dBm) | Optical levels. |
| TX bias current, supply voltage | Diagnostic. |
| Optic / CPU 1 / CPU 2 temperature | |
| PLOAM state | e.g. `O5.1`, with a `description` attribute. |
| PON link (binary) | On when the ONT is in the O5 operational state. |
| Alarm (binary) | On when pontop reports active alarms; the list is in the `alarms` attribute. |
| Optical receiver (binary) | Problem sensor, on when the receiver status is not `OK`. |
| Downstream / upstream throughput | Calculated from the GEM port byte counters between polls. |
| Downstream / upstream data | Cumulative GEM byte counters (total increasing). |
| BIP errors, FEC corrected/uncorrected codewords, FEC errored seconds | Error counters. |
| HEC / PLOAM MIC error counters | Disabled by default. |
| PON mode, Ethernet link speed, active firmware bank, last boot, memory usage, load | Diagnostic. |
| ONU ID assignments, ranging events, deactivations | PLOAM message counters. If they go up, the OLT re-ranged or dropped the ONT. |
| QoS queue drops | WRED + CoDel drops across the PPv4 QoS queues; queues with drops are listed in the `queues` attribute. |
| T-CONT link (binary) | On when every T-CONT allocation is `LINKED` and every GEM port is `Valid`; allocations and GEM ports are listed in attributes. |
| OLT transmit optical level, ODN class, PON ID | Values reported by the OLT. Diagnostic. |
| PON chip firmware | PON IP firmware version, with HW/SW/pontop versions as attributes. Diagnostic. |
| Inactive bank firmware | Version of the firmware in the other bank, with revision and variant. Diagnostic. |
| PON serial number, vendor ID, equipment ID | Identity the ONT presents to the OLT (as set on the 8311 config page). Diagnostic; the serial is redacted from diagnostics downloads. |
| Fix VLANs, dying gasp / RX LOS / ping daemon enabled | 8311 configuration settings. Diagnostic. |
| IP host MAC, LCT MAC | Diagnostic; redacted from diagnostics downloads. |
| Restart (button) | Reboots the ONT. **This drops your internet connection** until it re-ranges. |

## How it works

The integration uses the same endpoints as the 8311 LuCI pages:

- `admin/8311/gpon_status` (JSON) for the status summary
- `admin/8311/pontop/<page>` for optical, FEC, GTC, alarm and GEM counters
- the `ubus` JSON-RPC API (with the LuCI session) for uptime, memory and load

Each LuCI page costs the ONT roughly half a second of CPU (the configuration page about
six), and LuCI serves them one at a time. So only optical levels, FEC/GTC counters,
alarms, traffic and system stats are polled every interval (7 requests, ~4 s of ONT time).
PLOAM counters, queue drops, T-CONT/GEM state, OLT parameters, firmware banks and
configuration are refreshed every 5 minutes.

## Development

```bash
pip install -r requirements_test.txt
pytest
```

## License

MIT
