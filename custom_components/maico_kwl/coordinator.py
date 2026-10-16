"""DataUpdateCoordinator for the Maico KWL integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .client import (
    MaicoModbusClient,
    MaicoModbusError,
    MaicoModbusException,
)
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DOMAIN,
    MANUFACTURER,
)
from .registers import (
    FAULT_BITS,
    NOTICE_BITS,
    READ_GROUPS,
    REG_FAULT,
    REG_NOTICE,
    U32,
    active_bits,
    identity_problem,
    read_value,
)

if TYPE_CHECKING:
    from .bus import MaicoBusFeeder

_LOGGER = logging.getLogger(__name__)

type MaicoKWLConfigEntry = ConfigEntry[MaicoKWLCoordinator]

# Failed poll cycles in a row before the entities become unavailable.
FAILED_CYCLES_UNTIL_UNAVAILABLE = 3

# Notice bits that ask for a filter change, with the filter they name.
FILTER_DUE_BITS: dict[str, str] = {
    "device_filter_due": "device",
    "outdoor_filter_due": "outdoor",
    "room_filter_due": "room",
}


class MaicoKWLCoordinator(DataUpdateCoordinator[dict[int, int]]):
    """Polls the unit and writes to it over its own serialized Modbus connection."""

    config_entry: MaicoKWLConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MaicoKWLConfigEntry,
        client: MaicoModbusClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        # Consecutive poll cycles that failed; entities keep their last value
        # until FAILED_CYCLES_UNTIL_UNAVAILABLE of them failed.
        self.failed_cycles = 0
        self.offline = False
        self.unit_id: int = entry.data.get(CONF_SLAVE, DEFAULT_SLAVE)
        # Blocks the unit rejected with a Modbus exception (not fitted / not in
        # this firmware). They are not asked for again until the entry reloads.
        self.unsupported_blocks: set[tuple[int, int]] = set()
        # When the clock registers were read, to compare them with HA's time.
        self.last_read: datetime | None = None
        # Last value written to each write-only bus input (address -> value).
        self.bus_values: dict[int, float] = {}
        # Set up in async_setup_entry once the first poll succeeded.
        self.bus: MaicoBusFeeder
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=DEFAULT_NAME,
            manufacturer=MANUFACTURER,
            model="KWL WS/WR",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    async def _async_update_data(self) -> dict[int, int]:
        """Read all register blocks in as few requests as possible.

        A communication problem ends the cycle at once. The last values stay and
        the cycle counts as one failure.
        """
        data: dict[int, int] = {}
        try:
            for _, blocks in READ_GROUPS:
                if blocks := tuple(b for b in blocks if b not in self.unsupported_blocks):
                    data.update(await self._async_read_blocks(blocks))
        except MaicoModbusError as err:
            return self._cycle_failed(err)

        if problem := identity_problem(data):
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="not_maico",
                translation_placeholders={"problem": problem},
            )

        self._cycle_succeeded()
        self.last_read = dt_util.utcnow()
        self._update_issues(data)
        return data

    async def _async_read_blocks(self, blocks: tuple[tuple[int, int], ...]) -> dict[int, int]:
        """Read neighbouring blocks in one request; keep only the registers of the blocks."""
        start = blocks[0][0]
        count = blocks[-1][0] + blocks[-1][1] - start
        try:
            words = await self.client.read_holding_registers(start, count)
        except MaicoModbusException as err:
            if not err.unsupported:
                raise
            if len(blocks) == 1:
                self._block_unsupported(blocks[0], err)
                return {}
            # A gap or one of the blocks is missing on this unit: ask block by block.
            _LOGGER.debug("Read of %d+%d rejected (%s), reading its blocks", start, count, err)
            result: dict[int, int] = {}
            for block in blocks:
                result.update(await self._async_read_blocks((block,)))
            return result
        return {
            address: words[address - start]
            for block_start, block_count in blocks
            for address in range(block_start, block_start + block_count)
        }

    def _block_unsupported(self, block: tuple[int, int], err: Exception) -> None:
        # The unit answered, but does not have these registers. Other
        # exceptions (busy, device failure) are temporary.
        _LOGGER.info(
            "Registers %d-%d are not available on this unit (%s), skipping them",
            block[0],
            block[0] + block[1] - 1,
            err,
        )
        self.unsupported_blocks.add(block)

    def _cycle_failed(self, err: Exception) -> dict[int, int]:
        """Count a failed cycle; keep the last values until it is clear the unit is gone."""
        if self.data is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
        self.failed_cycles += 1
        if self.failed_cycles == 1:
            _LOGGER.warning(
                "Maico KWL does not answer (%s); keeping the last values and retrying", err
            )
        else:
            _LOGGER.debug("Poll cycle %d failed: %s", self.failed_cycles, err)
        if self.failed_cycles >= FAILED_CYCLES_UNTIL_UNAVAILABLE:
            self.offline = True
        return self.data

    def _cycle_succeeded(self) -> None:
        if self.failed_cycles:
            _LOGGER.info("Maico KWL answers again after %d failed polls", self.failed_cycles)
        self.failed_cycles = 0
        self.offline = False

    async def async_write(self, address: int, values: list[int]) -> None:
        """Write registers with FC 16, the only write the unit accepts over TCP."""
        try:
            await self.client.write_registers(address, values)
        except MaicoModbusError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="write_failed",
                translation_placeholders={"address": str(address), "error": str(err)},
            ) from err
        # Show the new value right away, then read back what the unit made of it
        # (e.g. the current level after a new setpoint).
        if self.data is not None and address in self.data:
            new = dict(self.data)
            new.update(zip(range(address, address + len(values)), values, strict=False))
            self.async_set_updated_data(new)
            await self.async_request_refresh()

    async def async_write_register(self, address: int, value: int) -> None:
        """Write a single register."""
        await self.async_write(address, [value & 0xFFFF])

    def _update_issues(self, data: dict[int, int]) -> None:
        """Raise or clear repair issues for faults and due filters."""
        entry_id = self.config_entry.entry_id

        faults = read_value(data, REG_FAULT, U32)
        fault_issue = f"fault_{entry_id}"
        if faults:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                fault_issue,
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="fault_active",
                translation_placeholders={
                    "faults": ", ".join(active_bits(int(faults), FAULT_BITS)),
                    "code": str(faults),
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, fault_issue)

        notices = read_value(data, REG_NOTICE, U32)
        due = set(active_bits(int(notices), NOTICE_BITS)) if notices is not None else set()
        for bit, filter_name in FILTER_DUE_BITS.items():
            issue_id = f"filter_due_{filter_name}_{entry_id}"
            if bit in due:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key=f"{filter_name}_filter_due",
                )
            else:
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)
