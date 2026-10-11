"""Diagnostics for the Maico KWL integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import registers as r
from .coordinator import MaicoKWLConfigEntry

TO_REDACT = {CONF_HOST, "unique_id", "title"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MaicoKWLConfigEntry
) -> dict[str, Any]:
    """Return diagnostics: raw registers and decoded status words."""
    coordinator = entry.runtime_data
    data = coordinator.data or {}
    faults = r.read_value(data, r.REG_FAULT, r.U32)
    notices = r.read_value(data, r.REG_NOTICE, r.U32)
    clock = r.decode_clock(data)
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "unit_id": coordinator.unit_id,
        "connected": coordinator.unit.connected,
        "unsupported_blocks": sorted(coordinator.unsupported_blocks),
        "registers": {str(address): value for address, value in sorted(data.items())},
        "faults": r.active_bits(int(faults), r.FAULT_BITS) if faults is not None else None,
        "notices": r.active_bits(int(notices), r.NOTICE_BITS) if notices is not None else None,
        "device_clock": clock.isoformat() if clock else None,
        "bus_values": {str(k): v for k, v in coordinator.bus_values.items()},
    }
