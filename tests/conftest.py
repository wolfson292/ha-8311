"""Fixtures for 8311 ONT tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.ont_8311.api import OntClient

FIXTURES = Path(__file__).parent / "fixtures"

SYSTEM_INFO = {
    "uptime": 977194,
    "load": [41216, 30272, 22144],
    "memory": {"total": 1022644224, "free": 427298816, "available": 411504640},
}
BOARD = {"hostname": "prx126-sfp-pon", "model": "PRX126-SFP-PON"}


def load(name: str) -> str:
    """Load a fixture file."""
    return (FIXTURES / name).read_text()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    return


async def _pontop(self, page: str) -> str:
    return load(f"pontop_{page}.txt")


async def _get_text(self, path: str) -> str:
    return load("footer.html")


async def _get_json(self, path: str) -> dict:
    return json.loads(load("gpon_status.json"))


async def _ubus(self, obj: str, method: str, params=None, *, retry=True):
    return {"info": SYSTEM_INFO, "board": BOARD}[method]


@pytest.fixture
def mock_ont():
    """Patch the ONT client to serve fixture data."""
    with (
        patch.object(OntClient, "login", AsyncMock()) as login,
        patch.object(OntClient, "pontop", _pontop),
        patch.object(OntClient, "get_text", _get_text),
        patch.object(OntClient, "get_json", _get_json),
        patch.object(OntClient, "ubus", _ubus),
    ):
        yield login
