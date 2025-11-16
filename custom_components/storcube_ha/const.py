"""Constants for the Storcube Battery Monitor integration."""

DOMAIN = "storcube_ha"
NAME = "Storcube Battery Monitor"

# Configuration constants
CONF_DEVICE_ID = "device_id"
CONF_APP_CODE = "app_code"
CONF_LOGIN_NAME = "login_name"
CONF_AUTH_PASSWORD = "auth_password"

# Default values
DEFAULT_APP_CODE = "Storcube"

# URLs
WS_URI = "ws://baterway.com:9501/equip/info/"
TOKEN_URL = "http://baterway.com/api/user/app/login"
FIRMWARE_URL = "http://baterway.com/api/equip/version/need/upgrade?equipId="
OUTPUT_URL = "http://baterway.com/api/scene/user/list/V2?equipId="
SET_POWER_URL = "http://baterway.com/api/slb/equip/set/power"
SET_THRESHOLD_URL = "http://baterway.com/api/scene/threshold/set"

# Nouveaux endpoints API
DEVICE_INFO_URL = "http://baterway.com/api/device/info"
DEVICE_STATUS_URL = "http://baterway.com/api/device/status"
DEVICE_LIST_URL = "http://baterway.com/api/device/list"
DEVICE_CONTROL_URL = "http://baterway.com/api/device/control"
DEVICE_SETTINGS_URL = "http://baterway.com/api/device/settings"
POWER_SETTINGS_URL = "http://baterway.com/api/power/settings"
STATISTICS_ENERGY_URL = "http://baterway.com/api/statistics/energy"
STATISTICS_POWER_URL = "http://baterway.com/api/statistics/power"
STATISTICS_DAILY_URL = "http://baterway.com/api/statistics/daily"
STATISTICS_MONTHLY_URL = "http://baterway.com/api/statistics/monthly"
SCENE_LIST_URL = "http://baterway.com/api/scene/list"
SCENE_DETAIL_URL = "http://baterway.com/api/scene/detail"
SCENE_CREATE_URL = "http://baterway.com/api/scene/create"
SCENE_UPDATE_URL = "http://baterway.com/api/scene/update"
SCENE_DELETE_URL = "http://baterway.com/api/scene/delete"
SCENE_EXECUTE_URL = "http://baterway.com/api/scene/execute"
FIRMWARE_CHECK_URL = "http://baterway.com/api/firmware/check"
FIRMWARE_UPGRADE_URL = "http://baterway.com/api/firmware/upgrade"
FIRMWARE_STATUS_URL = "http://baterway.com/api/firmware/status"


# Firmware constants
SERVICE_CHECK_FIRMWARE = "check_firmware"
ATTR_FIRMWARE_CURRENT = "current_version"
ATTR_FIRMWARE_LATEST = "latest_version"
ATTR_FIRMWARE_UPGRADE_AVAILABLE = "upgrade_available"
ATTR_FIRMWARE_NOTES = "firmware_notes"

# Icons
ICON_CONNECTION = "mdi:network" 