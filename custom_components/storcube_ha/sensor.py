"""Support for StorCube Battery Monitor sensors."""
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfPower,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ICON_BATTERY,
    ICON_SOLAR,
    ICON_INVERTER,
)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the StorCube Battery Monitor sensors."""
    async_add_entities([
        StorCubeBatteryLevel(config_entry),
        StorCubeSolarPower(config_entry),
        StorCubeBatteryPower(config_entry),
    ])

class StorCubeBaseSensor(SensorEntity):
    """Base class for StorCube sensors."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        name: str,
        icon: str,
        device_class: str | None = None,
        state_class: str | None = None,
        unit: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        self._config = config_entry
        self._attr_name = f"StorCube {name}"
        self._attr_unique_id = f"{config_entry.entry_id}_{name.lower().replace(' ', '_')}"
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._config.entry_id)},
            name="StorCube Battery",
            manufacturer="StorCube",
            model="Battery Monitor",
        )

class StorCubeBatteryLevel(StorCubeBaseSensor):
    """Sensor for battery level."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(
            config_entry,
            "Battery Level",
            ICON_BATTERY,
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
            unit=PERCENTAGE,
        )

    @property
    def native_value(self):
        """Return the battery level."""
        return 50  # À remplacer par la vraie valeur

class StorCubeSolarPower(StorCubeBaseSensor):
    """Sensor for solar power input."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(
            config_entry,
            "Solar Power",
            ICON_SOLAR,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            unit=UnitOfPower.WATT,
        )

    @property
    def native_value(self):
        """Return the solar power."""
        return 0  # À remplacer par la vraie valeur

class StorCubeBatteryPower(StorCubeBaseSensor):
    """Sensor for battery power output."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(
            config_entry,
            "Battery Power",
            ICON_INVERTER,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            unit=UnitOfPower.WATT,
        )

    @property
    def native_value(self):
        """Return the battery power."""
        return 0  # À remplacer par la vraie valeur 