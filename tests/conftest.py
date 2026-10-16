"""Fixtures for the Maico KWL tests."""

from __future__ import annotations

from collections.abc import Callable, Generator
from dataclasses import dataclass
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.maico_kwl.client import MaicoModbusException
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


@dataclass
class WriteEvent:
    """One write that reached the fake unit."""

    address: int
    values: list[int]
    function_code: int = 0x10


class FakeUnit:
    """A Maico KWL in memory, with the interface of MaicoModbusClient."""

    def __init__(self) -> None:
        self.holding: dict[int, int] = dict(REGISTERS)
        self.connected = True
        self.reads: list[tuple[int, int]] = []
        self._read_errors: dict[int, Exception] = {}
        self._write_errors: dict[int, Exception] = {}
        self._request_error: Exception | None = None
        self._write_listeners: list[Callable[[WriteEvent], None]] = []

    def fail_read(self, address: int, error: Exception | None) -> None:
        """Fail reads that cover the address (None clears it)."""
        if error is None:
            self._read_errors.pop(address, None)
        else:
            self._read_errors[address] = error

    def fail_write(self, address: int, error: Exception) -> None:
        """Fail writes to the address."""
        self._write_errors[address] = error

    def fail_requests(self, error: Exception | None) -> None:
        """Fail every request (None clears it)."""
        self._request_error = error

    def on_write(self, listener: Callable[[WriteEvent], None]) -> None:
        """Call the listener for every write."""
        self._write_listeners.append(listener)

    async def read_holding_registers(self, address: int, count: int) -> list[int]:
        """Read registers; unknown ones are rejected like the real unit does."""
        self.reads.append((address, count))
        if self._request_error is not None:
            raise self._request_error
        for failing, error in self._read_errors.items():
            if address <= failing < address + count:
                raise error
        return [self.holding.get(a, 0) for a in range(address, address + count)]

    async def write_registers(self, address: int, values: list[int]) -> None:
        """Write registers."""
        if self._request_error is not None:
            raise self._request_error
        if address in self._write_errors:
            raise self._write_errors[address]
        event = WriteEvent(address, list(values))
        for listener in self._write_listeners:
            listener(event)
        self.holding.update(zip(range(address, address + len(values)), values, strict=False))

    async def async_close(self) -> None:
        """Nothing to close."""


def busy() -> MaicoModbusException:
    """Modbus exception 6: server device busy."""
    return MaicoModbusException(6)


def illegal_address() -> MaicoModbusException:
    """Modbus exception 2: illegal data address."""
    return MaicoModbusException(2)


@pytest.fixture
def mock_unit() -> FakeUnit:
    """A Maico KWL in memory."""
    return FakeUnit()


@pytest.fixture
def patch_unit(mock_unit: FakeUnit) -> Generator[FakeUnit]:
    """Hand the fake unit to the integration instead of a real connection."""
    with patch("custom_components.maico_kwl.MaicoModbusClient", return_value=mock_unit):
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
