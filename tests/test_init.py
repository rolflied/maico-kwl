"""Tests for setup, entities and writes."""

from __future__ import annotations

from collections.abc import Generator
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.maico_kwl.client import MaicoConnectionError
from custom_components.maico_kwl.const import CONF_SCAN_INTERVAL, CONF_SLAVE, DOMAIN
from custom_components.maico_kwl.diagnostics import async_get_config_entry_diagnostics
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util

from .conftest import FakeUnit, WriteEvent, busy, illegal_address


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _writes(unit: FakeUnit) -> list[WriteEvent]:
    events: list[WriteEvent] = []
    unit.on_write(events.append)
    return events


async def test_setup_and_states(
    hass: HomeAssistant, patch_unit: FakeUnit, config_entry: MockConfigEntry
) -> None:
    """Entities reflect the registers."""
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    assert hass.states.get("sensor.maico_kwl_co2_sensor_1").state == "548"
    assert hass.states.get("sensor.maico_kwl_extract_air_humidity").state == "54"
    assert hass.states.get("sensor.maico_kwl_air_intake_temperature").state == "-5.0"
    assert hass.states.get("sensor.maico_kwl_operating_hours_total").state == "67851"
    assert hass.states.get("sensor.maico_kwl_current_ventilation_level").state == "nominal"
    assert hass.states.get("sensor.maico_kwl_heat_recovery_efficiency").state == "81.5"
    assert hass.states.get("select.maico_kwl_operating_mode").state == "manual"
    assert hass.states.get("number.maico_kwl_room_temperature_offset").state == "-0.2"
    assert hass.states.get("number.maico_kwl_minimum_supply_air_temperature_cooling").state == "14"
    assert hass.states.get("binary_sensor.maico_kwl_device_filter_change_due").state == "on"

    fan = hass.states.get("fan.maico_kwl")
    assert fan.state == "on"
    assert fan.attributes["percentage"] == 75
    assert fan.attributes["preset_mode"] == "manual"

    # Sensors without hardware start disabled; fitted ones enabled.
    registry = er.async_get(hass)
    assert registry.async_get("sensor.maico_kwl_co2_sensor_2").disabled
    assert registry.async_get("sensor.maico_kwl_outdoor_filter_remaining").disabled
    assert not registry.async_get("sensor.maico_kwl_co2_sensor_1").disabled

    # The device filter notice raises a repair issue.
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"filter_due_device_{config_entry.entry_id}")


async def test_writes_use_fc16(
    hass: HomeAssistant, patch_unit: FakeUnit, config_entry: MockConfigEntry
) -> None:
    """Every write goes out as Write Multiple Registers."""
    await _setup(hass, config_entry)
    writes = _writes(patch_unit)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.maico_kwl_ventilation_level", "option": "intensive"},
        blocking=True,
    )
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.maico_kwl_room_temperature_setpoint", "value": 22.5},
        blocking=True,
    )
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.maico_kwl_boost_ventilation"}, blocking=True
    )
    assert [(w.address, w.values, w.function_code) for w in writes] == [
        (554, [4], 0x10),
        (553, [225], 0x10),
        (551, [1], 0x10),
    ]
    assert hass.states.get("select.maico_kwl_ventilation_level").state == "intensive"


async def test_fan(
    hass: HomeAssistant, patch_unit: FakeUnit, config_entry: MockConfigEntry
) -> None:
    """Speed switches to manual, off sets the mode off, on restores it."""
    patch_unit.holding[550] = 3  # auto sensor
    await _setup(hass, config_entry)
    writes = _writes(patch_unit)

    await hass.services.async_call(
        "fan", "set_percentage", {"entity_id": "fan.maico_kwl", "percentage": 50}, blocking=True
    )
    assert [(w.address, w.values) for w in writes] == [(550, [1]), (554, [2])]

    writes.clear()
    await hass.services.async_call("fan", "turn_off", {"entity_id": "fan.maico_kwl"}, blocking=True)
    assert [(w.address, w.values) for w in writes] == [(550, [0])]
    assert hass.states.get("fan.maico_kwl").state == "off"

    writes.clear()
    await hass.services.async_call("fan", "turn_on", {"entity_id": "fan.maico_kwl"}, blocking=True)
    assert [(w.address, w.values) for w in writes] == [(550, [1])]

    writes.clear()
    await hass.services.async_call(
        "fan",
        "set_preset_mode",
        {"entity_id": "fan.maico_kwl", "preset_mode": "auto_time"},
        blocking=True,
    )
    assert [(w.address, w.values) for w in writes] == [(550, [2])]


