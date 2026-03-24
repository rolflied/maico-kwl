"""Config Flow für die Maico KWL Integration."""
from __future__ import annotations

import ipaddress
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _is_valid_host(host: str) -> bool:
    """Prüft ob host eine gültige IP-Adresse oder ein Hostname ist."""
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    # Einfache Hostname-Validierung
    return len(host) > 0 and len(host) <= 253


class MaicoKWLConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config Flow für Maico KWL."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Verarbeitet die Benutzereingabe."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            slave = user_input.get(CONF_SLAVE, DEFAULT_SLAVE)

            if not _is_valid_host(host):
                errors[CONF_HOST] = "invalid_host"
            else:
                await self.async_set_unique_id(f"{host}_{port}_{slave}")
                self._abort_if_unique_id_configured()

                # Kein Verbindungstest hier – die Maico KWL unterstützt nur eine
                # gleichzeitige TCP-Verbindung. Der Coordinator verbindet beim Start.
                return self.async_create_entry(
                    title=f"Maico KWL ({host})",
                    data={**user_input, CONF_HOST: host},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    int, vol.Range(min=1, max=65535)
                ),
                vol.Optional(CONF_SLAVE, default=DEFAULT_SLAVE): vol.All(
                    int, vol.Range(min=1, max=247)
                ),
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                    int, vol.Range(min=5, max=300)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
