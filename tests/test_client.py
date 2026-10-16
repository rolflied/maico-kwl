"""Tests for the Modbus client against a real (local) TCP server."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
import struct

import pytest

from custom_components.maico_kwl.client import (
    BACKOFF_SECONDS,
    MaicoConnectionError,
    MaicoModbusClient,
    MaicoModbusException,
)


class FakeServer:
    """A minimal Modbus TCP server that can drop or ignore requests."""

    def __init__(self) -> None:
        self.mode = "normal"  # normal | close | silent | exception
        self.connections = 0
        self.requests = 0
        self.writes: list[tuple[int, list[int]]] = []
        self.port = 0
        self._server: asyncio.Server | None = None
        self._writers: list[asyncio.StreamWriter] = []

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        for writer in self._writers:
            writer.close()
        assert self._server is not None
        self._server.close()
        await self._server.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.connections += 1
        self._writers.append(writer)
        try:
            while True:
                header = await reader.readexactly(7)
                tid, _, length, unit = struct.unpack(">HHHB", header)
                pdu = await reader.readexactly(length - 1)
                self.requests += 1
                if self.mode == "close":
                    writer.close()
                    return
                if self.mode == "silent":
                    continue
                function = pdu[0]
                if self.mode == "exception":
                    body = bytes([function | 0x80, 2])
                elif function == 3:
                    address, count = struct.unpack(">HH", pdu[1:5])
                    registers = b"".join(struct.pack(">H", address + i) for i in range(count))
                    body = bytes([function, len(registers)]) + registers
                elif function == 16:
                    address, count, _ = struct.unpack(">HHB", pdu[1:6])
                    values = list(struct.unpack(f">{count}H", pdu[6 : 6 + 2 * count]))
                    self.writes.append((address, values))
                    body = pdu[:5]
                else:
                    body = bytes([function | 0x80, 1])
                writer.write(struct.pack(">HHHB", tid, 0, len(body) + 1, unit) + body)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            return


@pytest.fixture
async def server(socket_enabled: None) -> AsyncGenerator[FakeServer]:
    srv = FakeServer()
    await srv.start()
    yield srv
    await srv.stop()


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def test_read_and_write(server: FakeServer) -> None:
    """Reads and writes work over one connection."""
    client = MaicoModbusClient("127.0.0.1", server.port, 10)
    assert not client.connected
    assert await client.read_holding_registers(100, 3) == [100, 101, 102]
    assert client.connected
    await client.write_registers(764, [550])
    assert server.writes == [(764, [550])]
    assert server.connections == 1
    await client.async_close()
    assert not client.connected


async def test_requests_never_overlap(server: FakeServer) -> None:
    """Parallel callers share one connection and are served one after the other."""
    client = MaicoModbusClient("127.0.0.1", server.port, 10)
    results = await asyncio.gather(*(client.read_holding_registers(a, 2) for a in (1, 10, 20)))
    assert results == [[1, 2], [10, 11], [20, 21]]
    assert server.connections == 1
    await client.async_close()


async def test_exception_response_keeps_connection(server: FakeServer) -> None:
    """A Modbus exception is an answer: no reconnect, no backoff."""
    client = MaicoModbusClient("127.0.0.1", server.port, 10)
    server.mode = "exception"
    with pytest.raises(MaicoModbusException) as err:
        await client.read_holding_registers(100, 1)
    assert err.value.unsupported
    assert client.connected
    assert client.failures == 0
    await client.async_close()


async def test_server_closes_connection(server: FakeServer) -> None:
    """After the unit hangs up the client reconnects by itself, without errors piling up."""
    client = MaicoModbusClient("127.0.0.1", server.port, 10, timeout=0.5)
    assert await client.read_holding_registers(100, 1) == [100]

    server.mode = "close"
    with pytest.raises(MaicoConnectionError):
        await client.read_holding_registers(100, 1)
    assert not client.connected
    assert client.failures == 1

    server.mode = "normal"
    # Inside the backoff window nothing touches the network.
    requests = server.requests
    connections = server.connections
    for _ in range(20):
        with pytest.raises(MaicoConnectionError, match="next attempt"):
            await client.read_holding_registers(100, 1)
    assert (server.requests, server.connections) == (requests, connections)
    await client.async_close()


async def test_reconnects_after_backoff(server: FakeServer) -> None:
    """After the waiting time the client builds a new connection and carries on."""
    clock = Clock()
    client = MaicoModbusClient(
        "127.0.0.1", server.port, 10, timeout=0.3, retries=0, monotonic=clock
    )
    assert await client.read_holding_registers(100, 1) == [100]

    server.mode = "silent"  # connection stays up, but the answer never comes
    with pytest.raises(MaicoConnectionError):
        await client.read_holding_registers(100, 1)
    assert not client.connected

    server.mode = "normal"
    clock.now += BACKOFF_SECONDS[0] - 1
    with pytest.raises(MaicoConnectionError, match="next attempt"):
        await client.read_holding_registers(100, 1)
    assert server.connections == 1

    clock.now += 2
    assert await client.read_holding_registers(100, 2) == [100, 101]
    assert server.connections == 2
    assert client.failures == 0
    await client.async_close()


async def test_backoff_grows(server: FakeServer) -> None:
    """Waiting times: 5, 15, 30, 60, 60 seconds."""
    clock = Clock()
    await server.stop()  # nothing listens any more
    client = MaicoModbusClient(
        "127.0.0.1", server.port, 10, timeout=0.3, retries=0, monotonic=clock
    )
    waits = []
    for _ in range(5):
        with pytest.raises(MaicoConnectionError, match="cannot connect"):
            await client.read_holding_registers(100, 1)
        waits.append(round(client._retry_at - clock.now))
        clock.now = client._retry_at + 0.1
    assert waits == [5, 15, 30, 60, 60]
    await client.async_close()
    await server.start()  # for the fixture teardown


async def test_idle_hangup_reconnects_at_once(server: FakeServer) -> None:
    """If the unit closed an idle connection, the next request just reconnects."""
    client = MaicoModbusClient("127.0.0.1", server.port, 10)
    assert await client.read_holding_registers(100, 1) == [100]
    for writer in server._writers:
        writer.close()
    await asyncio.sleep(0.1)
    assert not client.connected

    assert await client.read_holding_registers(100, 1) == [100]
    assert server.connections == 2
    assert client.failures == 0
    await client.async_close()
