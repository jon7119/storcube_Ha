"""Constants for the Storcube Battery Monitor integration."""

DOMAIN = "storcube_ha"

# Configuration constants
CONF_DEVICE_ID = "device_id"
CONF_APP_CODE = "app_code"
CONF_LOGIN_NAME = "login_name"
CONF_AUTH_PASSWORD = "auth_password"

# Default values
DEFAULT_PORT = 1883
DEFAULT_APP_CODE = "Storcube"

# API endpoints
WS_URI = "ws://baterway.com:9501/equip/info/"
TOKEN_URL = "http://baterway.com/api/user/app/login"
FIRMWARE_URL = "http://baterway.com/api/equip/version/need/upgrade"
OUTPUT_URL = "http://baterway.com/api/scene/user/list/V2"
SET_POWER_URL = "http://baterway.com/api/slb/equip/set/power"
SET_THRESHOLD_URL = "http://baterway.com/api/scene/threshold/set"

# MQTT Topics
TOPIC_BATTERY = "battery/reportEquip"
TOPIC_OUTPUT = "battery/outputEquip"
TOPIC_FIRMWARE = "battery/firmwareEquip"
TOPIC_POWER = "battery/set_power"
TOPIC_OUTPUT_POWER = "battery/outputPower"
TOPIC_THRESHOLD = "battery/set_threshold" 