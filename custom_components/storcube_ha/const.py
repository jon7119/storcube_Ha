"""Constants for the Storcube Battery Monitor integration."""

DOMAIN = "storcube_ha"
NAME = "Storcube Battery Monitor"
MANUFACTURER = "Storcube"

# Configuration constants
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_DEVICE_ID = "device_id"
CONF_APP_CODE = "app_code"
CONF_LOGIN_NAME = "login_name"
CONF_AUTH_PASSWORD = "auth_password"
CONF_DEVICE_PASSWORD = "device_password"
CONF_WS_URI = "ws_uri"

# Default values
DEFAULT_PORT = 1883
DEFAULT_APP_CODE = "Storcube"
DEFAULT_LOGIN_NAME = "admin"
DEFAULT_AUTH_PASSWORD = "admin"

# URLs
WS_URI = "ws://baterway.com:9501/equip/info/"
TOKEN_URL = "http://baterway.com/api/user/app/login"
FIRMWARE_URL = "http://baterway.com/api/equip/version/need/upgrade"
OUTPUT_URL = "http://baterway.com/api/scene/user/list/V2?equipId="
SET_POWER_URL = "http://baterway.com/api/slb/equip/set/power"
SET_THRESHOLD_URL = "http://baterway.com/api/scene/threshold/set"

# MQTT Topics
MQTT_TOPIC_PREFIX = "storcube"
TOPIC_BASE = f"{MQTT_TOPIC_PREFIX}/{{device_id}}/"
TOPIC_BATTERY = TOPIC_BASE + "status"
TOPIC_OUTPUT = TOPIC_BASE + "power"
TOPIC_FIRMWARE = TOPIC_BASE + "solar"
TOPIC_POWER = TOPIC_BASE + "set_power"
TOPIC_OUTPUT_POWER = TOPIC_BASE + "outputPower"
TOPIC_THRESHOLD = TOPIC_BASE + "set_threshold"
TOPIC_BATTERY_STATUS = TOPIC_BASE + "status"
TOPIC_BATTERY_POWER = TOPIC_BASE + "power"
TOPIC_BATTERY_SOLAR = TOPIC_BASE + "solar"
TOPIC_BATTERY_CAPACITY = TOPIC_BASE + "capacity"
TOPIC_BATTERY_OUTPUT = TOPIC_BASE + "output"
TOPIC_BATTERY_REPORT = TOPIC_BASE + "report"
TOPIC_BATTERY_COMMAND = TOPIC_BASE + "command"
TOPIC_BATTERY_SET_POWER = TOPIC_BASE + "set_power"
TOPIC_BATTERY_SET_THRESHOLD = TOPIC_BASE + "set_threshold"

# Sensor types
SENSOR_TYPES = {
    "battery_level": {
        "name": "Battery Level",
        "device_class": "battery",
        "state_class": "measurement",
        "unit_of_measurement": "%",
        "icon": "mdi:battery"
    },
    "power": {
        "name": "Power",
        "device_class": "power",
        "state_class": "measurement",
        "unit_of_measurement": "W",
        "icon": "mdi:power-plug"
    },
    "voltage": {
        "name": "Voltage",
        "device_class": "voltage",
        "state_class": "measurement",
        "unit_of_measurement": "V",
        "icon": "mdi:lightning-bolt"
    },
    "current": {
        "name": "Current",
        "device_class": "current",
        "state_class": "measurement",
        "unit_of_measurement": "A",
        "icon": "mdi:current-ac"
    },
    "temperature": {
        "name": "Temperature",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": "°C",
        "icon": "mdi:thermometer"
    }
}

# Binary sensor types
BINARY_SENSOR_TYPES = {
    "online": {
        "name": "Online Status",
        "device_class": "connectivity",
        "icon": "mdi:lan-connect"
    },
    "charging": {
        "name": "Charging Status",
        "device_class": "battery_charging",
        "icon": "mdi:battery-charging"
    },
    "discharging": {
        "name": "Discharging Status",
        "device_class": "battery",
        "icon": "mdi:battery"
    }
}

# Switch types
SWITCH_TYPES = {
    "power": {
        "name": "Power",
        "icon": "mdi:power"
    },
    "output": {
        "name": "Output",
        "icon": "mdi:power-socket"
    }
}

# Error messages
ERROR_MESSAGES = {
    "auth_failed": "Authentication failed",
    "connection_error": "Connection error",
    "invalid_config": "Invalid configuration",
    "timeout": "Request timeout"
} 