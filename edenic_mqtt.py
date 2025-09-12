#!/usr/bin/env python3

import json
import logging
import socket
import time
from dataclasses import dataclass, field
from typing import Callable

import paho.mqtt.client as mqtt
import requests
import yaml

PRO_CONTROLLER = "pro_controller"
LOOP_DELAY = 65


@dataclass
class DeviceConfig:
    """Configures an individual device."""

    name: str
    type: str
    label: str
    id: str = None
    ec_state_topic: str = None
    ph_state_topic: str = None
    temp_state_topic: str = None

    def __repr__(self):
        x = "\n ".join(f"{k} : {repr(v)}" for (k, v) in self.__dict__.items())
        return f"<\n{x}\n>"


@dataclass
class AppConfig:
    """Configures the Application."""

    log_level: str = "INFO"
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""

    discovery_prefix: str = "homeassistant"

    org_key: str = ""
    api_key: str = ""

    # https://docs.python.org/3/library/dataclasses.html#mutable-default-values
    devices: list[DeviceConfig] = field(default_factory=list)

    def __repr__(self):
        x = "\n ".join(f"{k} : {repr(v)}" for (k, v) in self.__dict__.items())
        return f"<\n{x}\n>"


def get_devices(organisation_id, api_key):
    """Returns the devices for an organisation.

    E.g.:
    [{'id': '08041fb0-6ea2-11ef-9d80-63343a698b74',
    'name': '9e9efe10-6e9f-11ef-9538-8dff4b34f2dc__0013a20041cdb315',
    'label': '4q3f',
    'gateway': False,
    'sortOrder': 0,
    'deviceTypeId': 'f33da651-1851-4291-a174-56e0c16e418c',
    'organisationId': '9e9efe10-6e9f-11ef-9348-8dff4b34f2dc',
    'deleted': False,
    'additionalInfo': {'lastConnectedGateway': 'c10ed720-6ea1-11ef-0d80-63543a698b74'}}]
    """
    url = f"https://api.edenic.io/api/v1/device/{organisation_id}"
    headers = {"Authorization": api_key}
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        raise requests.exceptions.RequestException(
            f"Failed to get devices. Status code: {response.status_code}, Response: {response.text}"
        )
    return response.json()


def update_device_ids(app_config: AppConfig, device_info: list[dict]):
    """Get the device id from Bluelab and update our device list."""
    for dconf in app_config.devices:
        for dinfo in device_info:
            if dconf.label == dinfo["label"]:
                dconf.id = dinfo["id"]
                break
    return


def get_telemetry(device_id, api_key):
    """Returns the telemetry for a device.

    E.g.:
    {'ph': [{'ts': 1726605615556, 'value': '5.8'}],
     'temperature': [{'ts': 1726605615556, 'value': '27.0'}],
      'electrical_conductivity': [{'ts': 1726605615556, 'value': '1.5'}]}
    """
    url = f"https://api.edenic.io/api/v1/telemetry/{device_id}"
    headers = {"Authorization": api_key}
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        raise requests.exceptions.RequestException(
            f"Failed to get telmetry: {response.text}"
        )
    return response.json()


def create_on_connect(app_config: AppConfig) -> Callable:
    """Create a callback to handle connection to MQTT broker.

    https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery
    https://developers.home-assistant.io/docs/core/entity/sensor/

    NB: Need to subscribe to the homeassistant/status topic to and
    listen for the connected message and then resubmit auto-discovery messages
    """

    def on_mqtt_connect(
        client: mqtt.Client, _userdata, _connect_flags, _reason_code, _properties
    ):
        """Subscribe to topics on connect."""

        for d in app_config.devices:
            if d.type == PRO_CONTROLLER:
                base_url = f"{app_config.discovery_prefix}/sensor"
                for stype in ["pH", "Temp", "EC"]:
                    sname = f"{stype.lower()}_{d.label}"
                    config_topic = f"{base_url}/{sname}/config"
                    state_topic = f"{base_url}/{sname}/state"
                    if stype == "pH":
                        d.ph_state_topic = state_topic
                    elif stype == "Temp":
                        d.temp_state_topic = state_topic
                    elif stype == "EC":
                        d.ec_state_topic = state_topic
                    # https://www.home-assistant.io/integrations/sensor/#device-class
                    dclass = {"pH": "ph", "Temp": "temperature", "EC": None}.get(stype)
                    payload = {
                        "name": f"Bluelab {stype} {d.label}",
                        "device_class": dclass,
                        "state_topic": state_topic,
                        "unique_id": sname,
                        "expire_after": LOOP_DELAY * 2,
                    }
                    client.publish(
                        config_topic,
                        json.dumps(payload).encode("utf8"),
                        qos=1,
                        retain=True,
                    )
                    _LOG.debug(
                        "Added Bluelab %s sensor to Home Assistant: %s", sname, payload
                    )
            else:
                raise ValueError(f"Unknown device type: {d.type}")

    return on_mqtt_connect


