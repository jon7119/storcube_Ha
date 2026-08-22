"""Constants for the Storcube Battery Monitor integration."""

DOMAIN = "storcube_ha"
NAME = "Storcube Battery Monitor"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CONF_DEVICE_ID = "device_id"
CONF_APP_CODE = "app_code"
CONF_LOGIN_NAME = "login_name"
CONF_AUTH_PASSWORD = "auth_password"

DEFAULT_APP_CODE = "Storcube"

# Conservé pour la compatibilité des anciennes entrées de configuration.
# Plus utilisé : l'intégration passe par le broker MQTT de Home Assistant.
DEFAULT_PORT = 1883

# ---------------------------------------------------------------------------
# URLs de l'API Baterway
# Les deux premières se terminent par un paramètre à compléter avec l'equipId.
# ---------------------------------------------------------------------------
WS_URI = "ws://baterway.com:9501/equip/info/"
TOKEN_URL = "http://baterway.com/api/user/app/login"
FIRMWARE_URL = "http://baterway.com/api/equip/version/need/upgrade?equipId="
OUTPUT_URL = "http://baterway.com/api/scene/user/list/V2?equipId="
SET_POWER_URL = "http://baterway.com/api/slb/equip/set/power"
SET_THRESHOLD_URL = "http://baterway.com/api/scene/threshold/set"
QUERY_THRESHOLD_URL = "http://baterway.com/api/scene/threshold/query"

# ---------------------------------------------------------------------------
# Topics MQTT — un topic distinct par grandeur, sans collision.
# TOPIC_BASE se termine par un slash.
# ---------------------------------------------------------------------------
TOPIC_BASE = "storcube/{device_id}/"

# Publiés par l'intégration (état remonté par le WebSocket).
TOPIC_BATTERY_STATUS = TOPIC_BASE + "status"
TOPIC_BATTERY_POWER = TOPIC_BASE + "power"
TOPIC_BATTERY_SOLAR = TOPIC_BASE + "solar"
TOPIC_BATTERY_CAPACITY = TOPIC_BASE + "capacity"
TOPIC_BATTERY_REPORT = TOPIC_BASE + "report"
TOPIC_OUTPUT = TOPIC_BASE + "output"
TOPIC_OUTPUT_POWER = TOPIC_BASE + "output_power"
TOPIC_FIRMWARE = TOPIC_BASE + "firmware"

# Topics de commande (consignes envoyées vers l'appareil).
TOPIC_SET_POWER = TOPIC_BASE + "set_power"
TOPIC_THRESHOLD = TOPIC_BASE + "set_threshold"

# Alias rétrocompatibles.
TOPIC_BATTERY = TOPIC_BATTERY_STATUS
TOPIC_POWER = TOPIC_SET_POWER

# ---------------------------------------------------------------------------
# Icônes
# ---------------------------------------------------------------------------
ICON_CONNECTION = "mdi:lan-connect"
ICON_BATTERY = "mdi:battery"
ICON_POWER = "mdi:flash"
ICON_SOLAR = "mdi:solar-power"
ICON_OUTPUT = "mdi:power-plug"
ICON_THRESHOLD = "mdi:battery-alert"
ICON_FIRMWARE = "mdi:chip"

# ---------------------------------------------------------------------------
# Firmware
# ---------------------------------------------------------------------------
SERVICE_CHECK_FIRMWARE = "check_firmware"
ATTR_FIRMWARE_CURRENT = "current_version"
ATTR_FIRMWARE_LATEST = "latest_version"
ATTR_FIRMWARE_UPGRADE_AVAILABLE = "upgrade_available"
ATTR_FIRMWARE_NOTES = "firmware_notes"

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
SERVICE_SET_POWER = "set_power"
SERVICE_SET_THRESHOLD = "set_threshold"
ATTR_POWER = "power"
ATTR_THRESHOLD = "threshold"
ATTR_DEVICE_ID = "device_id"

# Bornes des consignes.
MIN_POWER = 0
MAX_POWER = 800
MIN_THRESHOLD = 0
MAX_THRESHOLD = 100
