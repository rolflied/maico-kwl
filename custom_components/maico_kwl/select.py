"""Select entities for the Maico KWL integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import registers as r
from .coordinator import MaicoKWLConfigEntry, MaicoKWLCoordinator
from .entity import MaicoEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class MaicoSelectEntityDescription(SelectEntityDescription):
    """Describes a Maico KWL select."""

    register: int
    values: dict[int, str]


SELECTS: tuple[MaicoSelectEntityDescription, ...] = (
    MaicoSelectEntityDescription(
        key="operating_mode",
        translation_key="operating_mode",
        register=r.REG_OPERATING_MODE,
        values=r.OPERATING_MODES,
    ),
    MaicoSelectEntityDescription(
        key="ventilation_level",
        translation_key="ventilation_level",
        register=r.REG_VENTILATION_LEVEL,
        values=r.VENTILATION_LEVELS,
    ),
    MaicoSelectEntityDescription(
        key="season",
        translation_key="season",
        register=r.REG_SEASON,
        values=r.SEASONS,
    ),
    MaicoSelectEntityDescription(
        key="room_temperature_source",
        translation_key="room_temperature_source",
        register=r.REG_ROOM_TEMPERATURE_SOURCE,
        values=r.ROOM_TEMPERATURE_SOURCES,
        entity_category=EntityCategory.CONFIG,
    ),
    MaicoSelectEntityDescription(
        key="language",
        translation_key="language",
        register=r.REG_LANGUAGE,
        values=r.LANGUAGES,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaicoKWLConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities."""
    coordinator = entry.runtime_data
    async_add_entities(MaicoSelect(coordinator, description) for description in SELECTS)


class MaicoSelect(MaicoEntity, SelectEntity):
    """A Maico KWL select."""

    entity_description: MaicoSelectEntityDescription

    def __init__(
        self,
        coordinator: MaicoKWLCoordinator,
        description: MaicoSelectEntityDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, description, (description.register,))
        self._attr_options = list(description.values.values())

    @property
    def current_option(self) -> str | None:
        """Return the selected option."""
        desc = self.entity_description
        return desc.values.get(self.coordinator.data.get(desc.register, -1))

    async def async_select_option(self, option: str) -> None:
        """Write the selected option."""
        desc = self.entity_description
        raw = next(raw for raw, slug in desc.values.items() if slug == option)
        await self.coordinator.async_write_register(desc.register, raw)
