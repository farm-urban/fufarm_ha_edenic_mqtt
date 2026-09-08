# Developer Guide

This repository contains two independent ways to get Edenic Bluelab data into
Home Assistant:

- [`mqtt_bridge/`](mqtt_bridge/) — a standalone Python script that publishes
  data via MQTT discovery. Runs as its own systemd service.
- [`custom_components/edenic_bluelab/`](custom_components/edenic_bluelab/) —
  a native Home Assistant custom integration (config flow + coordinator +
  entities). Runs inside Home Assistant itself.

This document covers building and testing the custom integration.

## Setup

Run the setup script once to create a local virtual environment with
everything needed to develop and test the integration:

```sh
./scripts/setup_dev_env.sh
```

This creates `.venv/` at the repo root and installs:

- `pytest-homeassistant-custom-component` — pulls in a compatible pinned
  version of `homeassistant` itself, plus test fixtures for config flows,
  entities, and coordinators.
- `requests` — used by `custom_components/edenic_bluelab/api.py`.
- `ruff` — linting/formatting.

Activate the environment in your shell:

```sh
source .venv/bin/activate
```

Re-run `./scripts/setup_dev_env.sh` any time to pick up new/updated
dependencies (it's safe to run repeatedly).

## Linting

```sh
ruff check custom_components/edenic_bluelab
ruff format custom_components/edenic_bluelab
```

## Testing

Tests should live under `tests/` at the repo root (create it if it doesn't
exist yet), mirroring `pytest-homeassistant-custom-component`'s conventions,
e.g.:

```
tests/
└── edenic_bluelab/
    ├── conftest.py
    ├── test_config_flow.py
    └── test_sensor.py
```

Run the suite with:

```sh
pytest
```

## Live API tests

`tests/edenic_bluelab/test_live_api.py` calls the real Edenic API (no
mocking) to verify `api.py` against production behaviour. These are marked
`live` and excluded from the default `pytest` run so CI/normal test runs
never need real credentials.

To run them:

1. Copy the template and fill in real values:
   ```sh
   cp tests/secrets.yaml.template tests/secrets.yaml
   ```
   ```yaml
   org_key: "..."
   api_key: "..."
   device_label: "4q3f"   # a real device label in that org
   ```
   `tests/secrets.yaml` is gitignored — never commit it.
2. Run just the live tests:
   ```sh
   pytest -m live
   ```

Without `tests/secrets.yaml`, `pytest -m live` skips each test with a clear
message rather than failing.

## Installing the integration into a real Home Assistant instance

For manual testing against a live Home Assistant install (not via HACS):

1. Copy `custom_components/edenic_bluelab/` into
   `<homeassistant config dir>/custom_components/edenic_bluelab/`.
2. Restart Home Assistant.
3. Settings → Devices & Services → Add Integration → search "Edenic Bluelab".

## Repository layout

```
mqtt_bridge/                        # MQTT-discovery based script (existing approach)
custom_components/edenic_bluelab/   # Native HA custom integration (in development)
scripts/setup_dev_env.sh            # Creates/updates .venv for integration dev
hacs.json                           # Lets HACS discover custom_components/edenic_bluelab
```
