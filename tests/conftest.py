"""Shared pytest fixtures for testing custom_components/edenic_bluelab."""

import pathlib

import pytest
import yaml

pytest_plugins = "pytest_homeassistant_custom_component"

SECRETS_PATH = pathlib.Path(__file__).parent / "secrets.yaml"
REQUIRED_SECRET_KEYS = {"org_key", "api_key", "device_label"}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow Home Assistant to discover custom_components/ during tests."""
    yield


@pytest.fixture(scope="session")
def edenic_credentials():
    """Real Edenic credentials for live API tests, loaded from tests/secrets.yaml.

    Skips the test if the file is missing or incomplete, so `pytest -m live`
    fails loudly with a clear message rather than a stack trace.
    """
    if not SECRETS_PATH.exists():
        pytest.skip(
            "tests/secrets.yaml not found. Copy tests/secrets.yaml.template to "
            "tests/secrets.yaml and fill in real Edenic credentials to run live "
            "API tests."
        )
    data = yaml.safe_load(SECRETS_PATH.read_text(encoding="utf-8")) or {}
    missing = REQUIRED_SECRET_KEYS - data.keys()
    if missing:
        pytest.skip(f"tests/secrets.yaml is missing keys: {', '.join(missing)}")
    return data
