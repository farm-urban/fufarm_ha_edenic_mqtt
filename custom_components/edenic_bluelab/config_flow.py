"""Config flow for the Edenic Bluelab integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .api import EdenicApiError, EdenicAuthError, get_devices
from .const import (
    ALARM_MODES,
    CONF_ALARM_MODE,
    CONF_API_KEY,
    CONF_DEVICES,
    CONF_ORG_KEY,
    DEFAULT_ALARM_MODE,
    DOMAIN,
)

_LOG = logging.getLogger(__name__)


class EdenicBluelabConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Edenic Bluelab."""

    VERSION = 1

    def __init__(self) -> None:
        self._org_key: str | None = None
        self._api_key: str | None = None
        self._device_choices: dict[str, dict[str, str]] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Collect organisation credentials and validate them."""
        errors: dict[str, str] = {}
        if user_input is not None:
            org_key = user_input[CONF_ORG_KEY]
            api_key = user_input[CONF_API_KEY]
            await self.async_set_unique_id(org_key)
            self._abort_if_unique_id_configured()

            try:
                devices = await self.hass.async_add_executor_job(
                    get_devices, org_key, api_key
                )
            except EdenicAuthError:
                errors["base"] = "auth"
            except EdenicApiError:
                errors["base"] = "cannot_connect"
            else:
                # Gateways and other non-controller devices come back with no
                # label; only labelled devices (Pro Controllers) are selectable.
                labelled_devices = [d for d in devices if d.get("label")]
                if not labelled_devices:
                    errors["base"] = "no_devices"
                else:
                    self._org_key = org_key
                    self._api_key = api_key
                    self._device_choices = {
                        device["id"]: device for device in labelled_devices
                    }
                    return await self.async_step_devices()

        schema = vol.Schema(
            {
                vol.Required(CONF_ORG_KEY): str,
                vol.Required(CONF_API_KEY): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Let the user pick which discovered devices to track."""
        errors: dict[str, str] = {}
        if user_input is not None:
            selected_ids = user_input[CONF_DEVICES]
            devices = [
                {
                    "id": device_id,
                    "label": self._device_choices[device_id]["label"],
                }
                for device_id in selected_ids
            ]
            return self.async_create_entry(
                title=f"Edenic ({self._org_key})",
                data={
                    CONF_ORG_KEY: self._org_key,
                    CONF_API_KEY: self._api_key,
                    CONF_DEVICES: devices,
                },
            )

        options = {
            device_id: device["label"]
            for device_id, device in self._device_choices.items()
        }
        schema = vol.Schema(
            {
                vol.Required(CONF_DEVICES): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=k, label=v)
                            for k, v in options.items()
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="devices", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> EdenicOptionsFlow:
        """Return the options flow for this handler."""
        return EdenicOptionsFlow(config_entry)


class EdenicOptionsFlow(OptionsFlow):
    """Handle options for an existing Edenic Bluelab entry."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._device_choices: dict[str, dict[str, str]] = {}
        try:
            # Older HA: config_entry is a plain settable attribute.
            # HA >= 2024.11: it's a read-only property managed by the base
            # class once the flow manager attaches hass/handler, so this
            # raises AttributeError and can be safely ignored.
            self.config_entry = config_entry
        except AttributeError:
            pass

    async def async_step_init(self, _user_input: dict[str, Any] | None = None) -> FlowResult:
        """Show a menu to either change settings or manage tracked devices."""
        return self.async_show_menu(
            step_id="init", menu_options=["settings", "devices"]
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage alarm mode and polling interval options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ALARM_MODE,
                    default=current.get(CONF_ALARM_MODE, DEFAULT_ALARM_MODE),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=list(ALARM_MODES),
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    "scan_interval",
                    default=current.get("scan_interval", 65),
                ): int,
            }
        )
        return self.async_show_form(step_id="settings", data_schema=schema)

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Re-fetch devices from Edenic and let the user add/remove tracked ones."""
        errors: dict[str, str] = {}
        current_devices = {
            d["id"]: d["label"] for d in self.config_entry.data[CONF_DEVICES]
        }

        if user_input is not None:
            selected_ids = user_input[CONF_DEVICES]
            devices = [
                {"id": device_id, "label": self._device_choices[device_id]["label"]}
                for device_id in selected_ids
            ]
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_DEVICES: devices},
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        try:
            devices = await self.hass.async_add_executor_job(
                get_devices,
                self.config_entry.data[CONF_ORG_KEY],
                self.config_entry.data[CONF_API_KEY],
            )
        except EdenicAuthError:
            errors["base"] = "auth"
        except EdenicApiError:
            errors["base"] = "cannot_connect"
        else:
            # Always keep already-tracked devices selectable, even if Edenic
            # stops returning them (e.g. temporarily offline), plus any newly
            # discovered labelled devices.
            labelled = {d["id"]: d for d in devices if d.get("label")}
            for device_id, label in current_devices.items():
                labelled.setdefault(device_id, {"id": device_id, "label": label})
            self._device_choices = labelled

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEVICES, default=list(current_devices.keys())
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=device_id, label=device["label"]
                            )
                            for device_id, device in self._device_choices.items()
                        ],
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="devices", data_schema=schema, errors=errors
        )

