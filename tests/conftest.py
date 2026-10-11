"""Fixtures for the Maico KWL tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.maico_kwl.const import CONF_SCAN_INTERVAL, CONF_SLAVE, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

# A unit as seen in the field: manual mode, nominal level, one CO2 sensor,
# no outdoor/room filter.
REGISTERS: dict[int, int] = {
    100: 2026,
    101: 10,
    102: 11,
    103: 14,
    104: 30,
    105: 0,
    106: 0,
    107: 0,
    108: 0,
    109: 2,
    150: 6,
    151: 12,
    152: 3,
    153: 30,
    154: 120,
    155: 160,
    156: 220,
    300: 0xFFFE,
    301: 14,
    302: 260,
    401: 0,
    402: 0,
    403: 0,
    404: 1 << 9,
    550: 1,
    551: 0,
    552: 0,
    553: 215,
    554: 3,
    650: 3,
    651: 1239,
    652: 822,
    653: 160,
    654: 158,
    655: 178,
    656: 0,
    657: 0,
    700: 215,
    701: 0,
    702: 0,
    703: 0xFFCE,
    704: 170,
    705: 220,
    706: 10,
    750: 54,
    751: 0,
    752: 0,
    753: 0,
    754: 0,
    755: 548,
    756: 0,
    757: 0,
    758: 0,
    800: 1,
    801: 1,
    802: 0,
    803: 0,
    804: 0,
    805: 0,
    806: 0,
    807: 0,
    808: 0,
    850: 0,
    851: 10,
    852: 0,
    853: 2000,
    854: 1,
    855: 5,
    856: 0,
    857: 300,
    858: 1,
    859: 2315,
    900: 50,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations."""


@pytest.fixture
def mock_unit() -> MockModbusUnit:
    """A Maico KWL in memory."""
    unit = MockModbusConnection().for_unit(10)
    unit.holding.update(REGISTERS)
    return unit


@pytest.fixture
def patch_unit(mock_unit: MockModbusUnit) -> Generator[MockModbusUnit]:
    """Hand the mock unit to the integration instead of a real connection."""
    with patch("custom_components.maico_kwl.async_get_unit", return_value=mock_unit):
        yield mock_unit


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A current config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=2,
        unique_id="192.168.1.50_502_10",
        data={CONF_HOST: "192.168.1.50", CONF_PORT: 502, CONF_SLAVE: 10},
        options={CONF_SCAN_INTERVAL: 30},
    )