def setup_mqtt(app_config: AppConfig, create_on_connect: Callable) -> mqtt.Client:
    """Setup the MQTT client and subscribe to topics."""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    host = app_config.mqtt_host
    port = app_config.mqtt_port
    username = app_config.mqtt_username
    password = app_config.mqtt_password
    client.username_pw_set(username, password)
    try:
        client.connect(host, port=port)
    except (ConnectionRefusedError, socket.gaierror) as e:
        _LOG.error("Could not connect to MQTT broker: %s", e)
        raise e
    client.on_connect = create_on_connect(app_config)

    return client


def process_config(file_path: str) -> AppConfig:
    """Process the configuration file."""
    with open(file_path, "r", encoding="utf-8") as f:
        yamls = yaml.safe_load(f)
        _app_config = AppConfig(**yamls["app"])

        if not "devices" in yamls:
            raise ValueError("No devices in config file")

        for d in yamls["devices"]:
            device = DeviceConfig(**d)
            if device.type != PRO_CONTROLLER:
                raise ValueError(
                    f"Only {PRO_CONTROLLER} devices are currently supported."
                )
            _app_config.devices.append(device)

    if not hasattr(logging, _app_config.log_level):
        raise AttributeError(f"Unknown log_level: {_app_config.APP.log_level}")

    return _app_config


def main_loop(mqtt_client, app_config):
    """Main loop to get telemetry and publish to MQTT."""
    while True:
        while not mqtt_client.is_connected():
            _LOG.warning("mqtt_client not connected")
            mqtt_client.reconnect()
            time.sleep(2)

        for d in app_config.devices:
            telemetry = None
            try:
                telemetry = get_telemetry(d.id, app_config.api_key)
            except requests.exceptions.RequestException as e:
                _LOG.warning("Error getting telemetry: %s", e)
            if telemetry:
                for stype in ["ph", "temp", "ec"]:
                    state_topic = None
                    value = None
                    if stype == "ph":
                        state_topic = d.ph_state_topic
                        value = telemetry["ph"][0]["value"]
                    elif stype == "temp":
                        state_topic = d.temp_state_topic
                        value = telemetry["temperature"][0]["value"]
                    elif stype == "ec":
                        state_topic = d.ec_state_topic
                        value = telemetry["electrical_conductivity"][0]["value"]
                    assert (
                        state_topic is not None and value is not None
                    ), "Missing state_topic or value!"
                    mqtt_client.publish(state_topic, value.encode("utf8"))
                    _LOG.debug("Published %s to %s", value, state_topic)

        time.sleep(LOOP_DELAY)


APP_CONFIG = process_config("edenic.yml")

logging.basicConfig(
    level=APP_CONFIG.log_level,
    format="%(asctime)s rpi: %(message)s",
)
_LOG = logging.getLogger(__name__)

_LOG.info("Starting Bluelab MQTT")


# Get the individual device IDs from Edenic
DEVICE_INFO = get_devices(APP_CONFIG.org_key, APP_CONFIG.api_key)
update_device_ids(APP_CONFIG, DEVICE_INFO)

# Set up the MQTT client
MQTT_CLIENT = setup_mqtt(APP_CONFIG, create_on_connect)
MQTT_CLIENT.loop_start()

main_loop(MQTT_CLIENT, APP_CONFIG)
