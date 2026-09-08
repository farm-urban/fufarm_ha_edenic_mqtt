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

NO_ACTIVE_ALARMS = "No active alarms"
PRO_CONTROLLER = "pro_controller"
LOOP_DELAY = 65
ALARM_MODE_INDIVIDUAL = "individual"
ALARM_MODE_SUMMARY = "summary"
ALARM_MODE_ALL = "all"
ALARM_MODES = (ALARM_MODE_INDIVIDUAL, ALARM_MODE_SUMMARY, ALARM_MODE_ALL)
_LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class SensorDefinition:
    """Describes one sensor exposed through MQTT discovery."""

    key: str
    name: str
    telemetry_key: str
    state_topic_attr: str
    device_class: str | None


SENSORS = (
    SensorDefinition("ph", "pH", "ph", "ph_state_topic", "ph"),
    SensorDefinition("temp", "Temp", "temperature", "temp_state_topic", "temperature"),
    SensorDefinition("ec", "EC", "electrical_conductivity", "ec_state_topic", None),
)


@dataclass(frozen=True)
class AlarmDefinition:
    """Describes one alarm or lockout exposed through MQTT."""

    key: str
    name: str


ALARMS = (
    AlarmDefinition("alarm.ec_low_alarm", "EC low alarm"),
    AlarmDefinition("alarm.ec_high_alarm", "EC high alarm"),
    AlarmDefinition("alarm.ph_low_alarm", "pH low alarm"),
    AlarmDefinition("alarm.ph_high_alarm", "pH high alarm"),
    AlarmDefinition("alarm.temp_low_alarm", "Temperature low alarm"),
    AlarmDefinition("alarm.temp_high_alarm", "Temperature high alarm"),
    AlarmDefinition("alarm.other_lockout", "Other lockout"),
    AlarmDefinition(
        "alarm.ineffective_control_lockout", "Ineffective control lockout"
    ),
    AlarmDefinition("alarm.low_ec_lockout", "Low EC lockout"),
    AlarmDefinition("alarm.normally_closed_lockout", "Normally closed lockout"),
    AlarmDefinition("alarm.normally_open_lockout", "Normally open lockout"),
)


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

    # Which alarm entities to create: "individual", "summary", or "both"
    alarm_mode: str = ALARM_MODE_ALL

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
    devices_by_label = {device["label"]: device for device in device_info}
    missing_labels = []

    for dconf in app_config.devices:
        device = devices_by_label.get(dconf.label)
        if device is None:
            missing_labels.append(dconf.label)
        else:
            dconf.id = device["id"]

    if missing_labels:
        labels = ", ".join(missing_labels)
        raise ValueError(f"No Edenic device found for label(s): {labels}")


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


def get_device_attributes(device_id, api_key):
    """Return the configured alarm and lockout attributes for a device."""
    url = f"https://api.edenic.io/api/v1/device-attribute/{device_id}"
    headers = {"Authorization": api_key}
    response = requests.get(
        url,
        headers=headers,
        params={"keys": ",".join(alarm.key for alarm in ALARMS)},
        timeout=10,
    )
    if response.status_code != 200:
        raise requests.exceptions.RequestException(
            f"Failed to get device attributes. Status code: {response.status_code}, "
            f"Response: {response.text}"
        )
    return response.json()