async def test_write_error(
    hass: HomeAssistant, patch_unit: FakeUnit, config_entry: MockConfigEntry
) -> None:
    """A failed write is reported to the caller."""
    await _setup(hass, config_entry)
    patch_unit.fail_write(551, MaicoConnectionError("gone"))
    with pytest.raises(HomeAssistantError, match="551"):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.maico_kwl_boost_ventilation"},
            blocking=True,
        )


async def test_unsupported_block(
    hass: HomeAssistant, patch_unit: FakeUnit, config_entry: MockConfigEntry
) -> None:
    """A rejected block is skipped, its entities become unavailable."""
    patch_unit.fail_read(350, illegal_address())
    await _setup(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.unsupported_blocks == {(350, 24)}
    assert hass.states.get("sensor.maico_kwl_co2_sensor_1").state == "548"


async def _poll(hass: HomeAssistant, cycle: int) -> None:
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31 * cycle))
    await hass.async_block_till_done()


async def test_connection_lost(
    hass: HomeAssistant,
    patch_unit: FakeUnit,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Values are kept for two failed cycles, then unavailable; one warning per outage."""
    await _setup(hass, config_entry)
    patch_unit.fail_requests(MaicoConnectionError("down"))
    patch_unit.reads.clear()

    for cycle in (1, 2):
        await _poll(hass, cycle)
        assert hass.states.get("sensor.maico_kwl_supply_fan_speed").state == "1239"
    # A failed cycle stops at the first request instead of trying every block.
    assert len(patch_unit.reads) == 2

    await _poll(hass, 3)
    assert hass.states.get("sensor.maico_kwl_supply_fan_speed").state == STATE_UNAVAILABLE
    await _poll(hass, 4)
    warnings = [
        r
        for r in caplog.records
        if r.levelname == "WARNING" and r.name.startswith("custom_components.maico_kwl")
    ]
    assert len(warnings) == 1

    patch_unit.fail_requests(None)
    await _poll(hass, 5)
    assert hass.states.get("sensor.maico_kwl_supply_fan_speed").state == "1239"
    assert "answers again after 4 failed polls" in caplog.text


async def test_first_poll_fails(
    hass: HomeAssistant, patch_unit: FakeUnit, config_entry: MockConfigEntry
) -> None:
    """Without any data the setup is retried."""
    patch_unit.fail_requests(MaicoConnectionError("down"))
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_few_requests(
    hass: HomeAssistant, patch_unit: FakeUnit, config_entry: MockConfigEntry
) -> None:
    """The 12 register blocks are read with 5 requests."""
    await _setup(hass, config_entry)
    assert len(patch_unit.reads) == 5
    assert all(count <= 125 for _, count in patch_unit.reads)


async def test_unchanged_poll_writes_no_states(
    hass: HomeAssistant, patch_unit: FakeUnit, config_entry: MockConfigEntry
) -> None:
    """Only entities whose registers changed get a new state."""
    await _setup(hass, config_entry)
    changed: list[str] = []
    hass.bus.async_listen(
        "state_changed",
        lambda event: changed.append(event.data["entity_id"]),
    )
    await _poll(hass, 1)
    assert changed == []

    patch_unit.holding[651] = 1300  # supply fan speed
    await _poll(hass, 2)
    assert changed == ["sensor.maico_kwl_supply_fan_speed"]


async def test_not_maico(
    hass: HomeAssistant, patch_unit: FakeUnit, config_entry: MockConfigEntry
) -> None:
    """A device with foreign values is not set up."""
    patch_unit.holding[550] = 77
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_fault_issue(
    hass: HomeAssistant, patch_unit: FakeUnit, config_entry: MockConfigEntry
) -> None:
    """An active fault raises an issue and is decoded."""
    patch_unit.holding[402] = 0b11
    await _setup(hass, config_entry)
    state = hass.states.get("sensor.maico_kwl_active_faults")
    assert state.state == "2"
    assert state.attributes["active"] == ["supply_fan", "exhaust_fan"]
    assert hass.states.get("binary_sensor.maico_kwl_fault").state == "on"
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"fault_{config_entry.entry_id}")


class Clock:
    """A settable replacement for time.monotonic."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Generator[Clock]:
    """Control the clock the bus throttle uses."""
    clock = Clock()
    with patch("custom_components.maico_kwl.bus.time", SimpleNamespace(monotonic=clock)):
        yield clock


def _bus_writes(writes: list[WriteEvent], address: int) -> list[list[int]]:
    return [w.values for w in writes if w.address == address]


async def _fire(hass: HomeAssistant, clock: Clock, seconds: float) -> None:
    clock.now += seconds
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=clock.now - 1000))
    await hass.async_block_till_done()


