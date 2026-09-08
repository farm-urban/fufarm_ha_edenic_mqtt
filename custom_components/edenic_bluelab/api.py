"""Thin synchronous client for the Edenic API.

All functions are blocking (uses ``requests``) and must be called via
``hass.async_add_executor_job`` from async code.
"""

from __future__ import annotations

import requests

from .const import ALARMS

API_BASE = "https://api.edenic.io/api/v1"
TIMEOUT = 10


class EdenicApiError(Exception):
    """Raised when the Edenic API returns an unexpected response."""


class EdenicAuthError(EdenicApiError):
    """Raised when the Edenic API rejects the supplied credentials."""


def _get(url: str, api_key: str, params: dict | None = None) -> requests.Response:
    response = requests.get(
        url, headers={"Authorization": api_key}, params=params, timeout=TIMEOUT
    )
    if response.status_code in (401, 403):
        raise EdenicAuthError(f"Authentication failed: {response.status_code}")
    if response.status_code != 200:
        raise EdenicApiError(
            f"Request to {url} failed: {response.status_code} {response.text}"
        )
    return response


def get_devices(org_key: str, api_key: str) -> list[dict]:
    """Return the raw list of devices registered to an organisation."""
    response = _get(f"{API_BASE}/device/{org_key}", api_key)
    return response.json()


def get_telemetry(device_id: str, api_key: str) -> dict:
    """Return the latest telemetry values for a device."""
    response = _get(f"{API_BASE}/telemetry/{device_id}", api_key)
    return response.json()


def get_device_attributes(device_id: str, api_key: str) -> dict:
    """Return alarm/lockout attribute values for a device, keyed by attribute key."""
    response = _get(
        f"{API_BASE}/device-attribute/{device_id}",
        api_key,
        params={"keys": ",".join(alarm.key for alarm in ALARMS)},
    )
    return {attribute["key"]: bool(attribute["value"]) for attribute in response.json()}
