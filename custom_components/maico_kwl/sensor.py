"""Sensor entities for the Maico KWL integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfPower,
    UnitOfRatio,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import registers as r
from .coordinator import MaicoKWLConfigEntry, MaicoKWLCoordinator
from .entity import MaicoEntity

PARALLEL_UPDATES = 0

type Data = dict[int, int]


@dataclass(frozen=True, kw_only=True)
class MaicoSensorEntityDescription(SensorEntityDescription):
    """Describes a Maico KWL sensor."""

    registers: tuple[int, ...]
    value_fn: Callable[[MaicoKWLCoordinator], Any]
    attrs_fn: Callable[[Data], dict[str, Any]] | None = None
    # Decides from the first poll whether a new entity starts enabled, for
    # parts that are not fitted to every unit.
    enabled_fn: Callable[[Data], bool] | None = None


def _value(address: int, codec: r.Codec = r.U16) -> Callable[[MaicoKWLCoordinator], Any]:
    return lambda c: r.read_value(c.data, address, codec)


def _enum(address: int, options: dict[int, str]) -> Callable[[MaicoKWLCoordinator], Any]:
    return lambda c: options.get(c.data.get(address, -1))


def _non_zero(address: int) -> Callable[[Data], bool]:
    return lambda data: bool(data.get(address))


def _temperature(
    key: str,
    address: int,
    *,
    enabled_fn: Callable[[Data], bool] | None = None,
    enabled: bool = True,
) -> MaicoSensorEntityDescription:
    return MaicoSensorEntityDescription(
        key=key,
        translation_key=key,
        registers=(address,),
        value_fn=_value(address, r.S16_TENTHS),
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        enabled_fn=enabled_fn,
        entity_registry_enabled_default=enabled,
    )


def _optional_bank(
    kind: str,
    start: int,
    count: int,
    device_class: SensorDeviceClass,
    unit: str,
    *,
    first: int = 1,
) -> list[MaicoSensorEntityDescription]:
    return [
        MaicoSensorEntityDescription(
            key=f"{kind}_{i + first}",
            translation_key=kind,
            translation_placeholders={"n": str(i + first)},
            registers=(start + i,),
            value_fn=_value(start + i),
            device_class=device_class,
            native_unit_of_measurement=unit,
            state_class=SensorStateClass.MEASUREMENT,
            enabled_fn=_non_zero(start + i),
        )
        for i in range(count)
    ]


def _hours(key: str, address: int, enabled: bool = True) -> MaicoSensorEntityDescription:
    return MaicoSensorEntityDescription(
        key=key,
        translation_key=key,
        registers=(address, address + 1),
        value_fn=_value(address, r.U32),
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=enabled,
    )


def _bits(address: int, names: dict[int, str]) -> Callable[[Data], dict[str, Any]]:
    def attrs(data: Data) -> dict[str, Any]:
        value = r.read_value(data, address, r.U32)
        if value is None:
            return {}
        return {"active": r.active_bits(int(value), names), "code": int(value)}

    return attrs


def _bit_count(address: int) -> Callable[[MaicoKWLCoordinator], Any]:
    def value(c: MaicoKWLCoordinator) -> int | None:
        raw = r.read_value(c.data, address, r.U32)
        return None if raw is None else int(raw).bit_count()

    return value


def _temperatures(c: MaicoKWLCoordinator) -> tuple[float, float, float] | None:
    values = [
        r.read_value(c.data, address, r.S16_TENTHS)
        for address in (
            r.REG_AIR_INTAKE_TEMPERATURE,
            r.REG_SUPPLY_AIR_TEMPERATURE,
            r.REG_EXTRACT_AIR_TEMPERATURE,
        )
    ]
    if any(v is None for v in values):
        return None
    return values[0], values[1], values[2]  # type: ignore[return-value]


def _bypass_open(c: MaicoKWLCoordinator) -> bool:
    return bool(c.data.get(r.REG_SUMMER_BYPASS))


def _efficiency(c: MaicoKWLCoordinator) -> float | None:
    if (temps := _temperatures(c)) is None or _bypass_open(c):
        return None
    return r.heat_recovery_efficiency(*temps)


def _recovery_power(c: MaicoKWLCoordinator) -> float | None:
    temps = _temperatures(c)
    airflow = r.read_value(c.data, r.REG_SUPPLY_AIRFLOW)
    if temps is None or airflow is None or _bypass_open(c):
        return None
    return r.heat_recovery_power(airflow, temps[0], temps[1])


def _clock_deviation(c: MaicoKWLCoordinator) -> int | None:
    if (clock := r.decode_clock(c.data)) is None or c.last_read is None:
        return None
    device = clock.replace(tzinfo=dt_util.get_default_time_zone())
    return round((device - c.last_read).total_seconds())


_FAN_SPEED = {
    "native_unit_of_measurement": REVOLUTIONS_PER_MINUTE,
    "state_class": SensorStateClass.MEASUREMENT,
}
_AIRFLOW = {
    "device_class": SensorDeviceClass.VOLUME_FLOW_RATE,
    "native_unit_of_measurement": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    "state_class": SensorStateClass.MEASUREMENT,
}
_FILTER_DAYS = {
    "device_class": SensorDeviceClass.DURATION,
    "native_unit_of_measurement": UnitOfTime.DAYS,
    "state_class": SensorStateClass.MEASUREMENT,
}
_STATE_ENUM = {
    "device_class": SensorDeviceClass.ENUM,
    "options": list(r.HEAT_COOL_STATES.values()),
    "entity_category": EntityCategory.DIAGNOSTIC,
    "entity_registry_enabled_default": False,
}

SENSORS: tuple[MaicoSensorEntityDescription, ...] = (
    # ── Ventilation status ────────────────────────────────────────────────────
    MaicoSensorEntityDescription(
        key="current_ventilation_level",
        translation_key="current_ventilation_level",
        registers=(r.REG_CURRENT_VENTILATION_LEVEL,),
        value_fn=_enum(r.REG_CURRENT_VENTILATION_LEVEL, r.VENTILATION_LEVELS),
        device_class=SensorDeviceClass.ENUM,
        options=list(r.VENTILATION_LEVELS.values()),
    ),
    MaicoSensorEntityDescription(
        key="supply_fan_speed",
        translation_key="supply_fan_speed",
        registers=(r.REG_SUPPLY_FAN_SPEED,),
        value_fn=_value(r.REG_SUPPLY_FAN_SPEED),
        **_FAN_SPEED,
    ),
    MaicoSensorEntityDescription(
        key="exhaust_fan_speed",
        translation_key="exhaust_fan_speed",
        registers=(r.REG_EXHAUST_FAN_SPEED,),
        value_fn=_value(r.REG_EXHAUST_FAN_SPEED),
        **_FAN_SPEED,
    ),
    MaicoSensorEntityDescription(
        key="supply_airflow",
        translation_key="supply_airflow",
        registers=(r.REG_SUPPLY_AIRFLOW,),
        value_fn=_value(r.REG_SUPPLY_AIRFLOW),
        **_AIRFLOW,
    ),
    MaicoSensorEntityDescription(
        key="exhaust_airflow",
        translation_key="exhaust_airflow",
        registers=(r.REG_EXHAUST_AIRFLOW,),
        value_fn=_value(r.REG_EXHAUST_AIRFLOW),
        **_AIRFLOW,
    ),
    # ── Filters ───────────────────────────────────────────────────────────────
    MaicoSensorEntityDescription(
        key="device_filter_remaining",
        translation_key="device_filter_remaining",
        registers=(r.REG_DEVICE_FILTER_REMAINING,),
        value_fn=_value(r.REG_DEVICE_FILTER_REMAINING),
        **_FILTER_DAYS,
    ),
    # A filter that is not fitted stays at 0 days.
    MaicoSensorEntityDescription(
        key="outdoor_filter_remaining",
        translation_key="outdoor_filter_remaining",
        registers=(r.REG_OUTDOOR_FILTER_REMAINING,),
        value_fn=_value(r.REG_OUTDOOR_FILTER_REMAINING),
        enabled_fn=_non_zero(r.REG_OUTDOOR_FILTER_REMAINING),
        **_FILTER_DAYS,
    ),
    MaicoSensorEntityDescription(
        key="room_filter_remaining",
        translation_key="room_filter_remaining",
        registers=(r.REG_ROOM_FILTER_REMAINING,),
        value_fn=_value(r.REG_ROOM_FILTER_REMAINING),
        enabled_fn=_non_zero(r.REG_ROOM_FILTER_REMAINING),
        **_FILTER_DAYS,
    ),
    # ── Temperatures ──────────────────────────────────────────────────────────
    _temperature("room_temperature", r.REG_ROOM_TEMPERATURE),
    _temperature(
        "external_room_temperature",
        r.REG_EXTERNAL_ROOM_TEMPERATURE,
        enabled_fn=lambda d: d.get(r.REG_ROOM_TEMPERATURE_SOURCE) == 1,
    ),
    _temperature(
        "outdoor_before_ehx_temperature",
        r.REG_OUTDOOR_BEFORE_EHX_TEMPERATURE,
        enabled=False,
    ),
    _temperature("air_intake_temperature", r.REG_AIR_INTAKE_TEMPERATURE),
    _temperature("supply_air_temperature", r.REG_SUPPLY_AIR_TEMPERATURE),
    _temperature("extract_air_temperature", r.REG_EXTRACT_AIR_TEMPERATURE),
    _temperature("exhaust_air_temperature", r.REG_EXHAUST_AIR_TEMPERATURE),
    # ── Air quality ───────────────────────────────────────────────────────────
    MaicoSensorEntityDescription(
        key="extract_air_humidity",
        translation_key="extract_air_humidity",
        registers=(r.REG_EXTRACT_AIR_HUMIDITY,),
        value_fn=_value(r.REG_EXTRACT_AIR_HUMIDITY),
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    *_optional_bank(
        "humidity_sensor",
        r.REG_HUMIDITY_SENSOR,
        4,
        SensorDeviceClass.HUMIDITY,
        PERCENTAGE,
        first=1,
    ),
    *_optional_bank(
        "co2_sensor",
        r.REG_CO2_SENSOR,
        4,
        SensorDeviceClass.CO2,
        UnitOfRatio.PARTS_PER_MILLION,
        first=1,
    ),
    *_optional_bank(
        "voc_sensor",
        r.REG_VOC_SENSOR,
        4,
        SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        UnitOfRatio.PARTS_PER_MILLION,
        first=1,
    ),
    *_optional_bank(
        "enocean_co2",
        r.REG_ENOCEAN_CO2,
        8,
        SensorDeviceClass.CO2,
        UnitOfRatio.PARTS_PER_MILLION,
        first=0,
    ),
    *_optional_bank(
        "enocean_humidity",
        r.REG_ENOCEAN_HUMIDITY,
        8,
        SensorDeviceClass.HUMIDITY,
        PERCENTAGE,
        first=0,
    ),
    *_optional_bank(
        "enocean_voc",
        r.REG_ENOCEAN_VOC,
        8,
        SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        UnitOfRatio.PARTS_PER_MILLION,
        first=0,
    ),
    # ── Faults and notices ────────────────────────────────────────────────────
    MaicoSensorEntityDescription(
        key="faults",
        translation_key="faults",
        registers=(r.REG_FAULT, r.REG_FAULT + 1),
        value_fn=_bit_count(r.REG_FAULT),
        attrs_fn=_bits(r.REG_FAULT, r.FAULT_BITS),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MaicoSensorEntityDescription(
        key="notices",
        translation_key="notices",
        registers=(r.REG_NOTICE, r.REG_NOTICE + 1),
        value_fn=_bit_count(r.REG_NOTICE),
        attrs_fn=_bits(r.REG_NOTICE, r.NOTICE_BITS),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # ── ZP1 extension module ──────────────────────────────────────────────────
    MaicoSensorEntityDescription(
        key="brine_pump",
        translation_key="brine_pump",
        registers=(r.REG_BRINE_PUMP,),
        value_fn=_enum(r.REG_BRINE_PUMP, r.HEAT_COOL_STATES),
        **_STATE_ENUM,
    ),
    MaicoSensorEntityDescription(
        key="three_way_damper",
        translation_key="three_way_damper",
        registers=(r.REG_THREE_WAY_DAMPER,),
        value_fn=_enum(r.REG_THREE_WAY_DAMPER, r.HEAT_COOL_STATES),
        **_STATE_ENUM,
    ),
    MaicoSensorEntityDescription(
        key="zone_damper",
        translation_key="zone_damper",
        registers=(r.REG_ZONE_DAMPER,),
        value_fn=_enum(r.REG_ZONE_DAMPER, r.ZONE_DAMPER_STATES),
        device_class=SensorDeviceClass.ENUM,
        options=list(r.ZONE_DAMPER_STATES.values()),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    # ── Operating hours ───────────────────────────────────────────────────────
    _hours("operating_hours_humidity_protection", r.REG_HOURS_HUMIDITY_PROTECTION),
    _hours("operating_hours_reduced", r.REG_HOURS_REDUCED),
    _hours("operating_hours_nominal", r.REG_HOURS_NOMINAL),
    _hours("operating_hours_intensive", r.REG_HOURS_INTENSIVE),
    _hours("operating_hours_total", r.REG_HOURS_TOTAL),
    _hours("operating_hours_reheating_relay", r.REG_HOURS_REHEATING_RELAY, False),
    _hours("operating_hours_brine_pump", r.REG_HOURS_BRINE_PUMP, False),
    _hours("operating_hours_three_way_damper", r.REG_HOURS_THREE_WAY_DAMPER, False),
    _hours("operating_hours_zone_damper", r.REG_HOURS_ZONE_DAMPER, False),
    _hours("operating_hours_switch_contact", r.REG_HOURS_SWITCH_CONTACT, False),
    # ── Calculated ────────────────────────────────────────────────────────────
    MaicoSensorEntityDescription(
        key="heat_recovery_efficiency",
        translation_key="heat_recovery_efficiency",
        registers=(
            r.REG_AIR_INTAKE_TEMPERATURE,
            r.REG_SUPPLY_AIR_TEMPERATURE,
            r.REG_EXTRACT_AIR_TEMPERATURE,
        ),
        value_fn=_efficiency,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    MaicoSensorEntityDescription(
        key="heat_recovery_power",
        translation_key="heat_recovery_power",
        registers=(
            r.REG_AIR_INTAKE_TEMPERATURE,
            r.REG_SUPPLY_AIR_TEMPERATURE,
            r.REG_SUPPLY_AIRFLOW,
        ),
        value_fn=_recovery_power,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    MaicoSensorEntityDescription(
        key="clock_deviation",
        translation_key="clock_deviation",
        registers=tuple(range(r.REG_CLOCK, r.REG_CLOCK + 6)),
        value_fn=_clock_deviation,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaicoKWLConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(MaicoSensor(coordinator, description) for description in SENSORS)


class MaicoSensor(MaicoEntity, SensorEntity):
    """A Maico KWL sensor."""

    entity_description: MaicoSensorEntityDescription

    def __init__(
        self,
        coordinator: MaicoKWLCoordinator,
        description: MaicoSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description, description.registers)
        if description.enabled_fn is not None:
            self._attr_entity_registry_enabled_default = bool(
                coordinator.data and description.enabled_fn(coordinator.data)
            )

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the decoded bits of fault and notice words."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
