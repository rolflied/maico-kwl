"""Base entity for the Maico KWL integration."""

from __future__ import annotations

from collections.abc import Sequence

from homeassistant.core import callback
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
        self._snapshot: tuple[object, ...] | None = None

    def _current_snapshot(self) -> tuple[object, ...] | None:
        """What this entity's state is derived from; None if that is not known."""
        if not self._registers:
            return None
        data = self.coordinator.data or {}
        return (self.available, *(data.get(address) for address in self._registers))

    async def async_added_to_hass(self) -> None:
        """Remember the state that was written when the entity was added."""
        await super().async_added_to_hass()
        self._snapshot = self._current_snapshot()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Write the state only if a register behind it (or availability) changed."""
        snapshot = self._current_snapshot()
        if snapshot is not None and snapshot == self._snapshot:
            return
        self._snapshot = snapshot
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Available while the unit answers and reports the registers."""
        return (
            super().available
            and not self.coordinator.offline
            and self.coordinator.data is not None
            and all(address in self.coordinator.data for address in self._registers)
        )
