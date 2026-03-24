"""Button-Entitäten (einmalige Aktionen) für die Maico KWL Integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MaicoKWLCoordinator


@dataclass(frozen=True, kw_only=True)
class MaicoButtonEntityDescription(ButtonEntityDescription):
    """Beschreibung einer Maico KWL Button-Entität."""

    register: int = 0
    write_value: int = 1  # Wert der beim Drücken geschrieben wird


BUTTON_DESCRIPTIONS: tuple[MaicoButtonEntityDescription, ...] = (
    MaicoButtonEntityDescription(
        key="filterwechsel_geraet",
        name="Gerätefilter gewechselt",
        register=157,
        write_value=1,
        icon="mdi:air-filter",
    ),
    MaicoButtonEntityDescription(
        key="filterwechsel_aussen",
        name="Außenfilter gewechselt",
        register=158,
        write_value=1,
        icon="mdi:air-filter",
    ),
    MaicoButtonEntityDescription(
        key="filterwechsel_raum",
        name="Raumfilter gewechselt",
        register=159,
        write_value=1,
        icon="mdi:air-filter",
    ),
    MaicoButtonEntityDescription(
        key="fehler_reset",
        name="Fehler zurücksetzen",
        register=405,
        write_value=1,
        icon="mdi:alert-circle-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet Button-Entitäten ein."""
    coordinator: MaicoKWLCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MaicoButtonEntity(coordinator, description, entry)
        for description in BUTTON_DESCRIPTIONS
    )


class MaicoButtonEntity(ButtonEntity):
    """Repräsentiert einen Maico KWL Button."""

    entity_description: MaicoButtonEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MaicoKWLCoordinator,
        description: MaicoButtonEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialisierung."""
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Maico KWL",
            manufacturer="Maico",
            model="WS 320 KBET",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    async def async_press(self) -> None:
        """Führt die Aktion aus."""
        await self.coordinator.async_write_register(
            self.entity_description.register,
            self.entity_description.write_value,
        )
        await self.coordinator.async_request_refresh()
