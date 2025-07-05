"""Constants for the Storcube Battery Monitor integration."""

DOMAIN = "storcube_ha"
NAME = "Storcube Battery Monitor"

# Configuration constants
CONF_DEVICE_ID = "device_id"
CONF_APP_CODE = "app_code"
CONF_LOGIN_NAME = "login_name"
CONF_AUTH_PASSWORD = "auth_password"

# Default values
DEFAULT_PORT = 1883
DEFAULT_APP_CODE = "Storcube"

# URLs
WS_URI = "ws://baterway.com:9501/equip/info/"
TOKEN_URL = "http://baterway.com/api/user/app/login"
FIRMWARE_URL = "http://baterway.com/api/equip/version/need/upgrade"
OUTPUT_URL = "http://baterway.com/api/scene/user/list/V2?equipId="
SET_POWER_URL = "http://baterway.com/api/slb/equip/set/power"
SET_THRESHOLD_URL = "http://baterway.com/api/scene/threshold/set"

# MQTT Topics
TOPIC_BASE = "storcube/{device_id}/"
TOPIC_BATTERY = TOPIC_BASE + "status"
TOPIC_OUTPUT = TOPIC_BASE + "power"
TOPIC_FIRMWARE = TOPIC_BASE + "solar"
TOPIC_POWER = TOPIC_BASE + "set_power"
TOPIC_OUTPUT_POWER = TOPIC_BASE + "outputPower"
TOPIC_THRESHOLD = TOPIC_BASE + "set_threshold"
TOPIC_BATTERY_STATUS = TOPIC_BASE + "status"
TOPIC_BATTERY_POWER = TOPIC_BASE + "power"
TOPIC_BATTERY_SOLAR = TOPIC_BASE + "solar"

# MQTT Topic Status (ajouté pour corriger l'erreur d'import)
MQTT_TOPIC_STATUS = TOPIC_BATTERY_STATUS 