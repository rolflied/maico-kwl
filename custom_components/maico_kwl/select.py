"""Select-Entitäten (Auswahl-Felder) für die Maico KWL Integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, FAN_LEVELS, LANGUAGES, OPERATING_MODES, ROOM_TEMP_SOURCES, SEASONS
from .coordinator import MaicoKWLCoordinator


@dataclass(frozen=True, kw_only=True)
class MaicoSelectEntityDescription(SelectEntityDescription):
    """Beschreibung einer Maico KWL Select-Entität."""

    register: int = 0
    options_list: tuple[str, ...] = ()


SELECT_DESCRIPTIONS: tuple[MaicoSelectEntityDescription, ...] = (
    MaicoSelectEntityDescription(
        key="betriebsart",
        name="Betriebsart",
        register=550,
        options_list=tuple(OPERATING_MODES),
        icon="mdi:cog-outline",
    ),
    MaicoSelectEntityDescription(
        key="lueftungsstufe_soll",
        name="Lüftungsstufe Sollwert",
        register=554,
        options_list=tuple(FAN_LEVELS),
        icon="mdi:fan-speed-1",
    ),
    MaicoSelectEntityDescription(
        key="jahreszeit",
        name="Jahreszeit",
        register=552,
        options_list=tuple(SEASONS),
        icon="mdi:weather-partly-cloudy",
    ),
    MaicoSelectEntityDescription(
        key="raumtemperaturquelle",
        name="Raumtemperatur Quelle",
        register=109,
        options_list=tuple(ROOM_TEMP_SOURCES),
        icon="mdi:thermometer-probe",
    ),
    MaicoSelectEntityDescription(
        key="geraetesprache",
        name="Gerätesprache",
        register=108,
        options_list=tuple(LANGUAGES),
        icon="mdi:translate",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet Select-Entitäten ein."""
    coordinator: MaicoKWLCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MaicoSelectEntity(coordinator, description, entry)
        for description in SELECT_DESCRIPTIONS
    )


class MaicoSelectEntity(CoordinatorEntity[MaicoKWLCoordinator], SelectEntity):
    """Repräsentiert eine Maico KWL Select-Entität."""

    entity_description: MaicoSelectEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MaicoKWLCoordinator,
        description: MaicoSelectEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialisierung."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_options = list(description.options_list)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Maico KWL",
            manufacturer="Maico",
            model="WS 320 KBET",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def current_option(self) -> str | None:
        """Gibt die aktuell gewählte Option zurück."""
        data = self.coordinator.data
        if not data:
            return None
        raw = data.get(self.entity_description.register)
        if raw is None:
            return None
        opts = self.entity_description.options_list
        if raw < len(opts):
            return opts[raw]
        return f"Unbekannt ({raw})"

    async def async_select_option(self, option: str) -> None:
        """Setzt eine neue Option."""
        opts = self.entity_description.options_list
        if option not in opts:
            return
        index = opts.index(option)
        await self.coordinator.async_write_register(
            self.entity_description.register, index
        )
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zusätzliche Attribute."""
        return {
            "modbus_register": self.entity_description.register,
            "verfuegbare_optionen": list(self.entity_description.options_list),
        }
