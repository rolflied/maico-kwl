"""Number entities for the Maico KWL integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import registers as r
from .const import DOMAIN
from .coordinator import MaicoKWLConfigEntry, MaicoKWLCoordinator
from .entity import MaicoEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class MaicoNumberEntityDescription(NumberEntityDescription):
    """Describes a Maico KWL number."""

    register: int
    codec: r.Codec = r.U16


def _temperature(
    key: str,
    register: int,
    minimum: float,
    maximum: float,
    step: float,
    *,
    codec: r.Codec = r.S16_TENTHS,
    category: EntityCategory | None = EntityCategory.CONFIG,
) -> MaicoNumberEntityDescription:
    return MaicoNumberEntityDescription(
        key=key,
        translation_key=key,
        register=register,
        codec=codec,
        native_min_value=minimum,
        native_max_value=maximum,
        native_step=step,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        entity_category=category,
    )


def _setting(
    key: str,
    register: int,
    minimum: float,
    maximum: float,
    unit: str | None,
    *,
    device_class: NumberDeviceClass | None = None,
) -> MaicoNumberEntityDescription:
    return MaicoNumberEntityDescription(
        key=key,
        translation_key=key,
        register=register,
        native_min_value=minimum,
        native_max_value=maximum,
        native_step=1,
        native_unit_of_measurement=unit,
        device_class=device_class,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    )


def _airflow(key: str, register: int) -> MaicoNumberEntityDescription:
    # 80-300 m³/h are the general limits; the unit type may allow less.
    return _setting(
        key,
        register,
        80,
        300,
        UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        device_class=NumberDeviceClass.VOLUME_FLOW_RATE,
    )


NUMBERS: tuple[MaicoNumberEntityDescription, ...] = (
    _temperature(
        "room_temperature_setpoint",
        r.REG_ROOM_TEMPERATURE_SETPOINT,
        18,
        25,
        0.5,
        category=None,
    ),
    _temperature("room_temperature_offset", r.REG_ROOM_TEMPERATURE_OFFSET, -3, 3, 0.1),
    _temperature(
        "supply_air_min_temperature_cooling",
        r.REG_SUPPLY_AIR_MIN_TEMPERATURE_COOLING,
        8,
        29,
        1,
        codec=r.S16,
    ),
    _temperature("room_temperature_max", r.REG_ROOM_TEMPERATURE_MAX, 18, 30, 0.5),
    _airflow("airflow_reduced", r.REG_AIRFLOW_REDUCED),
    _airflow("airflow_nominal", r.REG_AIRFLOW_NOMINAL),
    _airflow("airflow_intensive", r.REG_AIRFLOW_INTENSIVE),
    _setting(
        "ventilation_level_duration",
        r.REG_VENTILATION_LEVEL_DURATION,
        5,
        90,
        UnitOfTime.MINUTES,
        device_class=NumberDeviceClass.DURATION,
    ),
    # Months; the unit comes from the translations (UnitOfTime.MONTHS reads "m").
    _setting("device_filter_interval", r.REG_DEVICE_FILTER_INTERVAL, 3, 12, None),
    _setting("outdoor_filter_interval", r.REG_OUTDOOR_FILTER_INTERVAL, 3, 18, None),
    _setting("room_filter_interval", r.REG_ROOM_FILTER_INTERVAL, 1, 6, None),
    _setting("filter_pressure_limit", r.REG_FILTER_PRESSURE_LIMIT, 10, 200, PERCENTAGE),
)

# Write-only inputs the unit uses instead of its own sensors (see bus.py).
BUS_NUMBERS: tuple[MaicoNumberEntityDescription, ...] = (
    MaicoNumberEntityDescription(
        key="bus_room_temperature",
        translation_key="bus_room_temperature",
        register=r.REG_BUS_ROOM_TEMPERATURE,
        codec=r.S16_TENTHS,
        native_min_value=-30,
        native_max_value=120,
        native_step=0.1,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
    ),
    MaicoNumberEntityDescription(
        key="bus_humidity",
        translation_key="bus_humidity",
        register=r.REG_BUS_HUMIDITY,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        device_class=NumberDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.BOX,
    ),
    MaicoNumberEntityDescription(
        key="bus_air_quality",
        translation_key="bus_air_quality",
        register=r.REG_BUS_AIR_QUALITY,
        native_min_value=0,
        native_max_value=5000,
        native_step=1,
        device_class=NumberDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaicoKWLConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator = entry.runtime_data
    entities: list[NumberEntity] = [
        MaicoNumber(coordinator, description) for description in NUMBERS
    ]
    entities.extend(MaicoBusNumber(coordinator, description) for description in BUS_NUMBERS)
    async_add_entities(entities)


class MaicoNumber(MaicoEntity, NumberEntity):
    """A writable setting of the unit."""

    entity_description: MaicoNumberEntityDescription

    def __init__(
        self,
        coordinator: MaicoKWLCoordinator,
        description: MaicoNumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator, description, (description.register,))

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        desc = self.entity_description
        return r.read_value(self.coordinator.data, desc.register, desc.codec)

    async def async_set_native_value(self, value: float) -> None:
        """Write a new value."""
        desc = self.entity_description
        await self.coordinator.async_write(desc.register, desc.codec.encode(value))


class MaicoBusNumber(MaicoEntity, NumberEntity):
    """A write-only bus input; shows the value last sent."""

    entity_description: MaicoNumberEntityDescription

    def __init__(
        self,
        coordinator: MaicoKWLCoordinator,
        description: MaicoNumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator, description)

    @property
    def native_value(self) -> float | None:
        """Return the value last written."""
        return self.coordinator.bus_values.get(self.entity_description.register)

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Name the entity that feeds this input, if any."""
        return {
            "source_entity": self.coordinator.bus.source_entity(self.entity_description.register)
        }

    async def async_set_native_value(self, value: float) -> None:
        """Send a value to the unit; it is repeated until changed."""
        register = self.entity_description.register
        if source := self.coordinator.bus.source_entity(register):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="bus_input_has_source",
                translation_placeholders={"entity_id": source},
            )
        await self.coordinator.bus.async_set(register, value)
