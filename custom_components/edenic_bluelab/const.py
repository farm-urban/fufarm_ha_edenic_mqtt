"""Constants for the Edenic Bluelab integration."""

from datetime import timedelta

DOMAIN = "edenic_bluelab"

CONF_ORG_KEY = "org_key"
CONF_API_KEY = "api_key"
CONF_DEVICES = "devices"
CONF_ALARM_MODE = "alarm_mode"

ALARM_MODE_INDIVIDUAL = "individual"
ALARM_MODE_SUMMARY = "summary"
ALARM_MODE_ALL = "all"
ALARM_MODES = (ALARM_MODE_INDIVIDUAL, ALARM_MODE_SUMMARY, ALARM_MODE_ALL)
DEFAULT_ALARM_MODE = ALARM_MODE_ALL

DEFAULT_SCAN_INTERVAL = timedelta(seconds=65)
NO_ACTIVE_ALARMS = "No active alarms"


class SensorDefinition:
    """Describes one telemetry sensor exposed by a Bluelab device."""

    def __init__(
        self,
        key: str,
        name: str,
        telemetry_key: str,
        device_class: str | None,
        unit: str | None,
    ) -> None:
        self.key = key
        self.name = name
        self.telemetry_key = telemetry_key
        self.device_class = device_class
        self.unit = unit


SENSORS: tuple[SensorDefinition, ...] = (
    SensorDefinition("ph", "pH", "ph", "ph", None),
    SensorDefinition(
        "temp", "Temperature", "temperature", "temperature", "°C"
    ),
    SensorDefinition("ec", "EC", "electrical_conductivity", None, "mS/cm"),
)


class AlarmDefinition:
    """Describes one alarm or lockout attribute exposed by a Bluelab device."""

    def __init__(self, key: str, name: str) -> None:
        self.key = key
        self.name = name


ALARMS: tuple[AlarmDefinition, ...] = (
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
