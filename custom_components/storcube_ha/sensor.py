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
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ICON_BATTERY,
    ICON_SOLAR,
    ICON_INVERTER,
    ICON_TEMPERATURE,
)
from .coordinator import StorCubeDataUpdateCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the StorCube Battery Monitor sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([
        StorCubeBatteryLevel(coordinator, config_entry),
        StorCubeSolarPower(coordinator, config_entry),
        StorCubeBatteryPower(coordinator, config_entry),
        StorCubeTemperature(coordinator, config_entry),
        StorCubeStatus(coordinator, config_entry),
    ])

class StorCubeBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for StorCube sensors."""

    def __init__(
        self,
        coordinator: StorCubeDataUpdateCoordinator,
        config_entry: ConfigEntry,
        name: str,
        icon: str,
        device_class: str | None = None,
        state_class: str | None = None,
        unit: str | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
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

    def __init__(self, coordinator: StorCubeDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
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
        return self.coordinator.data["battery_level"]

class StorCubeSolarPower(StorCubeBaseSensor):
    """Sensor for solar power input."""

    def __init__(self, coordinator: StorCubeDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
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
        return self.coordinator.data["solar_power"]

class StorCubeBatteryPower(StorCubeBaseSensor):
    """Sensor for battery power output."""

    def __init__(self, coordinator: StorCubeDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
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
        return self.coordinator.data["battery_power"]

class StorCubeTemperature(StorCubeBaseSensor):
    """Sensor for battery temperature."""

    def __init__(self, coordinator: StorCubeDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            config_entry,
            "Temperature",
            ICON_TEMPERATURE,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            unit=UnitOfTemperature.CELSIUS,
        )

    @property
    def native_value(self):
        """Return the battery temperature."""
        return self.coordinator.data["temperature"]

class StorCubeStatus(StorCubeBaseSensor):
    """Sensor for battery status."""

    def __init__(self, coordinator: StorCubeDataUpdateCoordinator, config_entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            config_entry,
            "Status",
            ICON_BATTERY,
        )

    @property
    def native_value(self):
        """Return the battery status."""
        return self.coordinator.data["status"] 