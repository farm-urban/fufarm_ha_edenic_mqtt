"""Tests for the Edenic API client."""

from unittest.mock import patch

import pytest

from custom_components.edenic_bluelab.api import (
    EdenicApiError,
    EdenicAuthError,
    get_devices,
)


class _FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def test_get_devices_success():
    """A 200 response returns the parsed device list."""
    devices = [{"id": "abc123", "label": "4q3f"}]
    with patch("requests.get", return_value=_FakeResponse(200, devices)):
        assert get_devices("org", "key") == devices


def test_get_devices_auth_error():
    """A 401/403 response raises EdenicAuthError."""
    with patch("requests.get", return_value=_FakeResponse(401, {})):
        with pytest.raises(EdenicAuthError):
            get_devices("org", "bad-key")


def test_get_devices_other_error():
    """Any other non-200 response raises EdenicApiError."""
    with patch("requests.get", return_value=_FakeResponse(500, {})):
        with pytest.raises(EdenicApiError):
            get_devices("org", "key")
