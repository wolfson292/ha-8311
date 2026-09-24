"""Config flow for the 8311 ONT integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import selector
import voluptuous as vol

from . import create_client
from .api import OntAuthError, OntDeviceInfo, OntError
from .const import (
    CONF_VERIFY_SSL,
    DEFAULT_HOST,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_USERNAME,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from .coordinator import OntConfigEntry

_LOGGER = logging.getLogger(__name__)

PASSWORD_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
)


def _user_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, DEFAULT_HOST)): str,
            vol.Required(
                CONF_USERNAME, default=defaults.get(CONF_USERNAME, DEFAULT_USERNAME)
            ): str,
            vol.Optional(CONF_PASSWORD, default=""): PASSWORD_SELECTOR,
            vol.Required(
                CONF_VERIFY_SSL, default=defaults.get(CONF_VERIFY_SSL, False)
            ): bool,
        }
    )


class Ont8311ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for 8311 ONT."""

    VERSION = 1

    async def _async_validate(
        self, data: dict[str, Any], errors: dict[str, str]
    ) -> OntDeviceInfo | None:
        client = create_client(self.hass, data)
        try:
            await client.login()
            return await client.get_device_info()
        except OntAuthError:
            errors["base"] = "invalid_auth"
        except OntError as err:
            _LOGGER.debug("Cannot connect to %s: %s", data[CONF_HOST], err)
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error validating ONT")
            errors["base"] = "unknown"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input.setdefault(CONF_PASSWORD, "")
            info = await self._async_validate(user_input, errors)
            if info is not None:
                await self.async_set_unique_id(info.serial_number or user_input[CONF_HOST])
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(
                    title=info.hostname or f"8311 ONT ({user_input[CONF_HOST]})",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input or {}),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change host or credentials."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input.setdefault(CONF_PASSWORD, "")
            info = await self._async_validate(user_input, errors)
            if info is not None:
                await self.async_set_unique_id(info.serial_number or user_input[CONF_HOST])
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(entry, data=user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_user_schema(user_input or entry.data),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for new credentials."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            data.setdefault(CONF_PASSWORD, "")
            if await self._async_validate(data, errors) is not None:
                return self.async_update_reload_and_abort(entry, data=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=entry.data.get(CONF_USERNAME, DEFAULT_USERNAME)
                    ): str,
                    vol.Optional(CONF_PASSWORD, default=""): PASSWORD_SELECTOR,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: OntConfigEntry) -> OntOptionsFlow:
        """Return the options flow."""
        return OntOptionsFlow()


class OntOptionsFlow(OptionsFlowWithReload):
    """Options for polling interval."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=3600)),
                }
            ),
        )
