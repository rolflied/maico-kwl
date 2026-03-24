"""Binäre Sensor-Entitäten für die Maico KWL Integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MaicoKWLCoordinator


@dataclass(frozen=True, kw_only=True)
class MaicoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Beschreibung eines Maico KWL Binärsensors."""

    register: int = 0
    on_value: int = 1  # Welcher Wert bedeutet "an/wahr"


BINARY_SENSOR_DESCRIPTIONS: tuple[MaicoBinarySensorEntityDescription, ...] = (
    MaicoBinarySensorEntityDescription(
        key="ventilator_zuluft",
        name="Zuluftventilator",
        register=800,
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:fan",
    ),
    MaicoBinarySensorEntityDescription(
        key="ventilator_abluft",
        name="Abluftventilator",
        register=801,
        device_class=BinarySensorDeviceClass.RUNNING,
        icon="mdi:fan",
    ),
    MaicoBinarySensorEntityDescription(
        key="sommerbypass",
        name="Sommerbypass",
        register=802,
        device_class=BinarySensorDeviceClass.OPENING,
        icon="mdi:valve-open",
    ),
    MaicoBinarySensorEntityDescription(
        key="ptc_heizregister",
        name="PTC-Heizregister",
        register=803,
        device_class=BinarySensorDeviceClass.HEAT,
        icon="mdi:heating-coil",
    ),
    MaicoBinarySensorEntityDescription(
        key="schaltkontakt_basisplatine",
        name="Schaltkontakt Basisplatine",
        register=804,
        device_class=BinarySensorDeviceClass.POWER,
        icon="mdi:electric-switch",
    ),
    MaicoBinarySensorEntityDescription(
        key="relais_nachheizung",
        name="Relais Nachheizung",
        register=805,
        device_class=BinarySensorDeviceClass.HEAT,
        icon="mdi:radiator",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet Binärsensor-Entitäten ein."""
    coordinator: MaicoKWLCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MaicoBinarySensorEntity(coordinator, description, entry)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class MaicoBinarySensorEntity(
    CoordinatorEntity[MaicoKWLCoordinator], BinarySensorEntity
):
    """Repräsentiert einen Maico KWL Binärsensor."""

    entity_description: MaicoBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MaicoKWLCoordinator,
        description: MaicoBinarySensorEntityDescription,
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
        """Gibt den aktuellen Zustand zurück."""
        if not self.coordinator.data:
            return None
        raw = self.coordinator.data.get(self.entity_description.register)
        if raw is None:
            return None
        return raw == self.entity_description.on_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zusätzliche Attribute."""
        return {"modbus_register": self.entity_description.register}
