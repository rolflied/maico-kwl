"""Constants for the Maico KWL integration."""

from typing import Final

DOMAIN: Final = "maico_kwl"
MANUFACTURER: Final = "Maico"
DEFAULT_NAME: Final = "Maico KWL"
DEFAULT_PORT: Final = 502
DEFAULT_SLAVE: Final = 10
DEFAULT_SCAN_INTERVAL: Final = 30

CONF_SLAVE: Final = "slave"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Options: Home Assistant entities whose values are fed to the bus inputs.
CONF_BUS_TEMPERATURE_ENTITY: Final = "bus_temperature_entity"
CONF_BUS_HUMIDITY_ENTITY: Final = "bus_humidity_entity"
CONF_BUS_AIR_QUALITY_ENTITY: Final = "bus_air_quality_entity"
