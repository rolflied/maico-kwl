"""Base entity for the Maico KWL integration."""

from __future__ import annotations

from collections.abc import Sequence

from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MaicoKWLCoordinator


class MaicoEntity(CoordinatorEntity[MaicoKWLCoordinator]):
    """A Maico KWL entity backed by one or more registers."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MaicoKWLCoordinator,
        description: EntityDescription,
        registers: Sequence[int] = (),
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._registers = tuple(registers)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        """Available while the unit answers and reports the registers."""
        return (
            super().available
            and self.coordinator.data is not None
            and all(address in self.coordinator.data for address in self._registers)
        )
