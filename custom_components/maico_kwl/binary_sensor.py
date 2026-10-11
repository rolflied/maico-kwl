"""Binary sensor entities for the Maico KWL integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import registers as r
from .coordinator import MaicoKWLConfigEntry, MaicoKWLCoordinator
from .entity import MaicoEntity

PARALLEL_UPDATES = 0

type Data = dict[int, int]


@dataclass(frozen=True, kw_only=True)
class MaicoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Maico KWL binary sensor."""

    registers: tuple[int, ...]
    is_on_fn: Callable[[Data], bool | None]
    enabled_fn: Callable[[Data], bool] | None = None


def _flag(address: int) -> Callable[[Data], bool | None]:
    return lambda data: None if (raw := data.get(address)) is None else raw == 1


def _bit(address: int, bit: int) -> Callable[[Data], bool | None]:
    def is_on(data: Data) -> bool | None:
        value = r.read_value(data, address, r.U32)
        return None if value is None else bool(int(value) >> bit & 1)

    return is_on


def _notice_bit(slug: str) -> int:
    return next(bit for bit, name in r.NOTICE_BITS.items() if name == slug)


_NOTICE = (r.REG_NOTICE, r.REG_NOTICE + 1)

BINARY_SENSORS: tuple[MaicoBinarySensorEntityDescription, ...] = (
    MaicoBinarySensorEntityDescription(
        key="supply_fan_running",
        translation_key="supply_fan_running",
        registers=(r.REG_SUPPLY_FAN_RUNNING,),
        is_on_fn=_flag(r.REG_SUPPLY_FAN_RUNNING),
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    MaicoBinarySensorEntityDescription(
        key="exhaust_fan_running",
        translation_key="exhaust_fan_running",
        registers=(r.REG_EXHAUST_FAN_RUNNING,),
        is_on_fn=_flag(r.REG_EXHAUST_FAN_RUNNING),
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    MaicoBinarySensorEntityDescription(
        key="summer_bypass",
        translation_key="summer_bypass",
        registers=(r.REG_SUMMER_BYPASS,),
        is_on_fn=_flag(r.REG_SUMMER_BYPASS),
        device_class=BinarySensorDeviceClass.OPENING,
    ),
    MaicoBinarySensorEntityDescription(
        key="ptc_heater",
        translation_key="ptc_heater",
        registers=(r.REG_PTC_HEATER,),
        is_on_fn=_flag(r.REG_PTC_HEATER),
        device_class=BinarySensorDeviceClass.HEAT,
    ),
    MaicoBinarySensorEntityDescription(
        key="base_board_contact",
        translation_key="base_board_contact",
        registers=(r.REG_BASE_BOARD_CONTACT,),
        is_on_fn=_flag(r.REG_BASE_BOARD_CONTACT),
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    MaicoBinarySensorEntityDescription(
        key="reheating_relay",
        translation_key="reheating_relay",
        registers=(r.REG_REHEATING_RELAY,),
        is_on_fn=_flag(r.REG_REHEATING_RELAY),
        device_class=BinarySensorDeviceClass.HEAT,
        entity_registry_enabled_default=False,
    ),
    MaicoBinarySensorEntityDescription(
        key="fault",
        translation_key="fault",
        registers=(r.REG_FAULT, r.REG_FAULT + 1),
        is_on_fn=lambda data: (
            None if (v := r.read_value(data, r.REG_FAULT, r.U32)) is None else v != 0
        ),
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    MaicoBinarySensorEntityDescription(
        key="device_filter_due",
        translation_key="device_filter_due",
        registers=_NOTICE,
        is_on_fn=_bit(r.REG_NOTICE, _notice_bit("device_filter_due")),
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    MaicoBinarySensorEntityDescription(
        key="outdoor_filter_due",
        translation_key="outdoor_filter_due",
        registers=_NOTICE,
        is_on_fn=_bit(r.REG_NOTICE, _notice_bit("outdoor_filter_due")),
        device_class=BinarySensorDeviceClass.PROBLEM,
        enabled_fn=lambda data: bool(data.get(r.REG_OUTDOOR_FILTER_REMAINING)),
    ),
    MaicoBinarySensorEntityDescription(
        key="room_filter_due",
        translation_key="room_filter_due",
        registers=_NOTICE,
        is_on_fn=_bit(r.REG_NOTICE, _notice_bit("room_filter_due")),
        device_class=BinarySensorDeviceClass.PROBLEM,
        enabled_fn=lambda data: bool(data.get(r.REG_ROOM_FILTER_REMAINING)),
    ),
    MaicoBinarySensorEntityDescription(
        key="frost_protection",
        translation_key="frost_protection",
        registers=_NOTICE,
        is_on_fn=_bit(r.REG_NOTICE, _notice_bit("frost_protection_active")),
        device_class=BinarySensorDeviceClass.COLD,
    ),
    MaicoBinarySensorEntityDescription(
        key="humidity_protection",
        translation_key="humidity_protection",
        registers=_NOTICE,
        is_on_fn=_bit(r.REG_NOTICE, _notice_bit("humidity_protection_active")),
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MaicoKWLConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        MaicoBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class MaicoBinarySensor(MaicoEntity, BinarySensorEntity):
    """A Maico KWL binary sensor."""

    entity_description: MaicoBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: MaicoKWLCoordinator,
        description: MaicoBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description, description.registers)
        if description.enabled_fn is not None:
            self._attr_entity_registry_enabled_default = bool(
                coordinator.data and description.enabled_fn(coordinator.data)
            )

    @property
    def is_on(self) -> bool | None:
        """Return the state."""
        return self.entity_description.is_on_fn(self.coordinator.data)
