"""Async client for the LuCI web interface of 8311 community firmware ONTs."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import re
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)

# pontop pages polled on every update
PONTOP_PAGES = ("optical", "fec", "gtc", "alarms", "gem_stats")

_KV_RE = re.compile(r"^\s*(?P<key>[^:]+?)\s*:\s*(?P<value>.*?)\s*$")
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
_FIRMWARE_RE = re.compile(
    r"8311 Community Firmware MOD</a>.*?\[(?P<variant>[^\]]+)\]\s*-\s*"
    r"(?P<version>v?[\w.\-]+)\s*\((?P<commit>[0-9a-f]+)\)",
    re.DOTALL,
)


class OntError(Exception):
    """Base error talking to the ONT."""


class OntConnectionError(OntError):
    """The ONT could not be reached."""


class OntAuthError(OntError):
    """The ONT rejected the credentials."""


@dataclass
class OntDeviceInfo:
    """Static information about the ONT, fetched once."""

    serial_number: str | None
    model: str | None
    hostname: str | None
    firmware_version: str | None
    firmware_variant: str | None
    firmware_commit: str | None
    vendor: str | None
    hw_version: str | None


def parse_key_values(text: str) -> dict[str, str]:
    """Parse ``Key    : value`` lines from a pontop page."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        match = _KV_RE.match(line)
        if match and match["key"] and not match["key"].startswith("-"):
            result.setdefault(match["key"], match["value"])
    return result


def parse_float(value: str | None) -> float | None:
    """Return the first number in a string, or None."""
    if value is None:
        return None
    match = _NUM_RE.search(value)
    return float(match.group()) if match else None


def parse_int(value: str | None) -> int | None:
    """Return the first integer in a string, or None."""
    number = parse_float(value)
    return int(number) if number is not None else None


def parse_table(text: str) -> list[list[str]]:
    """Parse a whitespace separated pontop table into rows (header excluded)."""
    lines = [line for line in text.splitlines() if line.strip()]
    # First line is "Page: ...", second is the column header
    return [line.split() for line in lines[2:]]


def parse_alarms(text: str) -> list[dict[str, str]]:
    """Parse the active alarms page."""
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return []
    # Columns are fixed width; they start where a header word follows 2+ spaces
    starts = [0] + [m.end() for m in re.finditer(r" {2,}(?=\S)", lines[1])]
    alarms = []
    for line in lines[2:]:
        if len(starts) >= 3:
            alarm_col, desc_col = starts[1], starts[2]
            alarms.append(
                {
                    "type": line[:alarm_col].strip(),
                    "alarm": line[alarm_col:desc_col].strip(),
                    "description": line[desc_col:].strip(),
                }
            )
        else:
            alarms.append({"type": "", "alarm": line.strip(), "description": ""})
    return alarms


def parse_temperatures(value: str | None) -> list[float | None]:
    """Parse ``76.01 °C (168.8 °F) / 75.13 °C (...) / 65.48 °C (...)``."""
    if not value:
        return []
    return [parse_float(part) for part in value.split("/")]


