"""Tests for stale entity cleanup when alarm_mode or the device list changes."""

from unittest.mock import patch

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.edenic_bluelab.const import DOMAIN

DEVICES = [{"id": "dev-1", "label": "4q3f"}]


async def _setup_entry(hass, options=None):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"org_key": "org-1", "api_key": "key-1", "devices": DEVICES},
        options=options or {},
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


async def test_switching_to_summary_removes_individual_alarm_entities(hass):
    """Individual alarm binary_sensors are removed when alarm_mode -> summary."""
    entry = await _setup_entry(hass, options={"alarm_mode": "all"})
    registry = er.async_get(hass)
    entity_ids = {
        e.unique_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert "dev-1_alarm_ec_low_alarm" in entity_ids
    assert "dev-1_alarm_summary" in entity_ids

    hass.config_entries.async_update_entry(entry, options={"alarm_mode": "summary"})
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
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    entity_ids = {
        e.unique_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)
    }
    assert "dev-1_alarm_ec_low_alarm" not in entity_ids
    assert "dev-1_alarm_summary" in entity_ids
