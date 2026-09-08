"""The Edenic Bluelab integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    ALARM_MODE_ALL,
    ALARM_MODE_INDIVIDUAL,
    ALARM_MODE_SUMMARY,
    ALARMS,
    CONF_ALARM_MODE,
    CONF_DEVICES,
    DEFAULT_ALARM_MODE,
    DOMAIN,
    SENSORS,
)
from .coordinator import EdenicCoordinator

PLATFORMS = ["sensor", "binary_sensor"]


def _expected_unique_ids(devices: list[dict[str, str]], alarm_mode: str) -> set[str]:
    """Return the unique_ids that should exist for the current alarm_mode."""
    ids: set[str] = set()
    for device in devices:
        device_id = device["id"]
        for sensor in SENSORS:
            ids.add(f"{device_id}_{sensor.key}")
        if alarm_mode in (ALARM_MODE_INDIVIDUAL, ALARM_MODE_ALL):
            for alarm in ALARMS:
                ids.add(f"{device_id}_{alarm.key.replace('.', '_')}")
        if alarm_mode in (ALARM_MODE_SUMMARY, ALARM_MODE_ALL):
            ids.add(f"{device_id}_alarm_summary")
    return ids


def _async_remove_stale_entities(
    hass: HomeAssistant, entry: ConfigEntry, devices: list[dict[str, str]], alarm_mode: str
) -> None:
    """Remove entities left behind by a previous alarm_mode (e.g. all -> summary)."""
    expected = _expected_unique_ids(devices, alarm_mode)
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.unique_id not in expected:
            registry.async_remove(entity.entity_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Edenic Bluelab from a config entry."""
    devices = entry.data[CONF_DEVICES]
    scan_interval = entry.options.get("scan_interval")
    alarm_mode = entry.options.get(CONF_ALARM_MODE, DEFAULT_ALARM_MODE)
    coordinator = EdenicCoordinator(hass, entry, devices, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    _async_remove_stale_entities(hass, entry, devices, alarm_mode)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change (e.g. alarm_mode, scan_interval)."""
    await hass.config_entries.async_reload(entry.entry_id)
