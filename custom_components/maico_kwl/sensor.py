"""Sensor-Entitäten für die Maico KWL Integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
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

from .const import DOMAIN, FAN_LEVELS
from .coordinator import MaicoKWLCoordinator, combine_32bit, to_int16

CONCENTRATION_PARTS_PER_MILLION = "ppm"
UNIT_RPM = "U/min"
UNIT_M3H = "m³/h"
UNIT_HOURS = "h"
UNIT_DAYS = "d"


@dataclass(frozen=True, kw_only=True)
class MaicoSensorEntityDescription(SensorEntityDescription):
    """Beschreibung eines Maico KWL Sensors."""

    register: int = 0
    scale: float = 1.0
    signed: bool = False
    high_register: int | None = None  # Für 32-Bit-Werte (High-Word)
    value_map: dict[int, str] | None = None  # Mapping von Wert auf Text


SENSOR_DESCRIPTIONS: tuple[MaicoSensorEntityDescription, ...] = (
    # ── Lüftungsstatus ────────────────────────────────────────────────────────
    MaicoSensorEntityDescription(
        key="aktuelle_lueftungsstufe",
        name="Aktuelle Lüftungsstufe",
        register=650,
        icon="mdi:fan",
        value_map={i: v for i, v in enumerate(FAN_LEVELS)},
    ),
    MaicoSensorEntityDescription(
        key="drehzahl_zuluft",
        name="Drehzahl Zuluftventilator",
        register=651,
        native_unit_of_measurement=UNIT_RPM,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan-clock",
    ),
    MaicoSensorEntityDescription(
        key="drehzahl_abluft",
        name="Drehzahl Abluftventilator",
        register=652,
        native_unit_of_measurement=UNIT_RPM,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:fan-clock",
    ),
    MaicoSensorEntityDescription(
        key="volumenstrom_zuluft",
        name="Volumenstrom Zuluft",
        register=653,
        native_unit_of_measurement=UNIT_M3H,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:air-filter",
    ),
    MaicoSensorEntityDescription(
        key="volumenstrom_abluft",
        name="Volumenstrom Abluft",
        register=654,
        native_unit_of_measurement=UNIT_M3H,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:air-filter",
    ),
    # ── Filterrestlaufzeiten ─────────────────────────────────────────────────
    MaicoSensorEntityDescription(
        key="restlaufzeit_geraetefilter",
        name="Restlaufzeit Gerätefilter",
        register=655,
        native_unit_of_measurement=UNIT_DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:air-filter",
    ),
    MaicoSensorEntityDescription(
        key="restlaufzeit_aussenfilter",
        name="Restlaufzeit Außenfilter",
        register=656,
        native_unit_of_measurement=UNIT_DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:air-filter",
    ),
    MaicoSensorEntityDescription(
        key="restlaufzeit_raumfilter",
        name="Restlaufzeit Raumfilter",
        register=657,
        native_unit_of_measurement=UNIT_DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:air-filter",
    ),
    # ── Temperaturen ──────────────────────────────────────────────────────────
    MaicoSensorEntityDescription(
        key="temperatur_raum",
        name="Temperatur Raum",
        register=700,
        scale=0.1,
        signed=True,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
    ),
    MaicoSensorEntityDescription(
        key="temperatur_raum_extern",
        name="Temperatur Raum Extern",
        register=701,
        scale=0.1,
        signed=True,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
    ),
    MaicoSensorEntityDescription(
        key="temperatur_aul_ewt",
        name="Temperatur Außenluft vor EWT",
        register=702,
        scale=0.1,
        signed=True,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-lines",
    ),
    MaicoSensorEntityDescription(
        key="temperatur_lufteintritt",
        name="Temperatur Lufteintritt",
        register=703,
        scale=0.1,
        signed=True,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-chevron-up",
    ),
    MaicoSensorEntityDescription(
        key="temperatur_zuluft",
        name="Temperatur Zuluft",
        register=704,
        scale=0.1,
        signed=True,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-chevron-up",
    ),
    MaicoSensorEntityDescription(
        key="temperatur_abluft",
        name="Temperatur Abluft",
        register=705,
        scale=0.1,
        signed=True,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-chevron-down",
    ),
    MaicoSensorEntityDescription(
        key="temperatur_fortluft",
        name="Temperatur Fortluft",
        register=706,
        scale=0.1,
        signed=True,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer-chevron-down",
    ),
    # ── Feuchte ───────────────────────────────────────────────────────────────
    # Rohwert = direkt in % (kein Skalierungsfaktor trotz CSV-Angabe "* 10")
    MaicoSensorEntityDescription(
        key="feuchte_abluft",
        name="Relative Feuchte Abluft",
        register=750,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
    ),
    MaicoSensorEntityDescription(
        key="feuchte_sensor1",
        name="Relative Feuchte Sensor 1",
        register=751,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
    ),
    MaicoSensorEntityDescription(
        key="feuchte_sensor2",
        name="Relative Feuchte Sensor 2",
        register=752,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
    ),
    MaicoSensorEntityDescription(
        key="feuchte_sensor3",
        name="Relative Feuchte Sensor 3",
        register=753,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
    ),
    MaicoSensorEntityDescription(
        key="feuchte_sensor4",
        name="Relative Feuchte Sensor 4",
        register=754,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-percent",
    ),
    # ── CO2 ───────────────────────────────────────────────────────────────────
    # Rohwert = direkt in ppm (kein Skalierungsfaktor trotz CSV-Angabe "* 10")
    MaicoSensorEntityDescription(
        key="co2_sensor1",
        name="CO₂ Sensor 1",
        register=755,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:molecule-co2",
    ),
    MaicoSensorEntityDescription(
        key="co2_sensor2",
        name="CO₂ Sensor 2",
        register=756,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:molecule-co2",
    ),
    MaicoSensorEntityDescription(
        key="co2_sensor3",
        name="CO₂ Sensor 3",
        register=757,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:molecule-co2",
    ),
    MaicoSensorEntityDescription(
        key="co2_sensor4",
        name="CO₂ Sensor 4",
        register=758,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:molecule-co2",
    ),
    # ── VOC ───────────────────────────────────────────────────────────────────
    # Rohwert = direkt in ppm (kein Skalierungsfaktor trotz CSV-Angabe "* 10")
    MaicoSensorEntityDescription(
        key="voc_sensor1",
        name="VOC Sensor 1",
        register=759,
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:air-purifier",
    ),
    MaicoSensorEntityDescription(
        key="voc_sensor2",
        name="VOC Sensor 2",
        register=760,
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:air-purifier",
    ),
    MaicoSensorEntityDescription(
        key="voc_sensor3",
        name="VOC Sensor 3",
        register=761,
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:air-purifier",
    ),
    MaicoSensorEntityDescription(
        key="voc_sensor4",
        name="VOC Sensor 4",
        register=762,
        device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:air-purifier",
    ),
    # ── Betriebsstunden (32-Bit High/Low-Word) ────────────────────────────────
    MaicoSensorEntityDescription(
        key="betriebsstunden_feuchteschutz",
        name="Betriebsstunden Feuchteschutz",
        register=851,         # Low-Word
        high_register=850,    # High-Word
        native_unit_of_measurement=UNIT_HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:clock-outline",
    ),
    MaicoSensorEntityDescription(
        key="betriebsstunden_reduziert",
        name="Betriebsstunden Reduzierte Lüftung",
        register=853,
        high_register=852,
        native_unit_of_measurement=UNIT_HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:clock-outline",
    ),
    MaicoSensorEntityDescription(
        key="betriebsstunden_nenn",
        name="Betriebsstunden Nennlüftung",
        register=855,
        high_register=854,
        native_unit_of_measurement=UNIT_HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:clock-outline",
    ),
    MaicoSensorEntityDescription(
        key="betriebsstunden_intensiv",
        name="Betriebsstunden Intensivlüftung",
        register=857,
        high_register=856,
        native_unit_of_measurement=UNIT_HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:clock-outline",
    ),
    MaicoSensorEntityDescription(
        key="betriebsstunden_gesamt",
        name="Betriebsstunden Gesamt",
        register=859,
        high_register=858,
        native_unit_of_measurement=UNIT_HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:clock-check-outline",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet Sensor-Entitäten ein."""
    coordinator: MaicoKWLCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list = [
        MaicoSensorEntity(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS
    ]
    entities.append(MaicoWRGSensorEntity(coordinator, entry))
    async_add_entities(entities)


class MaicoSensorEntity(CoordinatorEntity[MaicoKWLCoordinator], SensorEntity):
    """Repräsentiert einen Maico KWL Sensor."""

    entity_description: MaicoSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MaicoKWLCoordinator,
        description: MaicoSensorEntityDescription,
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
    def native_value(self) -> float | str | None:
        """Gibt den aktuellen Sensorwert zurück."""
        data = self.coordinator.data
        if not data:
            return None

        desc = self.entity_description

        # 32-Bit-Betriebsstunden
        if desc.high_register is not None:
            high = data.get(desc.high_register)
            low = data.get(desc.register)
            if high is None or low is None:
                return None
            return combine_32bit(high, low)

        raw = data.get(desc.register)
        if raw is None:
            return None

        # Text-Mapping (z. B. Lüftungsstufe)
        if desc.value_map is not None:
            return desc.value_map.get(raw, f"Unbekannt ({raw})")

        if desc.signed:
            raw = to_int16(raw)

        if desc.scale != 1.0:
            return round(raw * desc.scale, 1)

        return raw

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zusätzliche Attribute."""
        data = self.coordinator.data
        if not data:
            return {}

        desc = self.entity_description
        attrs: dict[str, Any] = {
            "modbus_register": desc.register,
        }

        if desc.high_register is not None:
            attrs["modbus_register_high"] = desc.high_register

        raw = data.get(desc.register)
        if raw is not None and desc.value_map is None:
            attrs["rohwert"] = raw

        return attrs


# ── Wärmerückgewinnung (berechneter Sensor) ───────────────────────────────────

def _raw_to_temp(raw: int) -> float:
    """Konvertiert einen rohen Register-Temperaturwert (signed, ×10) in °C."""
    if raw > 32767:
        raw -= 65536
    return raw / 10.0


class MaicoWRGSensorEntity(CoordinatorEntity[MaicoKWLCoordinator], SensorEntity):
    """Wärmerückgewinnungs-Effizienz in Prozent (berechneter Sensor).

    Formel: η = (T_Zuluft − T_Außenluft) / (T_Abluft − T_Außenluft) × 100

    Register:
      703 – Temperatur Lufteintritt (Außenluft, Kaltseite Eintritt)
      704 – Temperatur Zuluft       (Frischluft nach Wärmetauscher)
      705 – Temperatur Abluft       (Raumluft, Warmseite Eintritt)
    """

    _attr_has_entity_name = True
    _attr_name = "Wärmerückgewinnung"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:heat-wave"
    _attr_suggested_display_precision = 1

    # Register-Adressen
    _REG_AUSSEN = 703
    _REG_ZULUFT = 704
    _REG_ABLUFT = 705

    def __init__(
        self,
        coordinator: MaicoKWLCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialisierung."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_waermerueckgewinnung"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Maico KWL",
            manufacturer="Maico",
            model="WS 320 KBET",
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def native_value(self) -> float | None:
        """Berechnet die Wärmerückgewinnungseffizienz in Prozent."""
        data = self.coordinator.data
        if not data:
            return None

        raw_aussen = data.get(self._REG_AUSSEN)
        raw_zuluft = data.get(self._REG_ZULUFT)
        raw_abluft = data.get(self._REG_ABLUFT)

        if raw_aussen is None or raw_zuluft is None or raw_abluft is None:
            return None

        t_aussen = _raw_to_temp(raw_aussen)
        t_zuluft = _raw_to_temp(raw_zuluft)
        t_abluft = _raw_to_temp(raw_abluft)

        nenner = t_abluft - t_aussen
        if abs(nenner) < 0.5:
            # Temperaturunterschied zu gering für eine sinnvolle Berechnung
            return None

        effizienz = (t_zuluft - t_aussen) / nenner * 100.0
        # Auf 0–100 % begrenzen (Messungenauigkeiten können leicht über-/unterschreiten)
        return round(max(0.0, min(100.0, effizienz)), 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Zeigt die Eingangstemperaturen der Berechnung als Attribute."""
        data = self.coordinator.data
        if not data:
            return {}

        raw_aussen = data.get(self._REG_AUSSEN)
        raw_zuluft = data.get(self._REG_ZULUFT)
        raw_abluft = data.get(self._REG_ABLUFT)

        attrs: dict[str, Any] = {
            "formel": "η = (T_Zuluft − T_Außenluft) / (T_Abluft − T_Außenluft) × 100",
        }

        if raw_aussen is not None:
            attrs["t_aussenluft_c"] = _raw_to_temp(raw_aussen)
        if raw_zuluft is not None:
            attrs["t_zuluft_c"] = _raw_to_temp(raw_zuluft)
        if raw_abluft is not None:
            attrs["t_abluft_c"] = _raw_to_temp(raw_abluft)

        return attrs
