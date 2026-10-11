"""Button entities for the Maico KWL integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import registers as r
from .coordinator import MaicoKWLConfigEntry, MaicoKWLCoordinator
from .entity import MaicoEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class MaicoButtonEntityDescription(ButtonEntityDescription):
    """Describes a Maico KWL button."""

    press_fn: Callable[[MaicoKWLCoordinator], Awaitable[None]]
    # Registers that must answer for the button to be available.
    registers: tuple[int, ...] = ()


def _write_one(address: int) -> Callable[[MaicoKWLCoordinator], Awaitable[None]]:
    return lambda c: c.async_write_register(address, 1)


async def _sync_clock(coordinator: MaicoKWLCoordinator) -> None:
    # The unit keeps local time without a time zone.
    await coordinator.async_write(r.REG_CLOCK, r.encode_clock(dt_util.now()))


BUTTONS: tuple[MaicoButtonEntityDescription, ...] = (
    MaicoButtonEntityDescription(
        key="reset_device_filter",
        translation_key="reset_device_filter",
        press_fn=_write_one(r.REG_RESET_DEVICE_FILTER),
        registers=(r.REG_DEVICE_FILTER_REMAINING,),
        entity_category=EntityCategory.CONFIG,
    ),
    MaicoButtonEntityDescription(
        key="reset_outdoor_filter",
        translation_key="reset_outdoor_filter",
        press_fn=_write_one(r.REG_RESET_OUTDOOR_FILTER),
        registers=(r.REG_OUTDOOR_FILTER_REMAINING,),
        entity_category=EntityCategory.CONFIG,
    ),
    MaicoButtonEntityDescription(
        key="reset_room_filter",
        translation_key="reset_room_filter",
        press_fn=_write_one(r.REG_RESET_ROOM_FILTER),
        registers=(r.REG_ROOM_FILTER_REMAINING,),
        entity_category=EntityCategory.CONFIG,
    ),
    MaicoButtonEntityDescription(
        key="reset_faults",
        translation_key="reset_faults",
        press_fn=_write_one(r.REG_RESET_FAULT),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MaicoButtonEntityDescription(
        key="sync_clock",
        translation_key="sync_clock",
        press_fn=_sync_clock,
        registers=(r.REG_CLOCK,),
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaicoKWLConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button entities."""
    coordinator = entry.runtime_data
    async_add_entities(MaicoButton(coordinator, description) for description in BUTTONS)


class MaicoButton(MaicoEntity, ButtonEntity):
    """A Maico KWL button."""

    entity_description: MaicoButtonEntityDescription

    def __init__(
        self,
        coordinator: MaicoKWLCoordinator,
        description: MaicoButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, description, description.registers)

    async def async_press(self) -> None:
        """Run the action and read back the result."""
        await self.entity_description.press_fn(self.coordinator)
        await self.coordinator.async_request_refresh()
