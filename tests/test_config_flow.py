"""Tests for the config, reconfigure and options flows."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import asynccontextmanager
from unittest.mock import patch

from modbus_connection import ModbusConnectionError
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.maico_kwl.const import CONF_SCAN_INTERVAL, CONF_SLAVE, DOMAIN
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

USER_INPUT = {CONF_HOST: " 192.168.1.50 ", CONF_PORT: 502, CONF_SLAVE: 10}


@pytest.fixture
def patch_flow_unit(mock_unit: MockModbusUnit) -> Generator[MockModbusUnit]:
    """Hand the mock unit to the config flow."""

    @asynccontextmanager
    async def _temporary(hass, params, unit_id):
        yield mock_unit

    with patch("custom_components.maico_kwl.config_flow.async_get_temporary_unit", _temporary):
        yield mock_unit


async def test_user_flow(hass: HomeAssistant, patch_flow_unit: MockModbusUnit) -> None:
    """A Maico KWL is found and set up."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    with patch("custom_components.maico_kwl.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_HOST: "192.168.1.50", CONF_PORT: 502, CONF_SLAVE: 10}
    assert result["options"] == {CONF_SCAN_INTERVAL: 30}
    assert result["result"].unique_id == "192.168.1.50_502_10"


@pytest.mark.parametrize(
    ("setup", "error"),
    [
        (lambda unit: unit.fail_requests(ModbusConnectionError("x")), "cannot_connect"),
        (lambda unit: unit.holding.update({550: 42}), "not_maico"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant, patch_flow_unit: MockModbusUnit, setup, error: str
) -> None:
    """Connection problems and foreign devices are reported."""
    setup(patch_flow_unit)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_already_configured(
    hass: HomeAssistant, patch_flow_unit: MockModbusUnit, config_entry: MockConfigEntry
) -> None:
    """The same unit cannot be added twice."""
    config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure(
    hass: HomeAssistant,
    patch_flow_unit: MockModbusUnit,
    patch_unit: MockModbusUnit,
    config_entry: MockConfigEntry,
) -> None:
    """The connection can be changed."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.60", CONF_PORT: 502, CONF_SLAVE: 10}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert config_entry.data[CONF_HOST] == "192.168.1.60"
    assert config_entry.unique_id == "192.168.1.60_502_10"


async def test_options(
    hass: HomeAssistant, patch_unit: MockModbusUnit, config_entry: MockConfigEntry
) -> None:
    """Options set the interval and bus sources."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_SCAN_INTERVAL: 15, "bus_humidity_entity": "sensor.bath_humidity"},
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {
        CONF_SCAN_INTERVAL: 15,
        "bus_humidity_entity": "sensor.bath_humidity",
    }
    assert config_entry.runtime_data.update_interval.total_seconds() == 15