async def test_bus_feed(
    hass: HomeAssistant, patch_unit: FakeUnit, config_entry: MockConfigEntry, clock: Clock
) -> None:
    """A source entity feeds the bus input; it is throttled and repeated."""
    hass.states.async_set(
        "sensor.living_room",
        "68.0",
        {"unit_of_measurement": "°F", "device_class": "temperature"},
    )
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry,
        options={**config_entry.options, "bus_temperature_entity": "sensor.living_room"},
    )
    writes = _writes(patch_unit)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert _bus_writes(writes, 707) == [[200]]
    assert hass.states.get("number.maico_kwl_room_temperature_bus").state == "20.0"

    # A change within 30 s waits; the next tick sends the newest value only.
    hass.states.async_set(
        "sensor.living_room",
        "70.0",
        {"unit_of_measurement": "°F", "device_class": "temperature"},
    )
    hass.states.async_set(
        "sensor.living_room",
        "71.6",
        {"unit_of_measurement": "°F", "device_class": "temperature"},
    )
    await hass.async_block_till_done()
    assert _bus_writes(writes, 707) == [[200]]
    await _fire(hass, clock, 31)
    assert _bus_writes(writes, 707) == [[200], [220]]

    # Unchanged values are repeated after 5 minutes.
    await _fire(hass, clock, 120)
    assert _bus_writes(writes, 707) == [[200], [220]]
    await _fire(hass, clock, 181)
    assert _bus_writes(writes, 707) == [[200], [220], [220]]


async def test_co2_write_is_throttled(
    hass: HomeAssistant, patch_unit: FakeUnit, config_entry: MockConfigEntry, clock: Clock
) -> None:
    """CO2 is written for >= 25 ppm, at most every 30 s, else every 5 minutes."""
    attrs = {"unit_of_measurement": "ppm", "device_class": "carbon_dioxide"}
    hass.states.async_set("sensor.co2", "500", attrs)
    config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        config_entry, options={**config_entry.options, "bus_air_quality_entity": "sensor.co2"}
    )
    writes = _writes(patch_unit)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert _bus_writes(writes, 764) == [[500]]

    # Big jump right away: too soon.
    hass.states.async_set("sensor.co2", "600", attrs)
    await hass.async_block_till_done()
    assert _bus_writes(writes, 764) == [[500]]

    # After 30 s it goes out; small drifts after that do not.
    await _fire(hass, clock, 31)
    assert _bus_writes(writes, 764) == [[500], [600]]
    hass.states.async_set("sensor.co2", "620", attrs)
    await _fire(hass, clock, 31)
    assert _bus_writes(writes, 764) == [[500], [600]]

    # The 5 minute repeat sends the newest value.
    await _fire(hass, clock, 270)
    assert _bus_writes(writes, 764) == [[500], [600], [620]]

    # Nothing is written, and nothing queued, while the connection is down.
    patch_unit.connected = False
    hass.states.async_set("sensor.co2", "900", attrs)
    await _fire(hass, clock, 40)
    assert _bus_writes(writes, 764) == [[500], [600], [620]]
    patch_unit.connected = True
    await _fire(hass, clock, 31)
    assert _bus_writes(writes, 764) == [[500], [600], [620], [900]]

    # A failed write is not queued; the next tick sends the newest value.
    patch_unit.fail_write(764, MaicoConnectionError("x"))
    hass.states.async_set("sensor.co2", "1000", attrs)
    await _fire(hass, clock, 31)
    hass.states.async_set("sensor.co2", "1100", attrs)
    patch_unit._write_errors.clear()
    await _fire(hass, clock, 31)
    assert _bus_writes(writes, 764)[-1] == [1100]


