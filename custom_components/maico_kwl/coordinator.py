"""DataUpdateCoordinator for the Maico KWL integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING

from modbus_connection import (
    IllegalDataAddressError,
    IllegalFunctionError,
    ModbusError,
    ModbusUnit,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

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
    READ_BLOCKS,
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

# Notice bits that ask for a filter change, with the filter they name.
FILTER_DUE_BITS: dict[str, str] = {
    "device_filter_due": "device",
    "outdoor_filter_due": "outdoor",
    "room_filter_due": "room",
}


class MaicoKWLCoordinator(DataUpdateCoordinator[dict[int, int]]):
    """Polls the unit and writes to it over a shared Modbus connection."""

    config_entry: MaicoKWLConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MaicoKWLConfigEntry,
        unit: ModbusUnit,
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
        self.unit = unit
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
        """Read all register blocks."""
        data: dict[int, int] = {}
        for block in READ_BLOCKS:
            if block in self.unsupported_blocks:
                continue
            start, count = block
            try:
                words = await self.unit.read_holding_registers(start, count)
            except (IllegalDataAddressError, IllegalFunctionError) as err:
                # The unit answered, but does not have these registers. Other
                # exceptions (busy, device failure) are temporary.
                _LOGGER.info(
                    "Registers %d-%d are not available on this unit (%s), skipping them",
                    start,
                    start + count - 1,
                    err,
                )
                self.unsupported_blocks.add(block)
                continue
            except ModbusError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="communication_error",
                    translation_placeholders={"error": str(err)},
                ) from err
            data.update(zip(range(start, start + count), words, strict=False))

        if problem := identity_problem(data):
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="not_maico",
                translation_placeholders={"problem": problem},
            )

        self.last_read = dt_util.utcnow()
        self._update_issues(data)
        return data

    async def async_write(self, address: int, values: list[int]) -> None:
        """Write registers with FC 16, the only write the unit accepts over TCP."""
        try:
            await self.unit.write_registers(address, values)
        except ModbusError as err:
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
