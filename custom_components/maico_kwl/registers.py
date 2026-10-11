"""Modbus register map of the Maico KWL control (WS/WR series).

Source: Maico "KWL Steuerung Modbus Parameterbeschreibung RTU/TCP"
(CSV from maico-ventilatoren.com). This module has no Home Assistant imports
so it can be tested on its own.

Conventions taken from the documentation:
- Every register is a holding register, read with FC 03.
- Over Modbus TCP the unit only accepts FC 16 (Write Multiple Registers) for
  writes. FC 06 is documented for RTU only.
- 32-bit values are High-Word first.
- Default unit id is 10, TCP needs firmware V1.1.1 or newer.

Deviations from the documentation, checked on live units:
- Humidity (750-754) and CO2/VOC (755-762) are documented as "x10", but the
  unit reports them unscaled (e.g. 54 = 54 %, 548 = 548 ppm). The EnOcean
  values (350-373) follow the same pattern.
- 301 (minimum supply air temperature for cooling) is whole degrees.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

# ── Enumerations (raw value -> state slug) ─────────────────────────────────────

OPERATING_MODES: dict[int, str] = {
    0: "off",
    1: "manual",
    2: "auto_time",
    3: "auto_sensor",
    4: "eco_supply_air",
    5: "eco_exhaust_air",
}
VENTILATION_LEVELS: dict[int, str] = {
    0: "off",
    1: "humidity_protection",
    2: "reduced",
    3: "nominal",
    4: "intensive",
}
SEASONS: dict[int, str] = {0: "winter", 1: "summer"}
LANGUAGES: dict[int, str] = {0: "german", 1: "english", 2: "french", 3: "italian"}
ROOM_TEMPERATURE_SOURCES: dict[int, str] = {
    0: "comfort_control_panel",
    1: "external",
    2: "internal",
    3: "bus",
}
HEAT_COOL_STATES: dict[int, str] = {0: "off", 1: "heating", 2: "cooling"}
ZONE_DAMPER_STATES: dict[int, str] = {0: "off", 1: "zone_1", 2: "zone_2", 3: "zone_sensor"}

# Bit meanings of the fault (401/402) and notice (403/404) words. The CSV only
# says "Bitfeld"; the meanings follow the Maico Geniovent parameter list, which
# uses the same control. Bit n of the 32-bit value (401 = bits 16-31).
FAULT_BITS: dict[int, str] = {
    0: "supply_fan",
    1: "exhaust_fan",
    2: "sensor_air_intake",
    3: "sensor_supply_air",
    4: "sensor_extract_air",
    5: "sensor_room_control_panel",
    6: "sensor_room",
    7: "sensor_outdoor_before_ehx",
    8: "bypass",
    9: "zone_damper",
    10: "combi_sensor",
    11: "frost_protection",
    12: "external_preheater",
    13: "supply_or_extract_too_cold",
    14: "sensor_room_bus",
    15: "communication_zp1",
    16: "communication_zp2",
    17: "sensor_extract",
    18: "communication_control_panel",
    19: "system_memory",
    20: "system_bus",
    21: "unknown",
    22: "external_safety_shutdown",
}
NOTICE_BITS: dict[int, str] = {
    0: "brine_ehx_low_cooling",
    1: "communication_enocean",
    2: "communication_knx",
    3: "communication_air_at_home",
    4: "bypass_active",
    5: "zone_ventilation_active",
    6: "frost_protection_active",
    7: "frost_protection_airflow_reduced",
    8: "control_panel_locked",
    9: "device_filter_due",
    10: "outdoor_filter_due",
    11: "room_filter_due",
    12: "airflow_calibration_active",
    13: "humidity_protection_active",
    14: "reheating_active",
    16: "door_contact_triggered",
    17: "external_safety_shutdown",
    18: "forced_ventilation_active",
    19: "communication_modbus",
    20: "switch_test_active",
    21: "filter_pressure_init_active",
    22: "pressure_setpoint_not_reached",
    23: "external_start_stop_active",
    24: "night_cooling_active",
    25: "purge_active",
    26: "motion_detector_active",
    27: "external_control_active",
    28: "airflow_balancing_active",
    29: "holiday_program_active",
    30: "sensor_mode_active",
}

# ── Register addresses ─────────────────────────────────────────────────────────

REG_CLOCK = 100  # 100-105: year, month, day, hour, minute, second
REG_OFF_LEVEL_LOCK = 106
REG_CONTROL_PANEL_LOCK = 107
REG_LANGUAGE = 108
REG_ROOM_TEMPERATURE_SOURCE = 109

REG_DEVICE_FILTER_INTERVAL = 150
REG_OUTDOOR_FILTER_INTERVAL = 151
REG_ROOM_FILTER_INTERVAL = 152
REG_VENTILATION_LEVEL_DURATION = 153
REG_AIRFLOW_REDUCED = 154
REG_AIRFLOW_NOMINAL = 155
REG_AIRFLOW_INTENSIVE = 156
REG_RESET_DEVICE_FILTER = 157
REG_RESET_OUTDOOR_FILTER = 158
REG_RESET_ROOM_FILTER = 159

REG_ROOM_TEMPERATURE_OFFSET = 300
REG_SUPPLY_AIR_MIN_TEMPERATURE_COOLING = 301
REG_ROOM_TEMPERATURE_MAX = 302

REG_ENOCEAN_CO2 = 350  # 350-357, ID0-ID7
REG_ENOCEAN_HUMIDITY = 358  # 358-365
REG_ENOCEAN_VOC = 366  # 366-373

REG_FAULT = 401  # 401 high word, 402 low word
REG_NOTICE = 403  # 403 high word, 404 low word
REG_RESET_FAULT = 405  # write-only

REG_OPERATING_MODE = 550
REG_BOOST_VENTILATION = 551
REG_SEASON = 552
REG_ROOM_TEMPERATURE_SETPOINT = 553
REG_VENTILATION_LEVEL = 554

REG_CURRENT_VENTILATION_LEVEL = 650
REG_SUPPLY_FAN_SPEED = 651
REG_EXHAUST_FAN_SPEED = 652
REG_SUPPLY_AIRFLOW = 653
REG_EXHAUST_AIRFLOW = 654
REG_DEVICE_FILTER_REMAINING = 655
REG_OUTDOOR_FILTER_REMAINING = 656
REG_ROOM_FILTER_REMAINING = 657

REG_ROOM_TEMPERATURE = 700
REG_EXTERNAL_ROOM_TEMPERATURE = 701
REG_OUTDOOR_BEFORE_EHX_TEMPERATURE = 702
REG_AIR_INTAKE_TEMPERATURE = 703
REG_SUPPLY_AIR_TEMPERATURE = 704
REG_EXTRACT_AIR_TEMPERATURE = 705
REG_EXHAUST_AIR_TEMPERATURE = 706
REG_BUS_ROOM_TEMPERATURE = 707  # write-only

REG_EXTRACT_AIR_HUMIDITY = 750
REG_HUMIDITY_SENSOR = 751  # 751-754
REG_CO2_SENSOR = 755  # 755-758
REG_VOC_SENSOR = 759  # 759-762
REG_BUS_HUMIDITY = 763  # write-only
REG_BUS_AIR_QUALITY = 764  # write-only

REG_SUPPLY_FAN_RUNNING = 800
REG_EXHAUST_FAN_RUNNING = 801
REG_SUMMER_BYPASS = 802
REG_PTC_HEATER = 803
REG_BASE_BOARD_CONTACT = 804
REG_REHEATING_RELAY = 805
REG_BRINE_PUMP = 806
REG_THREE_WAY_DAMPER = 807
REG_ZONE_DAMPER = 808

REG_HOURS_HUMIDITY_PROTECTION = 850  # u32 pairs 850-869
REG_HOURS_REDUCED = 852
REG_HOURS_NOMINAL = 854
REG_HOURS_INTENSIVE = 856
REG_HOURS_TOTAL = 858
REG_HOURS_REHEATING_RELAY = 860
REG_HOURS_BRINE_PUMP = 862
REG_HOURS_THREE_WAY_DAMPER = 864
REG_HOURS_ZONE_DAMPER = 866
REG_HOURS_SWITCH_CONTACT = 868

REG_FILTER_PRESSURE_LIMIT = 900

# Contiguous blocks read on every poll (start, count). A block the unit rejects
# with a Modbus exception is skipped, the others are still read.
READ_BLOCKS: tuple[tuple[int, int], ...] = (
    (100, 10),  # base settings and clock
    (150, 7),  # ventilation settings (157-159 are reset triggers)
    (300, 3),  # temperature settings
    (350, 24),  # EnOcean wireless sensors
    (401, 4),  # fault and notice bit fields
    (550, 5),  # main control
    (650, 8),  # ventilation status
    (700, 7),  # temperatures
    (750, 13),  # humidity, CO2, VOC
    (800, 9),  # switching states
    (850, 20),  # operating hours
    (900, 1),  # filter monitoring
)

# Registers with the values every Maico KWL reports. A device that answers
# with other values is not taken for a Maico KWL, so nothing is written to it.
IDENTITY_RANGES: dict[int, tuple[int, int]] = {
    REG_LANGUAGE: (0, 3),
    REG_ROOM_TEMPERATURE_SOURCE: (0, 3),
    REG_OPERATING_MODE: (0, 5),
    REG_BOOST_VENTILATION: (0, 1),
    REG_SEASON: (0, 1),
    REG_VENTILATION_LEVEL: (0, 4),
}

# Bus inputs must be written again at least every 10 minutes, or the unit
# falls back to its own sensors.
BUS_REFRESH_SECONDS = 300


@dataclass(frozen=True, slots=True)
class Codec:
    """How a register's raw words map to a real-world value."""

    words: int = 1
    signed: bool = False
    scale: float = 1.0

    def decode(self, words: list[int]) -> float | int:
        """Combine the raw words (High-Word first) into the value."""
        raw = 0
        for word in words[: self.words]:
            raw = (raw << 16) | (word & 0xFFFF)
        bits = 16 * self.words
        if self.signed and raw >= 1 << (bits - 1):
            raw -= 1 << bits
        if self.scale == 1.0:
            return raw
        return round(raw * self.scale, 2)

    def encode(self, value: float) -> list[int]:
        """Turn a real-world value into raw words, High-Word first.

        Raises ValueError for a value the data type cannot hold.
        """
        raw = round(value / self.scale)
        bits = 16 * self.words
        low, high = (
            (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if self.signed else (0, (1 << bits) - 1)
        )
        if not low <= raw <= high:
            raise ValueError(f"{value} does not fit into {bits} bit")
        raw &= (1 << bits) - 1
        return [(raw >> (16 * (self.words - 1 - i))) & 0xFFFF for i in range(self.words)]


U16 = Codec()
S16_TENTHS = Codec(signed=True, scale=0.1)
S16 = Codec(signed=True)
U32 = Codec(words=2)


def read_value(data: dict[int, int], address: int, codec: Codec = U16) -> float | int | None:
    """Decode a value from polled data, None if a word is missing."""
    words = [data.get(address + i) for i in range(codec.words)]
    if any(word is None for word in words):
        return None
    return codec.decode(words)  # type: ignore[arg-type]


def active_bits(value: int, names: dict[int, str]) -> list[str]:
    """Slugs of the set bits, in bit order; undocumented bits as ``bit_<n>``."""
    return [names.get(bit, f"bit_{bit}") for bit in range(32) if value >> bit & 1]


def decode_clock(data: dict[int, int]) -> datetime | None:
    """The unit's local date and time (naive), None if unset or invalid."""
    words = [data.get(REG_CLOCK + i) for i in range(6)]
    if any(word is None for word in words):
        return None
    try:
        return datetime(*words)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def encode_clock(value: datetime) -> list[int]:
    """Words for registers 100-105."""
    return [value.year, value.month, value.day, value.hour, value.minute, value.second]


def identity_problem(data: dict[int, int]) -> str | None:
    """Why the data does not look like a Maico KWL, or None."""
    checked = 0
    for address, (low, high) in IDENTITY_RANGES.items():
        if (value := data.get(address)) is None:
            continue
        checked += 1
        if not low <= value <= high:
            return f"register {address} reads {value}, expected {low} to {high}"
    if not checked:
        return "none of the identifying registers could be read"
    return None


# Heat capacity of air per volume (rho * cp = 1.2 kg/m³ * 1005 J/(kg K)) in Wh/(m³ K).
AIR_HEAT_CAPACITY_WH = 1.2 * 1005 / 3600


def heat_recovery_efficiency(t_intake: float, t_supply: float, t_extract: float) -> float | None:
    """Supply-side temperature ratio in percent, None if not meaningful."""
    span = t_extract - t_intake
    if abs(span) < 3.0:
        # Below a few Kelvin the sensor tolerance dominates the result.
        return None
    return round(max(0.0, min(100.0, (t_supply - t_intake) / span * 100.0)), 1)


def heat_recovery_power(airflow: float, t_intake: float, t_supply: float) -> float:
    """Heat transferred to the supply air in W (negative when cooling)."""
    return round(AIR_HEAT_CAPACITY_WH * airflow * (t_supply - t_intake), 1)