async def test_migration(hass: HomeAssistant, patch_unit: FakeUnit) -> None:
    """0.1.x entries keep their entities under the new keys."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        unique_id="192.168.1.50_502_10",
        data={CONF_HOST: "192.168.1.50", CONF_PORT: 502, CONF_SLAVE: 10, CONF_SCAN_INTERVAL: 15},
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "select",
        DOMAIN,
        f"{entry.entry_id}_betriebsart",
        config_entry=entry,
        suggested_object_id="maico_kwl_betriebsart",
    )
    switch = registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{entry.entry_id}_stosslüftung",
        config_entry=entry,
        suggested_object_id="maico_kwl_stosslueftung",
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 2
    assert entry.options[CONF_SCAN_INTERVAL] == 15
    assert CONF_SCAN_INTERVAL not in entry.data
    assert registry.async_get(old.entity_id).unique_id == f"{entry.entry_id}_operating_mode"
    assert registry.async_get(switch.entity_id).unique_id == f"{entry.entry_id}_boost_ventilation"
    assert hass.states.get(old.entity_id).state == "manual"


async def test_diagnostics(
    hass: HomeAssistant, patch_unit: FakeUnit, config_entry: MockConfigEntry
) -> None:
    """Diagnostics carry the raw registers and redact the host."""
    await _setup(hass, config_entry)
    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diag["registers"]["550"] == 1
    assert diag["notices"] == ["device_filter_due"]
    assert diag["entry"]["data"][CONF_HOST] == "**REDACTED**"


async def test_all_entities_named(
    hass: HomeAssistant, patch_unit: FakeUnit, config_entry: MockConfigEntry
) -> None:
    """Every entity gets a translated name (only the fan uses the device name)."""
    await _setup(hass, config_entry)
    entries = er.async_entries_for_config_entry(er.async_get(hass), config_entry.entry_id)
    assert len(entries) > 100
    unnamed = [e.entity_id for e in entries if e.original_name is None]
    assert unnamed == ["fan.maico_kwl"]


async def test_busy_block_is_retried(
    hass: HomeAssistant, patch_unit: FakeUnit, config_entry: MockConfigEntry
) -> None:
    """A busy unit fails the cycle but does not drop the block for good."""
    await _setup(hass, config_entry)
    patch_unit.fail_read(650, busy())
    for cycle in (1, 2, 3):
        await _poll(hass, cycle)
    assert hass.states.get("sensor.maico_kwl_supply_fan_speed").state == STATE_UNAVAILABLE
    assert not config_entry.runtime_data.unsupported_blocks

    patch_unit.fail_read(650, None)
    await _poll(hass, 4)
    assert hass.states.get("sensor.maico_kwl_supply_fan_speed").state == "1239"


async def test_ships_brand_images(hass: HomeAssistant) -> None:
    """Home Assistant finds the bundled icon."""
    integration = await async_get_integration(hass, DOMAIN)
    assert integration.has_branding
