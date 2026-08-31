"""Sensor entity for Wiren Board."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfReactiveEnergy,
    UnitOfReactivePower,
    UnitOfSoundPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)

try:
    from homeassistant.const import UnitOfIlluminance
except ImportError:
    # No HA release ships UnitOfIlluminance yet (checked up to 2026.7);
    # keep this fallback until it appears in homeassistant.const.
    from enum import StrEnum

    class UnitOfIlluminance(StrEnum):
        LUX = "lx"


from .base import WirenBoardEntity

logger = logging.getLogger(__name__)

# WB device_type -> HA SensorDeviceClass
_DEVICE_CLASS_BY_TYPE = {
    "temperature": SensorDeviceClass.TEMPERATURE,
    "rel_humidity": SensorDeviceClass.HUMIDITY,
    "power": SensorDeviceClass.POWER,
    "power_consumption": SensorDeviceClass.ENERGY,
    "voltage": SensorDeviceClass.VOLTAGE,
    "current": SensorDeviceClass.CURRENT,
    "lux": SensorDeviceClass.ILLUMINANCE,
    "ppm": SensorDeviceClass.CO2,
    "concentration": SensorDeviceClass.CO2,
    "ppb": SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
    "sound_level": SensorDeviceClass.SOUND_PRESSURE,
    "atmospheric_pressure": SensorDeviceClass.ATMOSPHERIC_PRESSURE,
    "pressure": SensorDeviceClass.PRESSURE,
    "water_consumption": SensorDeviceClass.WATER,
    "heat_energy": SensorDeviceClass.ENERGY,
}

# Fallback: WB unit -> HA SensorDeviceClass (for generic "value"/"range" types)
_DEVICE_CLASS_BY_UNIT = {
    "V": SensorDeviceClass.VOLTAGE,
    "mV": SensorDeviceClass.VOLTAGE,
    "A": SensorDeviceClass.CURRENT,
    "mA": SensorDeviceClass.CURRENT,
    "W": SensorDeviceClass.POWER,
    "kW": SensorDeviceClass.POWER,
    "kWh": SensorDeviceClass.ENERGY,
    "Wh": SensorDeviceClass.ENERGY,
    "deg C": SensorDeviceClass.TEMPERATURE,
    "°C": SensorDeviceClass.TEMPERATURE,
    "C": SensorDeviceClass.TEMPERATURE,
    "%, RH": SensorDeviceClass.HUMIDITY,
    "Pa": SensorDeviceClass.PRESSURE,
    "hPa": SensorDeviceClass.ATMOSPHERIC_PRESSURE,
    "mbar": SensorDeviceClass.ATMOSPHERIC_PRESSURE,
    "bar": SensorDeviceClass.PRESSURE,
    "lx": SensorDeviceClass.ILLUMINANCE,
    "Hz": SensorDeviceClass.FREQUENCY,
    "ppm": SensorDeviceClass.CO2,
    "ppb": SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS,
    "dB": SensorDeviceClass.SOUND_PRESSURE,
    "m^3": SensorDeviceClass.WATER,
    "var": SensorDeviceClass.REACTIVE_POWER,
    "VA": SensorDeviceClass.APPARENT_POWER,
    "kvarh": SensorDeviceClass.REACTIVE_ENERGY,
}

# Types that represent cumulative totals
_TOTAL_INCREASING_TYPES = {
    "power_consumption",
    "water_consumption",
    "heat_energy",
}

# Device classes that are always cumulative totals on WB devices.
# Needed for generic "value"/"range" controls, whose device_class comes
# from the unit rather than from the WB type.
_TOTAL_INCREASING_CLASSES = {
    SensorDeviceClass.ENERGY,
    SensorDeviceClass.REACTIVE_ENERGY,
    SensorDeviceClass.WATER,
}

# Default units for deprecated WB types that imply a specific unit
# Used when the meta doesn't include an explicit "units" field
_DEFAULT_UNIT_BY_TYPE = {
    "temperature": "°C",
    "rel_humidity": "%",
    "power": "W",
    "power_consumption": "kWh",
    "voltage": "V",
    "current": "A",
    "lux": "lx",
    "ppm": "ppm",
    "ppb": "ppb",
    "concentration": "ppm",
    "sound_level": "dB",
    "atmospheric_pressure": "mbar",
    "pressure": "Pa",
    "water_consumption": "m^3",
    "heat_energy": "kWh",
    "heat_power": "W",
    "wind_speed": "m/s",
    "water_flow": "m^3/h",
    "resistance": "Ohm",
}

# WB unit -> HA native unit
_UNIT_MAPPING = {
    "°C": UnitOfTemperature.CELSIUS,
    "C": UnitOfTemperature.CELSIUS,
    "deg C": UnitOfTemperature.CELSIUS,
    "%": PERCENTAGE,
    "%, RH": PERCENTAGE,
    "RH": PERCENTAGE,
    "hPa": UnitOfPressure.HPA,
    "Pa": UnitOfPressure.PA,
    "mbar": UnitOfPressure.MBAR,
    "bar": UnitOfPressure.BAR,
    "V": UnitOfElectricPotential.VOLT,
    "mV": UnitOfElectricPotential.MILLIVOLT,
    "A": UnitOfElectricCurrent.AMPERE,
    "mA": UnitOfElectricCurrent.MILLIAMPERE,
    "W": UnitOfPower.WATT,
    "kW": UnitOfPower.KILO_WATT,
    "kWh": UnitOfEnergy.KILO_WATT_HOUR,
    "Wh": UnitOfEnergy.WATT_HOUR,
    "lx": UnitOfIlluminance.LUX,
    "lux": UnitOfIlluminance.LUX,
    "ppb": CONCENTRATION_PARTS_PER_BILLION,
    "ppm": CONCENTRATION_PARTS_PER_MILLION,
    "dB": UnitOfSoundPressure.DECIBEL,
    "Hz": UnitOfFrequency.HERTZ,
    "m/s": UnitOfSpeed.METERS_PER_SECOND,
    "m^3/h": UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
    "m^3": UnitOfVolume.CUBIC_METERS,
    "var": UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
    "VA": UnitOfApparentPower.VOLT_AMPERE,
    "kvarh": UnitOfReactiveEnergy.KILO_VOLT_AMPERE_REACTIVE_HOUR,
}


class WirenBoardSensor(WirenBoardEntity, SensorEntity):
    """Representation of a Wiren Board sensor."""

    def __init__(self, device_info, mqtt_client):
        """Initialize sensor."""
        super().__init__(device_info, mqtt_client)

        device_type = device_info.get("device_type", "")
        unit = device_info.get("unit", "")

        # If no explicit unit from meta, use default for deprecated WB types
        if not unit:
            unit = _DEFAULT_UNIT_BY_TYPE.get(device_type, "")

        # Set device_class from device_type, fallback to unit
        self._attr_device_class = _DEVICE_CLASS_BY_TYPE.get(device_type)
        if self._attr_device_class is None and unit:
            self._attr_device_class = _DEVICE_CLASS_BY_UNIT.get(unit)

        # Set state_class
        if (
            device_type in _TOTAL_INCREASING_TYPES
            or self._attr_device_class in _TOTAL_INCREASING_CLASSES
        ):
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif self._attr_device_class is not None:
            self._attr_state_class = SensorStateClass.MEASUREMENT

        # Set native unit
        if unit:
            mapped_unit = _UNIT_MAPPING.get(unit)
            if mapped_unit:
                self._attr_native_unit_of_measurement = mapped_unit
            else:
                self._attr_native_unit_of_measurement = unit

    def _handle_state_update(self, payload: str):
        """Handle state update for sensor."""
        try:
            self._state = float(payload) if payload else None
        except (ValueError, TypeError):
            self._state = payload

    @property
    def native_value(self):
        """Return the current sensor value."""
        return self._state