class OntClient:
    """Minimal LuCI + ubus client."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._host = host
        self._username = username
        self._password = password or ""
        self._sysauth: str | None = None
        self._lock = asyncio.Lock()
        self._base = f"https://{host}"

    @property
    def host(self) -> str:
        """Return the host."""
        return self._host

    async def login(self) -> None:
        """Log in to LuCI and store the session cookie."""
        try:
            async with self._session.post(
                f"{self._base}/cgi-bin/luci/",
                data={
                    "luci_username": self._username,
                    "luci_password": self._password,
                },
                allow_redirects=False,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                cookie = resp.cookies.get("sysauth")
                if resp.status in (302, 200) and cookie and cookie.value:
                    self._sysauth = cookie.value
                    return
                if resp.status == 403:
                    raise OntAuthError("Invalid username or password")
                raise OntConnectionError(f"Unexpected login response {resp.status}")
        except (aiohttp.ClientError, TimeoutError) as err:
            raise OntConnectionError(f"Error connecting to {self._host}: {err}") from err

    async def _ensure_login(self) -> str:
        async with self._lock:
            if self._sysauth is None:
                await self.login()
            assert self._sysauth is not None
            return self._sysauth

    def _invalidate(self, sysauth: str) -> None:
        # Only drop the session if a concurrent request hasn't already replaced it
        if self._sysauth == sysauth:
            self._sysauth = None

    async def _get(self, path: str, *, retry: bool = True) -> aiohttp.ClientResponse:
        sysauth = await self._ensure_login()
        try:
            resp = await self._session.get(
                f"{self._base}/cgi-bin/luci/{path}",
                headers={"Cookie": f"sysauth={sysauth}"},
                allow_redirects=False,
                timeout=REQUEST_TIMEOUT,
            )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise OntConnectionError(f"Error fetching {path}: {err}") from err
        if resp.status == 403 or resp.headers.get("X-LuCI-Login-Required"):
            resp.release()
            if not retry:
                raise OntAuthError("Session rejected after re-login")
            self._invalidate(sysauth)
            return await self._get(path, retry=False)
        if resp.status != 200:
            resp.release()
            raise OntConnectionError(f"HTTP {resp.status} fetching {path}")
        return resp

    async def get_text(self, path: str) -> str:
        """GET a LuCI path and return text."""
        resp = await self._get(path)
        try:
            return await resp.text(errors="replace")
        except (aiohttp.ClientError, TimeoutError) as err:
            raise OntConnectionError(f"Error reading {path}: {err}") from err
        finally:
            resp.release()

    async def get_json(self, path: str) -> dict[str, Any]:
        """GET a LuCI path and decode JSON."""
        resp = await self._get(path)
        try:
            return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise OntConnectionError(f"Error reading {path}: {err}") from err
        finally:
            resp.release()

    async def ubus(
        self, obj: str, method: str, params: dict[str, Any] | None = None, *, retry: bool = True
    ) -> Any:
        """Call a ubus method using the LuCI session."""
        sysauth = await self._ensure_login()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call",
            "params": [sysauth, obj, method, params or {}],
        }
        try:
            async with self._session.post(
                f"{self._base}/ubus", json=payload, timeout=REQUEST_TIMEOUT
            ) as resp:
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise OntConnectionError(f"ubus {obj}.{method} failed: {err}") from err

        if "error" in data:
            # -32002 is "Access denied", which is what an expired session returns
            if data["error"].get("code") == -32002 and retry:
                self._invalidate(sysauth)
                return await self.ubus(obj, method, params, retry=False)
            raise OntError(f"ubus {obj}.{method} error: {data['error']}")
        result = data.get("result") or [None]
        if result[0] != 0:
            raise OntError(f"ubus {obj}.{method} returned status {result[0]}")
        return result[1] if len(result) > 1 else None

    async def pontop(self, page: str) -> str:
        """Return the text output of a pontop page."""
        return await self.get_text(f"admin/8311/pontop/{page}")

    async def get_device_info(self) -> OntDeviceInfo:
        """Fetch static device information."""
        optical_info, status_page = await asyncio.gather(
            self.pontop("optical_info"),
            self.get_text("admin/8311/pon_status"),
        )
        board: dict[str, Any] = {}
        try:
            board = await self.ubus("system", "board") or {}
        except OntError as err:
            _LOGGER.debug("Unable to read board info: %s", err)

        optical = parse_key_values(optical_info)
        firmware = _FIRMWARE_RE.search(status_page)

        return OntDeviceInfo(
            serial_number=optical.get("Serial number") or None,
            model=optical.get("Part number") or board.get("model"),
            hostname=board.get("hostname"),
            firmware_version=firmware["version"] if firmware else None,
            firmware_variant=firmware["variant"] if firmware else None,
            firmware_commit=firmware["commit"] if firmware else None,
            vendor=optical.get("Vendor name") or None,
            hw_version=board.get("model"),
        )

    async def get_data(self) -> dict[str, Any]:
        """Fetch and parse all polled data."""
        results = await asyncio.gather(
            self.get_json("admin/8311/gpon_status"),
            *(self.pontop(page) for page in PONTOP_PAGES),
            self.ubus("system", "info"),
        )
        gpon_status: dict[str, Any] = results[0]
        pages = dict(zip(PONTOP_PAGES, results[1:-1], strict=True))
        system_info: dict[str, Any] = results[-1] or {}

        optical = parse_key_values(pages["optical"])
        fec = parse_key_values(pages["fec"])
        gtc = parse_key_values(pages["gtc"])

        temps = parse_temperatures(gpon_status.get("temperature"))
        power = [parse_float(p) for p in (gpon_status.get("power") or "").split("/")]

        status = gpon_status.get("status") or ""
        ploam_state, _, ploam_desc = status.partition(",")

        gem_us_bytes = gem_ds_bytes = gem_us_packets = gem_ds_packets = 0
        for row in parse_table(pages["gem_stats"]):
            if len(row) >= 6 and row[0].isdigit():
                gem_us_packets += int(row[2])
                gem_us_bytes += int(row[3])
                gem_ds_packets += int(row[4])
                gem_ds_bytes += int(row[5])

        memory = system_info.get("memory") or {}
        mem_total = memory.get("total")
        mem_avail = memory.get("available", memory.get("free"))
        load = system_info.get("load") or []

        return {
            "ploam_state": ploam_state.strip() or None,
            "ploam_state_description": ploam_desc.strip() or None,
            "pon_mode": gpon_status.get("pon_mode"),
            "eth_speed": parse_int(gpon_status.get("eth_speed")),
            "active_bank": gpon_status.get("active_bank"),
            "module_info": gpon_status.get("module_info"),
            "cpu1_temperature": temps[0] if len(temps) > 0 else None,
            "cpu2_temperature": temps[1] if len(temps) > 1 else None,
            "optic_temperature": temps[2] if len(temps) > 2 else None,
            "rx_power": parse_float(optical.get("Receive power"))
            if "Receive power" in optical
            else (power[0] if power else None),
            "tx_power": parse_float(optical.get("Transmit power"))
            if "Transmit power" in optical
            else (power[1] if len(power) > 1 else None),
            "tx_bias": parse_float(optical.get("Transmit bias current"))
            if "Transmit bias current" in optical
            else (power[2] if len(power) > 2 else None),
            "voltage": parse_float(optical.get("Transceiver supply voltage"))
            or parse_float(gpon_status.get("voltage")),
            "receiver_status": optical.get("Receiver status"),
            "transmitter_status": optical.get("Transmitter status"),
            "bip_errors": parse_int(fec.get("BIP errors")),
            "fec_codewords_total": parse_int(fec.get("Total FEC codewords")),
            "fec_codewords_corrected": parse_int(fec.get("Corrected FEC codewords")),
            "fec_codewords_uncorrected": parse_int(fec.get("Uncorrected FEC codewords")),
            "fec_bytes_corrected": parse_int(fec.get("Corrected FEC bytes")),
            "fec_errored_seconds": parse_int(fec.get("FEC errored seconds")),
            "psbd_hec_errors_uncorrected": parse_int(gtc.get("PSBd HEC errors uncorrected")),
            "fs_hec_errors_uncorrected": parse_int(gtc.get("FS HEC errors uncorrected")),
            "hec_lost_words": parse_int(gtc.get("Lost words due to HEC errors")),
            "ploam_mic_errors": parse_int(gtc.get("PLOAM MIC errors")),
            "alarms": parse_alarms(pages["alarms"]),
            "upstream_bytes": gem_us_bytes,
            "downstream_bytes": gem_ds_bytes,
            "upstream_packets": gem_us_packets,
            "downstream_packets": gem_ds_packets,
            "uptime": system_info.get("uptime"),
            "memory_usage": round((1 - mem_avail / mem_total) * 100, 1)
            if mem_total and mem_avail is not None
            else None,
            "load_1m": round(load[0] / 65536, 2) if load else None,
            "load_5m": round(load[1] / 65536, 2) if len(load) > 1 else None,
        }

    async def reboot(self) -> None:
        """Reboot the ONT."""
        await self.ubus("file", "exec", {"command": "/sbin/reboot"})
