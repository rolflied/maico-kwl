"""Maico KWL ventilation unit (Modbus TCP) for Home Assistant."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .bus import MaicoBusFeeder
from .client import MaicoModbusClient
from .const import CONF_SCAN_INTERVAL, CONF_SLAVE, DEFAULT_PORT, DEFAULT_SLAVE, DOMAIN
from .coordinator import MaicoKWLConfigEntry, MaicoKWLCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Entity keys of version 0.1.x (German) -> current keys.
LEGACY_KEYS: dict[str, str] = {
    "aktuelle_lueftungsstufe": "current_ventilation_level",
    "drehzahl_zuluft": "supply_fan_speed",
    "drehzahl_abluft": "exhaust_fan_speed",
    "volumenstrom_zuluft": "supply_airflow",
    "volumenstrom_abluft": "exhaust_airflow",
    "restlaufzeit_geraetefilter": "device_filter_remaining",
    "restlaufzeit_aussenfilter": "outdoor_filter_remaining",
    "restlaufzeit_raumfilter": "room_filter_remaining",
    "temperatur_raum": "room_temperature",
    "temperatur_raum_extern": "external_room_temperature",
    "temperatur_aul_ewt": "outdoor_before_ehx_temperature",
    "temperatur_lufteintritt": "air_intake_temperature",
    "temperatur_zuluft": "supply_air_temperature",
    "temperatur_abluft": "extract_air_temperature",
    "temperatur_fortluft": "exhaust_air_temperature",
    "feuchte_abluft": "extract_air_humidity",
    **{f"feuchte_sensor{n}": f"humidity_sensor_{n}" for n in range(1, 5)},
    **{f"co2_sensor{n}": f"co2_sensor_{n}" for n in range(1, 5)},
    **{f"voc_sensor{n}": f"voc_sensor_{n}" for n in range(1, 5)},
    "betriebsstunden_feuchteschutz": "operating_hours_humidity_protection",
    "betriebsstunden_reduziert": "operating_hours_reduced",
    "betriebsstunden_nenn": "operating_hours_nominal",
    "betriebsstunden_intensiv": "operating_hours_intensive",
    "betriebsstunden_gesamt": "operating_hours_total",
    "waermerueckgewinnung": "heat_recovery_efficiency",
    "ventilator_zuluft": "supply_fan_running",
    "ventilator_abluft": "exhaust_fan_running",
    "sommerbypass": "summer_bypass",
    "ptc_heizregister": "ptc_heater",
    "schaltkontakt_basisplatine": "base_board_contact",
    "relais_nachheizung": "reheating_relay",
    "solltemperatur_raum": "room_temperature_setpoint",
    "abgleich_raumtemperatur": "room_temperature_offset",
    "zuluft_min_temp_kuehlen": "supply_air_min_temperature_cooling",
    "raum_max_temperatur": "room_temperature_max",
    "volumenstrom_reduziert": "airflow_reduced",
    "volumenstrom_nenn": "airflow_nominal",
    "volumenstrom_intensiv": "airflow_intensive",
    "dauer_lueftungsstufe": "ventilation_level_duration",
    "filterintervall_geraet": "device_filter_interval",
    "filterintervall_aussen": "outdoor_filter_interval",
    "filterintervall_raum": "room_filter_interval",
    "filter_druckdifferenz": "filter_pressure_limit",
    "bus_raumtemperatur": "bus_room_temperature",
    "bus_feuchte": "bus_humidity",
    "bus_co2": "bus_air_quality",
    "betriebsart": "operating_mode",
    "lueftungsstufe_soll": "ventilation_level",
    "jahreszeit": "season",
    "raumtemperaturquelle": "room_temperature_source",
    "geraetesprache": "language",
    "stosslüftung": "boost_ventilation",
    "luefterstufe_aus_sperren": "off_level_lock",
    "bde_sperren": "control_panel_lock",
    "filterwechsel_geraet": "reset_device_filter",
    "filterwechsel_aussen": "reset_outdoor_filter",
    "filterwechsel_raum": "reset_room_filter",
    "fehler_reset": "reset_faults",
}


async def async_setup_entry(hass: HomeAssistant, entry: MaicoKWLConfigEntry) -> bool:
    """Set up a Maico KWL from a config entry."""
    client = MaicoModbusClient(
        entry.data[CONF_HOST],
        entry.data.get(CONF_PORT, DEFAULT_PORT),
        entry.data.get(CONF_SLAVE, DEFAULT_SLAVE),
    )
    entry.async_on_unload(client.async_close)

    coordinator = MaicoKWLCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    coordinator.bus = MaicoBusFeeder(hass, entry, coordinator)
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    coordinator.bus.async_start()
    entry.async_on_unload(coordinator.bus.async_stop)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MaicoKWLConfigEntry) -> bool:
    """Unload a config entry; the connection is closed by async_on_unload."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the repair issues of a deleted entry."""
    issue_registry = ir.async_get(hass)
    for domain, issue_id in list(issue_registry.issues):
        if domain == DOMAIN and issue_id.endswith(entry.entry_id):
            ir.async_delete_issue(hass, DOMAIN, issue_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entries of older versions."""
    if entry.version > 1:
        return False

    if entry.minor_version < 2:
        # 0.1.x: German entity keys, scan interval in data.
        prefix = f"{entry.entry_id}_"

        @callback
        def _migrate(entity: er.RegistryEntry) -> dict[str, Any] | None:
            if not entity.unique_id.startswith(prefix):
                return None
            new_key = LEGACY_KEYS.get(entity.unique_id.removeprefix(prefix))
            if new_key is None:
                return None
            return {"new_unique_id": prefix + new_key}

        await er.async_migrate_entries(hass, entry.entry_id, _migrate)

        data = dict(entry.data)
        options = dict(entry.options)
        if CONF_SCAN_INTERVAL in data:
            options.setdefault(CONF_SCAN_INTERVAL, data.pop(CONF_SCAN_INTERVAL))
        hass.config_entries.async_update_entry(entry, data=data, options=options, minor_version=2)
        _LOGGER.info("Migrated Maico KWL entry %s to version 1.2", entry.entry_id)

    return True