def alarm_topics(app_config: AppConfig, device: DeviceConfig) -> tuple[str, str]:
    """Return the binary-sensor base topic and summary topic for a device."""
    prefix = app_config.discovery_prefix
    device_key = device.label.lower()
    return (
        f"{prefix}/binary_sensor/edenic_{device_key}_alarm",
        f"{prefix}/sensor/edenic_{device_key}_alarm_summary",
    )


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
                for sensor in SENSORS:
                    sname = f"{sensor.key}_{d.label}"
                    config_topic = f"{base_url}/{sname}/config"
                    state_topic = f"{base_url}/{sname}/state"
                    setattr(d, sensor.state_topic_attr, state_topic)
                    payload = {
                        "name": f"Bluelab {sensor.name} {d.label}",
                        "device_class": sensor.device_class,
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

                alarm_base_topic, summary_topic = alarm_topics(app_config, d)
                if app_config.alarm_mode in (ALARM_MODE_INDIVIDUAL, ALARM_MODE_ALL):
                    for alarm in ALARMS:
                        entity_key = alarm.key.replace(".", "_")
                        config_topic = (
                            f"{app_config.discovery_prefix}/binary_sensor/"
                            f"edenic_{d.label.lower()}_{entity_key}/config"
                        )
                        state_topic = f"{alarm_base_topic}/{entity_key}/state"
                        payload = {
                            "name": f"Bluelab {alarm.name} {d.label}",
                            "state_topic": state_topic,
                            "unique_id": f"edenic_{d.label.lower()}_{entity_key}",
                            "payload_on": "ON",
                            "payload_off": "OFF",
                            "device_class": "problem",
                        }
                        client.publish(
                            config_topic,
                            json.dumps(payload).encode("utf8"),
                            qos=1,
                            retain=True,
                        )

                if app_config.alarm_mode in (ALARM_MODE_SUMMARY, ALARM_MODE_ALL):
                    summary_config_topic = (
                        f"{app_config.discovery_prefix}/sensor/"
                        f"edenic_{d.label.lower()}_alarm_summary/config"
                    )
                    summary_payload = {
                        "name": f"Bluelab alarms {d.label}",
                        "state_topic": f"{summary_topic}/state",
                        "unique_id": f"edenic_{d.label.lower()}_alarm_summary",
                        "icon": "mdi:alarm-light",
                    }
                    client.publish(
                        summary_config_topic,
                        json.dumps(summary_payload).encode("utf8"),
                        qos=1,
                        retain=True,
                    )
            else:
                raise ValueError(f"Unknown device type: {d.type}")

    return on_mqtt_connect


def setup_mqtt(app_config: AppConfig, on_connect_factory: Callable) -> mqtt.Client:
    """Setup the MQTT client and subscribe to topics."""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    host = app_config.mqtt_host
    port = app_config.mqtt_port
    username = app_config.mqtt_username
    password = app_config.mqtt_password
    client.username_pw_set(username, password)
    client.on_connect = on_connect_factory(app_config)
    try:
        client.connect(host, port=port)
    except (ConnectionRefusedError, socket.gaierror) as e:
        _LOG.error("Could not connect to MQTT broker: %s", e)
        raise e

    return client


def process_config(file_path: str) -> AppConfig:
    """Process the configuration file."""
    with open(file_path, "r", encoding="utf-8") as config_file:
        yaml_config = yaml.safe_load(config_file) or {}

    if "app" not in yaml_config:
        raise ValueError("No app configuration in config file")
    if "devices" not in yaml_config:
        raise ValueError("No devices in config file")

    app_config = AppConfig(**yaml_config["app"])

    for device_config in yaml_config["devices"]:
        device = DeviceConfig(**device_config)
        if device.type != PRO_CONTROLLER:
            raise ValueError(
                f"Only {PRO_CONTROLLER} devices are currently supported."
            )
        app_config.devices.append(device)

    if app_config.log_level.upper() not in logging.getLevelNamesMapping():
        raise ValueError(f"Unknown log_level: {app_config.log_level}")

    if app_config.alarm_mode not in ALARM_MODES:
        raise ValueError(f"Unknown alarm_mode: {app_config.alarm_mode}")

    return app_config


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
                for sensor in SENSORS:
                    state_topic = getattr(d, sensor.state_topic_attr)
                    value = telemetry[sensor.telemetry_key][0]["value"]
                    if state_topic is None or value is None:
                        raise ValueError(
                            f"Missing state topic or value for {sensor.key}"
                        )
                    mqtt_client.publish(state_topic, value.encode("utf8"))
                    _LOG.debug("Published %s to %s", value, state_topic)

            try:
                attributes = get_device_attributes(d.id, app_config.api_key)
            except requests.exceptions.RequestException as e:
                _LOG.warning("Error getting device attributes: %s", e)
            else:
                values_by_key = {
                    attribute["key"]: bool(attribute["value"])
                    for attribute in attributes
                }
                alarm_base_topic, summary_topic = alarm_topics(app_config, d)
                active_alarms = []
                for alarm in ALARMS:
                    state = "ON" if values_by_key.get(alarm.key, False) else "OFF"
                    if app_config.alarm_mode in (
                        ALARM_MODE_INDIVIDUAL,
                        ALARM_MODE_ALL,
                    ):
                        entity_key = alarm.key.replace(".", "_")
                        mqtt_client.publish(
                            f"{alarm_base_topic}/{entity_key}/state", state
                        )
                    if state == "ON":
                        active_alarms.append(alarm.name)

                if app_config.alarm_mode in (ALARM_MODE_SUMMARY, ALARM_MODE_ALL):
                    summary = ", ".join(active_alarms) or NO_ACTIVE_ALARMS
                    mqtt_client.publish(f"{summary_topic}/state", summary)
                    _LOG.debug(
                        "Published alarms for %s: %s", d.label, summary
                    )

        time.sleep(LOOP_DELAY)


def main() -> None:
    """Load configuration, initialize integrations, and publish telemetry."""
    app_config = process_config("edenic.yml")
    logging.basicConfig(
        level=app_config.log_level,
        format="%(asctime)s rpi: %(message)s",
    )
    _LOG.info("Starting Bluelab MQTT")

    device_info = get_devices(app_config.org_key, app_config.api_key)
    update_device_ids(app_config, device_info)

    mqtt_client = setup_mqtt(app_config, create_on_connect)
    mqtt_client.loop_start()
    main_loop(mqtt_client, app_config)


if __name__ == "__main__":
    main()
