"""Switch-Entitäten (Ein/Aus-Schalter) für die Maico KWL Integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MaicoKWLCoordinator


@dataclass(frozen=True, kw_only=True)
class MaicoSwitchEntityDescription(SwitchEntityDescription):
    """Beschreibung einer Maico KWL Switch-Entität."""

    register: int = 0


SWITCH_DESCRIPTIONS: tuple[MaicoSwitchEntityDescription, ...] = (
    MaicoSwitchEntityDescription(
        key="stosslüftung",
        name="Stoßlüftung",
        register=551,
        icon="mdi:weather-windy",
    ),
    MaicoSwitchEntityDescription(
        key="luefterstufe_aus_sperren",
        name="Lüftungsstufe Aus sperren",
        register=106,
        icon="mdi:fan-off",
    ),
    MaicoSwitchEntityDescription(
        key="bde_sperren",
        name="Bedieneinheit sperren",
        register=107,
        icon="mdi:lock-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet Switch-Entitäten ein."""
    coordinator: MaicoKWLCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MaicoSwitchEntity(coordinator, description, entry)
        for description in SWITCH_DESCRIPTIONS
    )


class MaicoSwitchEntity(CoordinatorEntity[MaicoKWLCoordinator], SwitchEntity):
    """Repräsentiert einen Maico KWL Schalter."""

    entity_description: MaicoSwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MaicoKWLCoordinator,
        description: MaicoSwitchEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialisierung."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Maico KWL",
            manufacturer="Maico",
            model="WS 320 KBET",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def is_on(self) -> bool | None:
        """Gibt den aktuellen Schaltzustand zurück."""
        if not self.coordinator.data:
            return None
        raw = self.coordinator.data.get(self.entity_description.register)
        if raw is None:
            return None
        return raw == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Schaltet ein."""
        await self.coordinator.async_write_register(self.entity_description.register, 1)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Schaltet aus."""
        await self.coordinator.async_write_register(self.entity_description.register, 0)
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zusätzliche Attribute."""
        return {"modbus_register": self.entity_description.register}
