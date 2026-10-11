"""Switch entities for the Maico KWL integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import registers as r
from .coordinator import MaicoKWLConfigEntry, MaicoKWLCoordinator
from .entity import MaicoEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class MaicoSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Maico KWL switch."""

    register: int


SWITCHES: tuple[MaicoSwitchEntityDescription, ...] = (
    MaicoSwitchEntityDescription(
        key="boost_ventilation",
        translation_key="boost_ventilation",
        register=r.REG_BOOST_VENTILATION,
    ),
    MaicoSwitchEntityDescription(
        key="off_level_lock",
        translation_key="off_level_lock",
        register=r.REG_OFF_LEVEL_LOCK,
        entity_category=EntityCategory.CONFIG,
    ),
    MaicoSwitchEntityDescription(
        key="control_panel_lock",
        translation_key="control_panel_lock",
        register=r.REG_CONTROL_PANEL_LOCK,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaicoKWLConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch entities."""
    coordinator = entry.runtime_data
    async_add_entities(MaicoSwitch(coordinator, description) for description in SWITCHES)


class MaicoSwitch(MaicoEntity, SwitchEntity):
    """A Maico KWL switch."""

    entity_description: MaicoSwitchEntityDescription

    def __init__(
        self,
        coordinator: MaicoKWLCoordinator,
        description: MaicoSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, description, (description.register,))

    @property
    def is_on(self) -> bool | None:
        """Return the state."""
        raw = self.coordinator.data.get(self.entity_description.register)
        return None if raw is None else raw == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on."""
        await self.coordinator.async_write_register(self.entity_description.register, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off."""
        await self.coordinator.async_write_register(self.entity_description.register, 0)
