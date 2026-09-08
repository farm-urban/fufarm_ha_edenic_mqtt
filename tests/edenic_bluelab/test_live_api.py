"""Tests that call the real Edenic API.

These require tests/secrets.yaml with real credentials (see
tests/secrets.yaml.template) and are excluded from the default test run.

Run explicitly with:
    pytest -m live
"""

import pytest
import pytest_socket

from custom_components.edenic_bluelab.api import (
    get_device_attributes,
    get_devices,
    get_telemetry,
)

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def _allow_real_network():
    """Override pytest-homeassistant-custom-component's localhost-only socket guard.

    That plugin unconditionally restricts connections to 127.0.0.1 on every
    test via its own pytest_runtest_setup hook, which runs before fixtures.
    Re-allowing the real API host here (fixture setup runs after that hook)
    lets these tests reach the real Edenic API.
    """
    pytest_socket.enable_socket()
    pytest_socket.socket_allow_hosts(["api.edenic.io"], allow_unix_socket=True)
    yield


def _find_device(devices: list[dict], label: str) -> dict:
    for device in devices:
        if device["label"] == label:
            return device
    raise AssertionError(f"No device with label {label!r} found in {devices!r}")


def test_get_devices_live(edenic_credentials):
    """The configured org returns a device list containing the test device."""
    devices = get_devices(
        edenic_credentials["org_key"], edenic_credentials["api_key"]
    )
    _find_device(devices, edenic_credentials["device_label"])


def test_get_telemetry_live(edenic_credentials):
    """The test device returns telemetry with the expected keys."""
    devices = get_devices(
        edenic_credentials["org_key"], edenic_credentials["api_key"]
    )
    device = _find_device(devices, edenic_credentials["device_label"])

    telemetry = get_telemetry(device["id"], edenic_credentials["api_key"])

    for key in ("ph", "temperature", "electrical_conductivity"):
        assert key in telemetry


def test_get_device_attributes_live(edenic_credentials):
    """The test device returns a dict of alarm attribute keys to booleans."""
    devices = get_devices(
        edenic_credentials["org_key"], edenic_credentials["api_key"]
    )
    device = _find_device(devices, edenic_credentials["device_label"])

    attributes = get_device_attributes(device["id"], edenic_credentials["api_key"])

    assert isinstance(attributes, dict)
    assert all(isinstance(value, bool) for value in attributes.values())
