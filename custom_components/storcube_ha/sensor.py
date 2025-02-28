"""Support for StorCube Battery Monitor sensors."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the StorCube Battery Monitor sensors."""
    async_add_entities([StorCubeSensor(config_entry)])

class StorCubeSensor(SensorEntity):
    """Representation of a StorCube Battery Monitor sensor."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._attr_name = "StorCube Battery"
        self._attr_unique_id = f"{config_entry.entry_id}_battery"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return "Connected" 