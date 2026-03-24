"""DataUpdateCoordinator für die Maico KWL Integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, REGISTER_BLOCKS

_LOGGER = logging.getLogger(__name__)


def to_int16(value: int) -> int:
    """Konvertiert einen vorzeichenlosen 16-Bit-Wert in einen vorzeichenbehafteten."""
    if value > 32767:
        return value - 65536
    return value


def to_uint16(value: int) -> int:
    """Konvertiert einen vorzeichenbehafteten Wert in eine vorzeichenlose 16-Bit-Darstellung."""
    if value < 0:
        return value & 0xFFFF
    return value


def combine_32bit(high: int, low: int) -> int:
    """Kombiniert zwei 16-Bit-Register zu einem 32-Bit-Wert."""
    return (high << 16) | low


class MaicoKWLCoordinator(DataUpdateCoordinator[dict[int, int]]):
    """Koordinator für die Maico KWL Modbus-Kommunikation."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave: int,
        scan_interval: int,
    ) -> None:
        """Initialisierung des Koordinators."""
        self.host = host
        self.port = port
        self.slave = slave
        self._client: AsyncModbusTcpClient | None = None
        # None = noch nicht ermittelt, wird beim ersten verbundenen Aufruf gesetzt
        self._slave_kwargs: dict | None = None

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def async_setup(self) -> None:
        """Erstellt den Modbus-Client (Verbindung beim ersten Update)."""
        self._client = AsyncModbusTcpClient(
            host=self.host,
            port=self.port,
        )

    async def async_shutdown(self) -> None:
        """Trennt die Modbus-Verbindung."""
        if self._client:
            if self._client.connected:
                await self._client.close()
            self._client = None

    async def _ensure_connected(self) -> bool:
        """Stellt sicher, dass der Client verbunden ist."""
        if not self._client:
            return False
        if not self._client.connected:
            _LOGGER.debug(
                "Modbus nicht verbunden – versuche Neuverbindung zu %s:%d",
                self.host,
                self.port,
            )
            return await self._client.connect()
        return True

    async def _detect_slave_kwargs(self) -> dict:
        """Ermittelt durch Ausprobieren welchen Kwarg diese pymodbus-Version unterstützt.

        Reihenfolge: slave= → unit= → kein Kwarg
        TypeError bedeutet: dieser Kwarg-Name ist nicht gültig → nächste Option.
        Andere Exceptions bedeuten: Kwarg-Name ist akzeptiert, aber Kommunikationsproblem.
        """
        for candidate in ({"slave": self.slave}, {"unit": self.slave}, {}):
            try:
                await self._client.read_holding_registers(
                    address=550, count=1, **candidate
                )
                # Kein TypeError → dieser Kwarg wird akzeptiert
                key = next(iter(candidate), None)
                if key:
                    _LOGGER.debug("pymodbus: Slave-Kwarg '%s=' erkannt und gecacht", key)
                else:
                    _LOGGER.warning(
                        "pymodbus: weder 'slave' noch 'unit' wird akzeptiert. "
                        "Slave-ID %d kann nicht per Request übermittelt werden.",
                        self.slave,
                    )
                return candidate
            except TypeError:
                key = next(iter(candidate), None)
                _LOGGER.debug(
                    "pymodbus: Kwarg '%s=' nicht unterstützt – versuche nächste Option",
                    key,
                )
            except Exception:
                # Anderer Fehler (Modbus, Netzwerk): Kwarg-Name ist korrekt,
                # Kommunikationsfehler wird im normalen Update-Zyklus behandelt
                key = next(iter(candidate), None)
                if key:
                    _LOGGER.debug(
                        "pymodbus: Kwarg '%s=' akzeptiert (Kommunikationsfehler ignoriert)",
                        key,
                    )
                return candidate

        return {}

    async def _async_update_data(self) -> dict[int, int]:
        """Liest alle konfigurierten Modbus-Register aus."""
        if not self._client:
            raise UpdateFailed("Kein Modbus-Client verfügbar")

        if not await self._ensure_connected():
            raise UpdateFailed(
                f"Verbindung zu {self.host}:{self.port} fehlgeschlagen"
            )

        # Slave-Kwarg beim ersten erfolgreichen Verbindungsaufbau einmalig ermitteln
        if self._slave_kwargs is None:
            self._slave_kwargs = await self._detect_slave_kwargs()

        data: dict[int, int] = {}

        try:
            for start, count in REGISTER_BLOCKS:
                result = await self._client.read_holding_registers(
                    address=start,
                    count=count,
                    **self._slave_kwargs,
                )
                if result.isError():
                    _LOGGER.warning(
                        "Fehler beim Lesen der Register %d–%d: %s",
                        start,
                        start + count - 1,
                        result,
                    )
                    continue

                for i, value in enumerate(result.registers):
                    data[start + i] = value

        except ModbusException as err:
            raise UpdateFailed(f"Modbus-Kommunikationsfehler: {err}") from err

        return data

    async def async_write_register(self, address: int, value: int) -> bool:
        """Schreibt einen einzelnen Modbus-Register-Wert."""
        if not self._client:
            _LOGGER.error("Schreiben nicht möglich – kein Modbus-Client")
            return False

        if not await self._ensure_connected():
            _LOGGER.error(
                "Schreiben nicht möglich – Verbindung zu %s:%d fehlgeschlagen",
                self.host,
                self.port,
            )
            return False

        # Slave-Kwargs müssen vor dem ersten Schreiben bekannt sein
        if self._slave_kwargs is None:
            self._slave_kwargs = await self._detect_slave_kwargs()

        try:
            result = await self._client.write_register(
                address=address,
                value=to_uint16(value),
                **self._slave_kwargs,
            )
            if result.isError():
                _LOGGER.error(
                    "Fehler beim Schreiben in Register %d (Wert %d): %s",
                    address,
                    value,
                    result,
                )
                return False
            return True
        except ModbusException as err:
            _LOGGER.error("Modbus-Schreibfehler bei Register %d: %s", address, err)
            return False
