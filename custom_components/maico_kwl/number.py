"""Number-Entitäten (schreibbare Zahlenwerte) für die Maico KWL Integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MaicoKWLCoordinator, to_int16

UNIT_M3H = "m³/h"
UNIT_MONTHS = "Monate"


@dataclass(frozen=True, kw_only=True)
class MaicoNumberEntityDescription(NumberEntityDescription):
    """Beschreibung einer Maico KWL Number-Entität."""

    register: int = 0
    scale: float = 1.0
    signed: bool = False
    write_only: bool = False  # True = kein Lesen aus Modbus


# ── Schreib-/Lesbare Number-Entitäten ─────────────────────────────────────────
NUMBER_DESCRIPTIONS: tuple[MaicoNumberEntityDescription, ...] = (
    # Solltemperatur Raum
    MaicoNumberEntityDescription(
        key="solltemperatur_raum",
        name="Solltemperatur Raum",
        register=553,
        scale=0.1,
        signed=True,
        native_min_value=18.0,
        native_max_value=25.0,
        native_step=0.5,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        icon="mdi:thermometer-auto",
    ),
    # Abgleich Raumtemperatur
    MaicoNumberEntityDescription(
        key="abgleich_raumtemperatur",
        name="Abgleich Raumtemperatur",
        register=300,
        scale=0.1,
        signed=True,
        native_min_value=-3.0,
        native_max_value=3.0,
        native_step=0.1,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        icon="mdi:thermometer-check",
    ),
    # Zuluft Mindesttemperatur Kühlen
    MaicoNumberEntityDescription(
        key="zuluft_min_temp_kuehlen",
        name="Zuluft Mindesttemperatur Kühlen",
        register=301,
        scale=1.0,
        signed=True,
        native_min_value=8.0,
        native_max_value=29.0,
        native_step=1.0,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        icon="mdi:snowflake-thermometer",
    ),
    # Raum Maximaltemperatur
    MaicoNumberEntityDescription(
        key="raum_max_temperatur",
        name="Raum Maximaltemperatur",
        register=302,
        scale=0.1,
        signed=True,
        native_min_value=18.0,
        native_max_value=30.0,
        native_step=0.5,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        icon="mdi:thermometer-high",
    ),
    # Volumenstrom Reduzierte Lüftung
    MaicoNumberEntityDescription(
        key="volumenstrom_reduziert",
        name="Volumenstrom Reduzierte Lüftung",
        register=154,
        native_min_value=80.0,
        native_max_value=300.0,
        native_step=10.0,
        native_unit_of_measurement=UNIT_M3H,
        mode=NumberMode.BOX,
        icon="mdi:fan-minus",
    ),
    # Volumenstrom Nennlüftung
    MaicoNumberEntityDescription(
        key="volumenstrom_nenn",
        name="Volumenstrom Nennlüftung",
        register=155,
        native_min_value=80.0,
        native_max_value=300.0,
        native_step=10.0,
        native_unit_of_measurement=UNIT_M3H,
        mode=NumberMode.BOX,
        icon="mdi:fan",
    ),
    # Volumenstrom Intensivlüftung
    MaicoNumberEntityDescription(
        key="volumenstrom_intensiv",
        name="Volumenstrom Intensivlüftung",
        register=156,
        native_min_value=80.0,
        native_max_value=300.0,
        native_step=10.0,
        native_unit_of_measurement=UNIT_M3H,
        mode=NumberMode.BOX,
        icon="mdi:fan-plus",
    ),
    # Dauer Lüftungsstufe
    MaicoNumberEntityDescription(
        key="dauer_lueftungsstufe",
        name="Dauer Lüftungsstufe",
        register=153,
        native_min_value=5.0,
        native_max_value=90.0,
        native_step=1.0,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
        icon="mdi:timer-outline",
    ),
    # Filterintervall Gerätefilter
    MaicoNumberEntityDescription(
        key="filterintervall_geraet",
        name="Filterintervall Gerätefilter",
        register=150,
        native_min_value=3.0,
        native_max_value=12.0,
        native_step=1.0,
        native_unit_of_measurement=UNIT_MONTHS,
        mode=NumberMode.BOX,
        icon="mdi:air-filter",
    ),
    # Filterintervall Außenfilter
    MaicoNumberEntityDescription(
        key="filterintervall_aussen",
        name="Filterintervall Außenfilter",
        register=151,
        native_min_value=3.0,
        native_max_value=18.0,
        native_step=1.0,
        native_unit_of_measurement=UNIT_MONTHS,
        mode=NumberMode.BOX,
        icon="mdi:air-filter",
    ),
    # Filterintervall Raumfilter
    MaicoNumberEntityDescription(
        key="filterintervall_raum",
        name="Filterintervall Raumfilter",
        register=152,
        native_min_value=1.0,
        native_max_value=6.0,
        native_step=1.0,
        native_unit_of_measurement=UNIT_MONTHS,
        mode=NumberMode.BOX,
        icon="mdi:air-filter",
    ),
    # Zulässige Druckdifferenz Filterüberwachung
    MaicoNumberEntityDescription(
        key="filter_druckdifferenz",
        name="Filter Druckdifferenz Grenzwert",
        register=900,
        native_min_value=10.0,
        native_max_value=200.0,
        native_step=1.0,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.BOX,
        icon="mdi:gauge",
    ),
)

# ── Schreib-Only Number-Entitäten (Bus-Eingangswerte) ─────────────────────────
WRITE_ONLY_NUMBER_DESCRIPTIONS: tuple[MaicoNumberEntityDescription, ...] = (
    # Raumtemperatur via Bus senden (für Auto-Sensor Modus)
    MaicoNumberEntityDescription(
        key="bus_raumtemperatur",
        name="Raumtemperatur Bus",
        register=707,
        scale=0.1,
        signed=True,
        write_only=True,
        native_min_value=-30.0,
        native_max_value=50.0,
        native_step=0.1,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        icon="mdi:thermometer-bluetooth",
    ),
    # Relative Feuchte via Bus senden
    MaicoNumberEntityDescription(
        key="bus_feuchte",
        name="Relative Feuchte Bus",
        register=763,
        write_only=True,
        native_min_value=0.0,
        native_max_value=100.0,
        native_step=1.0,
        device_class=NumberDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.BOX,
        icon="mdi:water-percent-alert",
    ),
    # CO2-/Luftqualität via Bus senden (Hauptwert zur KWL-Steuerung)
    MaicoNumberEntityDescription(
        key="bus_co2",
        name="CO₂-Wert Bus (Luftqualität)",
        register=764,
        write_only=True,
        native_min_value=0.0,
        native_max_value=5000.0,
        native_step=1.0,
        device_class=NumberDeviceClass.CO2,
        native_unit_of_measurement="ppm",
        mode=NumberMode.BOX,
        icon="mdi:molecule-co2",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet Number-Entitäten ein."""
    coordinator: MaicoKWLCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = [
        MaicoNumberEntity(coordinator, desc, entry)
        for desc in NUMBER_DESCRIPTIONS
    ]
    entities += [
        MaicoWriteOnlyNumberEntity(coordinator, desc, entry)
        for desc in WRITE_ONLY_NUMBER_DESCRIPTIONS
    ]
    async_add_entities(entities)


