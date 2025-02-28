"""Constants pour l'intégration Storcube Battery Monitor."""

DOMAIN = "storcube_battery_monitor"

# Configuration
CONF_DEVICE_ID = "device_id"
CONF_APP_CODE = "app_code"
CONF_LOGIN_NAME = "login_name"
CONF_DEVICE_PASSWORD = "device_password"

# Valeurs par défaut
DEFAULT_UPDATE_INTERVAL = 30  # secondes
DEFAULT_PORT = 1883

# Topics MQTT - Format: battery/{device_id}/...
TOPIC_BASE = "battery/{device_id}"  # Sera formaté avec l'ID de l'appareil
TOPIC_BATTERY_STATUS = TOPIC_BASE + "/status"
TOPIC_BATTERY_POWER = TOPIC_BASE + "/power"
TOPIC_BATTERY_SOLAR = TOPIC_BASE + "/solar"
TOPIC_BATTERY_CAPACITY = TOPIC_BASE + "/capacity"
TOPIC_BATTERY_OUTPUT = TOPIC_BASE + "/outputEquip"
TOPIC_BATTERY_REPORT = TOPIC_BASE + "/reportEquip"
TOPIC_BATTERY_COMMAND = TOPIC_BASE + "/command"
TOPIC_BATTERY_SET_POWER = TOPIC_BASE + "/set_power"
TOPIC_BATTERY_SET_THRESHOLD = TOPIC_BASE + "/set_threshold"

# Unités
UNIT_POWER = "W"
UNIT_ENERGY = "Wh"
UNIT_PERCENTAGE = "%"
UNIT_TEMPERATURE = "°C"

# Icônes
ICON_SOLAR = "mdi:solar-power"
ICON_BATTERY = "mdi:battery-high"
ICON_BATTERY_CHARGING = "mdi:battery-charging"
ICON_INVERTER = "mdi:power"
ICON_PLUG = "mdi:power-plug"
ICON_TEMPERATURE = "mdi:thermometer"
ICON_IDENTIFIER = "mdi:identifier"
ICON_WORKING = "mdi:cog"
ICON_UPDATE = "mdi:cloud-upload"
ICON_FLASH = "mdi:flash"
ICON_CONNECTION = "mdi:wifi"

# Messages d'erreur
ERRORS = {
    "cannot_connect": "Impossible de se connecter au broker MQTT",
    "invalid_auth": "Identifiants MQTT invalides",
    "invalid_device": "Code de l'application ou identifiants invalides",
    "unknown": "Erreur inattendue"
} 