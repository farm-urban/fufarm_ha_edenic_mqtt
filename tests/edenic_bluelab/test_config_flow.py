"""Tests for the Edenic Bluelab config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.edenic_bluelab.api import EdenicAuthError
from custom_components.edenic_bluelab.const import DOMAIN

FAKE_DEVICES = [{"id": "dev-1", "label": "4q3f", "name": "Farm Bluelab"}]


async def test_user_step_shows_form(hass):
    """The first step of the flow shows the org/API key form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_full_flow_creates_entry(hass):
    """Valid credentials followed by a device selection creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.edenic_bluelab.config_flow.get_devices",
        return_value=FAKE_DEVICES,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"org_key": "org-1", "api_key": "key-1"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "devices"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"devices": ["dev-1"]}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["org_key"] == "org-1"
    assert result["data"]["devices"] == FAKE_DEVICES


async def test_invalid_auth_shows_error(hass):
    """An auth failure re-shows the user form with an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.edenic_bluelab.config_flow.get_devices",
        side_effect=EdenicAuthError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"org_key": "org-1", "api_key": "bad-key"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "auth"}