class MaicoNumberEntity(CoordinatorEntity[MaicoKWLCoordinator], NumberEntity):
    """Schreib-/lesbare Number-Entität."""

    entity_description: MaicoNumberEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MaicoKWLCoordinator,
        description: MaicoNumberEntityDescription,
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
    def native_value(self) -> float | None:
        """Gibt den aktuellen Wert zurück."""
        data = self.coordinator.data
        if not data:
            return None
        raw = data.get(self.entity_description.register)
        if raw is None:
            return None
        if self.entity_description.signed:
            raw = to_int16(raw)
        return round(raw * self.entity_description.scale, 1)

    async def async_set_native_value(self, value: float) -> None:
        """Schreibt den neuen Wert ins Gerät."""
        desc = self.entity_description
        raw = round(value / desc.scale)
        await self.coordinator.async_write_register(desc.register, raw)
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zusätzliche Attribute."""
        return {"modbus_register": self.entity_description.register}


class MaicoWriteOnlyNumberEntity(NumberEntity):
    """Schreib-only Number-Entität (kein Rücklesen aus Modbus)."""

    entity_description: MaicoNumberEntityDescription
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: MaicoKWLCoordinator,
        description: MaicoNumberEntityDescription,
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
        # Startwert: Mitte des Bereichs
        self._native_value: float = description.native_min_value or 0.0

    @property
    def native_value(self) -> float:
        """Gibt den zuletzt gesendeten Wert zurück."""
        return self._native_value

    async def async_set_native_value(self, value: float) -> None:
        """Schreibt den Wert ins Gerät."""
        desc = self.entity_description
        raw = round(value / desc.scale)
        success = await self.coordinator.async_write_register(desc.register, raw)
        if success:
            self._native_value = value
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zusätzliche Attribute."""
        return {
            "modbus_register": self.entity_description.register,
            "schreibzyklus_empfehlung": "mindestens alle 10 Minuten",
        }
