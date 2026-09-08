"""Sensor platform for the Edenic Bluelab integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ALARM_MODE_ALL,
    ALARM_MODE_SUMMARY,
    ALARMS,
    CONF_ALARM_MODE,
    DEFAULT_ALARM_MODE,
    DOMAIN,
    NO_ACTIVE_ALARMS,
    SENSORS,
)
from .coordinator import EdenicCoordinator


def _device_info(device: dict[str, str]) -> DeviceInfo:
    # device["name"] is an opaque org_id__mac string from the Edenic API;
    # the label (e.g. "4q3f") is the human-friendly identifier.
    return DeviceInfo(
        identifiers={(DOMAIN, device["id"])},
        name=device["label"],
        manufacturer="Bluelab",
        model="Pro Controller",
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up telemetry and alarm-summary sensors for each configured device."""
    coordinator: EdenicCoordinator = hass.data[DOMAIN][entry.entry_id]
    alarm_mode = entry.options.get(CONF_ALARM_MODE, DEFAULT_ALARM_MODE)

    entities: list[SensorEntity] = []
    for device in coordinator.devices:
        for sensor in SENSORS:
            entities.append(EdenicTelemetrySensor(coordinator, device, sensor))
        if alarm_mode in (ALARM_MODE_SUMMARY, ALARM_MODE_ALL):
            entities.append(EdenicAlarmSummarySensor(coordinator, device))

    async_add_entities(entities)


class EdenicTelemetrySensor(CoordinatorEntity[EdenicCoordinator], SensorEntity):
    """Represents a single telemetry value (pH, temperature, EC) for a device."""

    def __init__(self, coordinator, device, sensor_def) -> None:
        super().__init__(coordinator)
        self._device_id = device["id"]
        self._sensor_def = sensor_def
        self._attr_name = f"{sensor_def.name} {device['label']}"
        self._attr_unique_id = f"{self._device_id}_{sensor_def.key}"
        self._attr_device_class = sensor_def.device_class
        self._attr_native_unit_of_measurement = sensor_def.unit
        self._attr_device_info = _device_info(device)

    @property
    def native_value(self):
        """Return the latest telemetry value for this sensor."""
        data = self.coordinator.data.get(self._device_id)
        if data is None:
            return None
        readings = data.telemetry.get(self._sensor_def.telemetry_key)
        if not readings:
            return None
        return readings[0]["value"]


class EdenicAlarmSummarySensor(CoordinatorEntity[EdenicCoordinator], SensorEntity):
    """Represents a comma-separated summary of active alarms for a device."""

    _attr_icon = "mdi:alarm-light"

    def __init__(self, coordinator, device) -> None:
        super().__init__(coordinator)
        self._device_id = device["id"]
        self._attr_name = f"Alarms {device['label']}"
        self._attr_unique_id = f"{self._device_id}_alarm_summary"
        self._attr_device_info = _device_info(device)

    @property
    def native_value(self) -> str:
        """Return a comma-separated list of active alarm names."""
        data = self.coordinator.data.get(self._device_id)
        if data is None:
            return NO_ACTIVE_ALARMS
        active = [alarm.name for alarm in ALARMS if data.alarms.get(alarm.key)]
        return ", ".join(active) or NO_ACTIVE_ALARMS
