"""Fan entity for the Maico KWL integration.

Speeds are the ventilation levels 1-4 (humidity protection, reduced, nominal,
intensive), presets are the operating modes. Setting a speed switches to the
manual mode, as the unit only follows the level setpoint (554) there.
Turning off sets the operating mode "off"; turning on restores the last mode.
"""

from __future__ import annotations

import math
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityDescription, FanEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import registers as r
from .coordinator import MaicoKWLConfigEntry, MaicoKWLCoordinator
from .entity import MaicoEntity

PARALLEL_UPDATES = 1

SPEED_RANGE = (1, 4)
MODE_OFF = 0
MODE_MANUAL = 1
PRESET_MODES = [slug for raw, slug in r.OPERATING_MODES.items() if raw != MODE_OFF]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaicoKWLConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the fan entity."""
    async_add_entities([MaicoFan(entry.runtime_data)])


class MaicoFan(MaicoEntity, FanEntity):
    """The ventilation unit as a fan."""

    _attr_name = None
    _attr_translation_key = "ventilation"
    _attr_preset_modes = PRESET_MODES
    _attr_speed_count = SPEED_RANGE[1] - SPEED_RANGE[0] + 1
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: MaicoKWLCoordinator) -> None:
        """Initialize the fan."""
        super().__init__(
            coordinator,
            FanEntityDescription(key="ventilation", translation_key="ventilation"),
            (r.REG_OPERATING_MODE, r.REG_CURRENT_VENTILATION_LEVEL),
        )
        self._last_mode = MODE_MANUAL
        self._remember_mode()

    def _remember_mode(self) -> None:
        if (
            self.coordinator.data
            and (mode := self.coordinator.data.get(r.REG_OPERATING_MODE, MODE_OFF))
            in r.OPERATING_MODES
            and mode != MODE_OFF
        ):
            self._last_mode = mode

    @callback
    def _handle_coordinator_update(self) -> None:
        self._remember_mode()
        super()._handle_coordinator_update()

    @property
    def _mode(self) -> int | None:
        return self.coordinator.data.get(r.REG_OPERATING_MODE)

    @property
    def is_on(self) -> bool | None:
        """On unless the operating mode is off."""
        mode = self._mode
        return None if mode is None else mode != MODE_OFF

    @property
    def percentage(self) -> int | None:
        """The level the unit is running at (650), as a percentage."""
        if not self.is_on:
            return 0
        level = self.coordinator.data.get(r.REG_CURRENT_VENTILATION_LEVEL, 0)
        if level < SPEED_RANGE[0]:
            return 0
        return ranged_value_to_percentage(SPEED_RANGE, min(level, SPEED_RANGE[1]))

    @property
    def preset_mode(self) -> str | None:
        """The operating mode."""
        mode = self._mode
        return None if mode in (None, MODE_OFF) else r.OPERATING_MODES.get(mode)

    async def async_set_percentage(self, percentage: int) -> None:
        """Run at a level in manual mode."""
        if percentage == 0:
            await self.async_turn_off()
            return
        level = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        if self._mode != MODE_MANUAL:
            await self.coordinator.async_write_register(r.REG_OPERATING_MODE, MODE_MANUAL)
        await self.coordinator.async_write_register(r.REG_VENTILATION_LEVEL, level)
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the operating mode."""
        raw = next(raw for raw, slug in r.OPERATING_MODES.items() if slug == preset_mode)
        await self.coordinator.async_write_register(r.REG_OPERATING_MODE, raw)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on with a preset, a speed, or the last operating mode."""
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
        elif percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            await self.coordinator.async_write_register(r.REG_OPERATING_MODE, self._last_mode)
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Set the operating mode off."""
        await self.coordinator.async_write_register(r.REG_OPERATING_MODE, MODE_OFF)
        await self.coordinator.async_request_refresh()
