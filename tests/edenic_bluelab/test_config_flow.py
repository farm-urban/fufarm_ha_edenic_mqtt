"""Tests for the Edenic Bluelab config flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.edenic_bluelab.api import EdenicAuthError
from custom_components.edenic_bluelab.const import DOMAIN

FAKE_DEVICES = [{"id": "dev-1", "label": "4q3f", "name": "Farm Bluelab"}]

# Real orgs also contain gateways/hubs with no label, which must be filtered
# out before building the device-selection form.
FAKE_DEVICES_WITH_UNLABELLED = FAKE_DEVICES + [
    {"id": "dev-2", "label": None, "name": "Gateway"}
]


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

    with (
        patch(
            "custom_components.edenic_bluelab.coordinator.get_telemetry",
            return_value={},
        ),
        patch(
            "custom_components.edenic_bluelab.coordinator.get_device_attributes",
            return_value={},
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"devices": ["dev-1"]}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["org_key"] == "org-1"
    assert result["data"]["devices"] == [{"id": "dev-1", "label": "4q3f"}]


async def test_devices_step_filters_unlabelled_devices(hass):
    """Gateways/hubs with no label are excluded from the device selector."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.edenic_bluelab.config_flow.get_devices",
        return_value=FAKE_DEVICES_WITH_UNLABELLED,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"org_key": "org-1", "api_key": "key-1"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "devices"
    options = result["data_schema"].schema["devices"].config["options"]
    values = {option["value"] for option in options}
    assert values == {"dev-1"}


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
