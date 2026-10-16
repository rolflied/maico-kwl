"""Feed the unit's write-only bus inputs (707, 763, 764).

The unit only uses a bus value for 10 minutes, so every known value is written
again every few minutes. Values come from the bus number entities or from
Home Assistant entities chosen in the options.

Writes are throttled: at most one per input every 30 s, and only while the
connection is up. A value is written when it differs enough from the last
written one (25 ppm for CO2) or when nothing was written for 5 minutes. A failed
write is not queued; the next opportunity sends whatever value is newest.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
import time

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import (
    CONF_BUS_AIR_QUALITY_ENTITY,
    CONF_BUS_HUMIDITY_ENTITY,
    CONF_BUS_TEMPERATURE_ENTITY,
)
from .coordinator import MaicoKWLConfigEntry, MaicoKWLCoordinator
from .registers import (
    BUS_MIN_WRITE_INTERVAL_SECONDS,
    BUS_REFRESH_SECONDS,
    REG_BUS_AIR_QUALITY,
    REG_BUS_HUMIDITY,
    REG_BUS_ROOM_TEMPERATURE,
    S16_TENTHS,
    U16,
    Codec,
)

_LOGGER = logging.getLogger(__name__)


def _temperature(state: State) -> float | None:
    """Temperature in °C."""
    value = float(state.state)
    unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT, UnitOfTemperature.CELSIUS)
    if unit not in TemperatureConverter.VALID_UNITS:
        return None
    return TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)


def _humidity(state: State) -> float | None:
    """Relative humidity in %."""
    value = float(state.state)
    return value if 0 <= value <= 100 else None


def _air_quality(state: State) -> float | None:
    """CO2 / air quality in ppm."""
    value = float(state.state)
    if state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfRatio.PARTS_PER_BILLION:
        value /= 1000
    elif state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) not in (
        None,
        UnitOfRatio.PARTS_PER_MILLION,
    ):
        return None
    return value


@dataclass(frozen=True, slots=True)
class BusInput:
    """One write-only bus input of the unit."""

    address: int
    codec: Codec
    minimum: float
    maximum: float
    option: str
    convert: Callable[[State], float | None]
    # A value is only written again if it moved at least this much.
    min_change: float = 0.0


BUS_MIN_CHANGE_CO2_PPM = 25.0

BUS_INPUTS: tuple[BusInput, ...] = (
    BusInput(
        REG_BUS_ROOM_TEMPERATURE,
        S16_TENTHS,
        -30.0,
        120.0,
        CONF_BUS_TEMPERATURE_ENTITY,
        _temperature,
    ),
    BusInput(REG_BUS_HUMIDITY, U16, 0.0, 100.0, CONF_BUS_HUMIDITY_ENTITY, _humidity),
    BusInput(
        REG_BUS_AIR_QUALITY,
        U16,
        0.0,
        5000.0,
        CONF_BUS_AIR_QUALITY_ENTITY,
        _air_quality,
        min_change=BUS_MIN_CHANGE_CO2_PPM,
    ),
)
BUS_INPUTS_BY_ADDRESS = {bus.address: bus for bus in BUS_INPUTS}


class MaicoBusFeeder:
    """Keeps the bus inputs of one unit supplied."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MaicoKWLConfigEntry,
        coordinator: MaicoKWLCoordinator,
    ) -> None:
        """Initialize the feeder."""
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self._listeners: list[Callable[[], None]] = []
        # address -> (value, monotonic time) of the last successful write.
        self._written: dict[int, tuple[float, float]] = {}

    def source_entity(self, address: int) -> str | None:
        """The entity configured as source of a bus input."""
        return self.entry.options.get(BUS_INPUTS_BY_ADDRESS[address].option) or None

    @callback
    def async_start(self) -> None:
        """Track the source entities and refresh the inputs periodically."""
        sources = {
            entity_id: bus for bus in BUS_INPUTS if (entity_id := self.source_entity(bus.address))
        }
        if sources:
            self._listeners.append(
                async_track_state_change_event(self.hass, list(sources), self._async_source_changed)
            )
            for entity_id, bus in sources.items():
                if (state := self.hass.states.get(entity_id)) is not None:
                    self._take(bus, state)
        self._listeners.append(
            async_track_time_interval(
                self.hass,
                self._async_refresh,
                timedelta(seconds=BUS_MIN_WRITE_INTERVAL_SECONDS),
                name="maico_kwl bus refresh",
            )
        )
        if self.coordinator.bus_values:
            self.entry.async_create_background_task(
                self.hass, self._async_refresh(), "maico_kwl bus initial write"
            )

    @callback
    def async_stop(self) -> None:
        """Stop all listeners."""
        while self._listeners:
            self._listeners.pop()()

    def _take(self, bus: BusInput, state: State) -> bool:
        """Store the value of a source state, True if it changed."""
        if state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return False
        try:
            value = bus.convert(state)
        except ValueError:
            value = None
        if value is None:
            _LOGGER.debug("Ignoring %s for bus input %d", state, bus.address)
            return False
        value = max(bus.minimum, min(bus.maximum, value))
        if self.coordinator.bus_values.get(bus.address) == value:
            return False
        self.coordinator.bus_values[bus.address] = value
        return True

    @callback
    def _async_source_changed(self, event: Event[EventStateChangedData]) -> None:
        """Remember a changed source value and write it if the throttle allows."""
        if (state := event.data["new_state"]) is None:
            return
        for bus in BUS_INPUTS:
            if self.source_entity(bus.address) == state.entity_id and self._take(bus, state):
                self.entry.async_create_background_task(
                    self.hass, self._async_write(bus), "maico_kwl bus write"
                )

    async def async_set(self, address: int, value: float) -> None:
        """Set a bus input from a number entity and write it right away."""
        bus = BUS_INPUTS_BY_ADDRESS[address]
        self.coordinator.bus_values[address] = value
        await self._async_write(bus, raise_on_error=True, force=True)

    def _is_due(self, bus: BusInput, value: float) -> bool:
        """Whether the throttle allows writing this value now."""
        if not self.coordinator.client.connected:
            return False
        if (last := self._written.get(bus.address)) is None:
            return True
        last_value, last_time = last
        age = time.monotonic() - last_time
        if age < BUS_MIN_WRITE_INTERVAL_SECONDS:
            return False
        return age >= BUS_REFRESH_SECONDS or abs(value - last_value) >= max(bus.min_change, 1e-9)

    async def _async_write(
        self, bus: BusInput, raise_on_error: bool = False, force: bool = False
    ) -> None:
        value = self.coordinator.bus_values.get(bus.address)
        if value is None or not (force or self._is_due(bus, value)):
            return
        try:
            await self.coordinator.async_write(bus.address, bus.codec.encode(value))
        except HomeAssistantError as err:
            if raise_on_error:
                raise
            _LOGGER.debug("Writing bus input %d failed: %s", bus.address, err)
        else:
            self._written[bus.address] = (value, time.monotonic())
            self.coordinator.async_update_listeners()

    async def _async_refresh(self, _now: object = None) -> None:
        """Write what is due: changed values and those about to be forgotten."""
        for bus in BUS_INPUTS:
            await self._async_write(bus)
