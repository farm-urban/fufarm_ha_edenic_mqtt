"""Tests for the Edenic Bluelab options flow (settings + device management)."""

from unittest.mock import patch

from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edenic_bluelab.const import DOMAIN

EXISTING_DEVICES = [{"id": "dev-1", "label": "4q3f"}]
DISCOVERED_DEVICES = [
    {"id": "dev-1", "label": "4q3f", "name": "n/a"},
    {"id": "dev-2", "label": "52rf", "name": "n/a"},
]


async def _setup_entry(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"org_key": "org-1", "api_key": "key-1", "devices": EXISTING_DEVICES},
    )
    entry.add_to_hass(hass)
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
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_options_init_shows_menu(hass):
    """The options flow's first step is a menu of settings/devices."""
    entry = await _setup_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.MENU
    assert set(result["menu_options"]) == {"settings", "devices"}


async def test_options_devices_step_adds_new_device(hass):
    """Selecting a newly discovered device updates entry.data and reloads it."""
    entry = await _setup_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    with patch(
        "custom_components.edenic_bluelab.config_flow.get_devices",
        return_value=DISCOVERED_DEVICES,
    ):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "devices"}
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
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"devices": ["dev-1", "dev-2"]}
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.data["devices"] == [
        {"id": "dev-1", "label": "4q3f"},
        {"id": "dev-2", "label": "52rf"},
    ]
