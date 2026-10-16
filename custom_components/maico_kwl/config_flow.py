"""Config flow for the Maico KWL integration."""

from __future__ import annotations

import logging
from typing import Any

from modbus_connection import ModbusError
import voluptuous as vol

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from . import create_modbus_params
from .const import (
    CONF_BUS_AIR_QUALITY_ENTITY,
    CONF_BUS_HUMIDITY_ENTITY,
    CONF_BUS_TEMPERATURE_ENTITY,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DOMAIN,
)
from .registers import identity_problem

_LOGGER = logging.getLogger(__name__)

# Blocks holding the registers of registers.IDENTITY_RANGES.
IDENTITY_BLOCKS = ((108, 2), (550, 5))


def _box(minimum: int, maximum: int, unit: str | None = None) -> vol.All:
    config = NumberSelectorConfig(min=minimum, max=maximum, mode=NumberSelectorMode.BOX)
    if unit is not None:
        config["unit_of_measurement"] = unit
    return vol.All(NumberSelector(config), vol.Coerce(int))


CONNECTION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): TextSelector(),
        vol.Required(CONF_PORT, default=DEFAULT_PORT): _box(1, 65535),
        vol.Required(CONF_SLAVE, default=DEFAULT_SLAVE): _box(1, 247),
    }
)


async def validate_connection(hass: HomeAssistant, data: dict[str, Any]) -> str | None:
    """Read the identifying registers; return an error key or None."""
    try:
        async with async_get_temporary_unit(
            hass, create_modbus_params(data), data[CONF_SLAVE]
        ) as unit:
            values: dict[int, int] = {}
            for start, count in IDENTITY_BLOCKS:
                words = await unit.read_holding_registers(start, count)
                values.update(zip(range(start, start + count), words, strict=False))
    except (HomeAssistantError, ModbusError):
        _LOGGER.debug("Cannot connect to Maico KWL", exc_info=True)
        return "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected error while connecting to Maico KWL")
        return "unknown"
    if problem := identity_problem(values):
        _LOGGER.warning("Device does not look like a Maico KWL: %s", problem)
        return "not_maico"
    return None


def _normalize(user_input: dict[str, Any]) -> dict[str, Any]:
    return {**user_input, CONF_HOST: user_input[CONF_HOST].strip().lower()}


class MaicoKWLConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Maico KWL."""

    VERSION = 1
    MINOR_VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MaicoKWLOptionsFlow:
        """Return the options flow."""
        return MaicoKWLOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the connection details."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _normalize(user_input)
            await self.async_set_unique_id(
                f"{data[CONF_HOST]}_{data[CONF_PORT]}_{data[CONF_SLAVE]}"
            )
            self._abort_if_unique_id_configured()
            if (error := await validate_connection(self.hass, data)) is None:
                return self.async_create_entry(
                    title=f"{DEFAULT_NAME} ({data[CONF_HOST]})",
                    data=data,
                    options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(CONNECTION_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change host, port or Modbus address."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _normalize(user_input)
            await self.async_set_unique_id(
                f"{data[CONF_HOST]}_{data[CONF_PORT]}_{data[CONF_SLAVE]}"
            )
            for other in self._async_current_entries(include_ignore=False):
                if other.entry_id != entry.entry_id and other.unique_id == self.unique_id:
                    raise AbortFlow("already_configured")
            # The unit takes one TCP connection only: free it before testing.
            was_loaded = entry.state is ConfigEntryState.LOADED
            if was_loaded and not await self.hass.config_entries.async_unload(entry.entry_id):
                errors["base"] = "unknown"
            elif (error := await validate_connection(self.hass, data)) is not None:
                errors["base"] = error
                if was_loaded:
                    await self.hass.config_entries.async_setup(entry.entry_id)
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=self.unique_id,
                    title=f"{DEFAULT_NAME} ({data[CONF_HOST]})",
                    data_updates=data,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                CONNECTION_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )


def _source(device_class: SensorDeviceClass) -> EntitySelector:
    return EntitySelector(EntitySelectorConfig(domain="sensor", device_class=device_class))


class MaicoKWLOptionsFlow(OptionsFlowWithReload):
    """Host, polling interval and the sources of the bus inputs."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the options."""
        entry = self.config_entry
        errors: dict[str, str] = {}
        if user_input is not None:
            options = {k: v for k, v in user_input.items() if k != CONF_HOST}
            host = user_input[CONF_HOST].strip().lower()
            if host == entry.data[CONF_HOST]:
                return self.async_create_entry(data=options)
            if error := await self._async_change_host(host):
                errors["base"] = error
            else:
                return self.async_create_entry(data=options)

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): TextSelector(),
                vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): _box(5, 300, "s"),
                vol.Optional(CONF_BUS_TEMPERATURE_ENTITY): _source(SensorDeviceClass.TEMPERATURE),
                vol.Optional(CONF_BUS_HUMIDITY_ENTITY): _source(SensorDeviceClass.HUMIDITY),
                vol.Optional(CONF_BUS_AIR_QUALITY_ENTITY): _source(SensorDeviceClass.CO2),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema, {CONF_HOST: entry.data[CONF_HOST], **(user_input or entry.options)}
            ),
            errors=errors,
        )

    async def _async_change_host(self, host: str) -> str | None:
        """Test the new host and store it; return an error key or None."""
        entry = self.config_entry
        data = {**entry.data, CONF_HOST: host}
        port = data.get(CONF_PORT, DEFAULT_PORT)
        slave = data.get(CONF_SLAVE, DEFAULT_SLAVE)
        unique_id = f"{host}_{port}_{slave}"
        for other in self.hass.config_entries.async_entries(DOMAIN):
            if other.entry_id != entry.entry_id and other.unique_id == unique_id:
                return "already_configured"
        # The unit takes one TCP connection only: free it before testing.
        was_loaded = entry.state is ConfigEntryState.LOADED
        if was_loaded and not await self.hass.config_entries.async_unload(entry.entry_id):
            return "unknown"
        if (error := await validate_connection(self.hass, data)) is not None:
            if was_loaded:
                await self.hass.config_entries.async_setup(entry.entry_id)
            return error
        self.hass.config_entries.async_update_entry(
            entry, data=data, unique_id=unique_id, title=f"{DEFAULT_NAME} ({host})"
        )
        return None
