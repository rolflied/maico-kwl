"""One serialized, self-healing Modbus TCP connection to the unit.

The unit serves a single TCP connection and answers slowly, so everything goes
through one pymodbus client behind a lock. Nothing here blocks the event loop.

A dead connection is closed and rebuilt. After a failed connect or request the
next attempt waits 5, 15, 30, then 60 seconds, so a unit that is down or
rebooting is not hammered on every poll.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import time

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

_LOGGER = logging.getLogger(__name__)

TIMEOUT = 3
RETRIES = 1
BACKOFF_SECONDS: tuple[int, ...] = (5, 15, 30, 60)

# Modbus exception codes meaning "this unit does not have that".
ILLEGAL_FUNCTION = 1
ILLEGAL_DATA_ADDRESS = 2


class MaicoModbusError(Exception):
    """Base class of all errors raised by the client."""


class MaicoConnectionError(MaicoModbusError):
    """The unit cannot be reached, or did not answer in time."""


class MaicoModbusException(MaicoModbusError):
    """The unit answered with a Modbus exception response."""

    def __init__(self, code: int) -> None:
        """Initialize the error."""
        super().__init__(f"Modbus exception {code}")
        self.code = code

    @property
    def unsupported(self) -> bool:
        """The unit lacks the function or the registers (permanent)."""
        return self.code in (ILLEGAL_FUNCTION, ILLEGAL_DATA_ADDRESS)


class MaicoModbusClient:
    """Lock-serialized access to one unit with connection management."""

    def __init__(
        self,
        host: str,
        port: int,
        unit_id: int,
        *,
        timeout: float = TIMEOUT,
        retries: int = RETRIES,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialize the client; nothing connects before the first request."""
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self._timeout = timeout
        self._retries = retries
        self._monotonic = monotonic
        self._client: AsyncModbusTcpClient | None = None
        self._lock = asyncio.Lock()
        self._failures = 0
        self._retry_at = 0.0

    @property
    def connected(self) -> bool:
        """The TCP connection is up."""
        return self._client is not None and self._client.connected

    @property
    def failures(self) -> int:
        """Consecutive failed connects or requests."""
        return self._failures

    async def read_holding_registers(self, address: int, count: int) -> list[int]:
        """Read holding registers (FC 3)."""
        response = await self._request("read_holding_registers", address, count=count)
        return list(response.registers[:count])

    async def write_registers(self, address: int, values: list[int]) -> None:
        """Write registers with FC 16, the only write the unit accepts over TCP."""
        await self._request("write_registers", address, values=values)

    async def async_close(self) -> None:
        """Close the connection."""
        async with self._lock:
            self._discard()

    def _discard(self) -> None:
        """Close and forget the client; the next request builds a new one."""
        client, self._client = self._client, None
        if client is not None:
            client.close()

    def _fail(self) -> None:
        """Count a failure and schedule the next attempt."""
        self._discard()
        delay = BACKOFF_SECONDS[min(self._failures, len(BACKOFF_SECONDS) - 1)]
        self._failures += 1
        self._retry_at = self._monotonic() + delay

    async def _ensure_connected(self) -> AsyncModbusTcpClient:
        if self._client is not None and self._client.connected:
            return self._client
        if (wait := self._retry_at - self._monotonic()) > 0:
            raise MaicoConnectionError(f"not connected, next attempt in {wait:.0f} s")
        # Build a fresh client: a half-dead one keeps answering "not connected".
        self._discard()
        # reconnect_delay=0: pymodbus must not reconnect on its own.
        client = AsyncModbusTcpClient(
            self.host,
            port=self.port,
            timeout=self._timeout,
            retries=self._retries,
            reconnect_delay=0,
        )
        try:
            connected = await client.connect()
        except (ModbusException, OSError, TimeoutError) as err:
            client.close()
            self._fail()
            raise MaicoConnectionError(f"cannot connect to {self.host}:{self.port}: {err}") from err
        if not connected:
            client.close()
            self._fail()
            raise MaicoConnectionError(f"cannot connect to {self.host}:{self.port}")
        self._client = client
        return client

    async def _request(self, method: str, address: int, **kwargs: object):
        async with self._lock:
            client = await self._ensure_connected()
            try:
                # pymodbus has its own timeout and retries; this one only
                # guarantees that a stuck transport cannot hold the lock.
                async with asyncio.timeout(self._timeout * (self._retries + 1) + 2):
                    response = await getattr(client, method)(
                        address, device_id=self.unit_id, **kwargs
                    )
            except (ModbusException, OSError, TimeoutError) as err:
                self._fail()
                raise MaicoConnectionError(str(err) or type(err).__name__) from err
            if response.isError():
                if (code := getattr(response, "exception_code", None)) is not None:
                    # The unit is alive and answered: not a connection problem.
                    self._failures = 0
                    raise MaicoModbusException(code)
                self._fail()
                raise MaicoConnectionError(str(response))
            self._failures = 0
            return response
