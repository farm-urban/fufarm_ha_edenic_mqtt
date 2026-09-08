"""Data update coordinator for the Edenic Bluelab integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EdenicApiError, get_device_attributes, get_telemetry
from .const import DEFAULT_SCAN_INTERVAL

_LOG = logging.getLogger(__name__)


@dataclass
class EdenicDeviceData:
    """Latest telemetry and alarm data for a single device."""

    telemetry: dict[str, Any]
    alarms: dict[str, bool]


class EdenicCoordinator(DataUpdateCoordinator[dict[str, EdenicDeviceData]]):
    """Polls the Edenic API for all configured devices on an interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        devices: list[dict[str, str]],
        scan_interval: int | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOG,
            name=f"{entry.title} coordinator",
            update_interval=timedelta(seconds=scan_interval)
            if scan_interval
            else DEFAULT_SCAN_INTERVAL,
        )
        self.api_key: str = entry.data["api_key"]
        self.devices = devices

    async def _async_update_data(self) -> dict[str, EdenicDeviceData]:
        result: dict[str, EdenicDeviceData] = {}
        for device in self.devices:
            device_id = device["id"]
            try:
                telemetry = await self.hass.async_add_executor_job(
                    get_telemetry, device_id, self.api_key
                )
                alarms = await self.hass.async_add_executor_job(
                    get_device_attributes, device_id, self.api_key
                )
            except EdenicApiError as err:
                raise UpdateFailed(f"Error updating {device['label']}: {err}") from err
            result[device_id] = EdenicDeviceData(telemetry=telemetry, alarms=alarms)
        return result
