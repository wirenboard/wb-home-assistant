"""Sensor entity for Wiren Board."""

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
)

from .base import WirenBoardEntity

logger = logging.getLogger(__name__)


class WirenBoardSensor(WirenBoardEntity, SensorEntity):
    """Representation of a Wiren Board sensor."""

    def __init__(self, device_info, mqtt_client):
        """Initialize sensor."""
        super().__init__(device_info, mqtt_client)

    def _handle_state_update(self, payload: str):
        """Handle state update for sensor."""
        try:
            # Пробуем преобразовать в число, если это числовой сенсор
            if self._device_info.get("device_type") == "value":
                self._state = float(payload) if payload else 0.0
            else:
                self._state = payload
        except (ValueError, TypeError):
            self._state = payload

    @property
    def native_value(self):
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        unit = self._device_info.get("unit")
        if unit:
            unit_mapping = {
                "°C": UnitOfTemperature.CELSIUS,
                "C": UnitOfTemperature.CELSIUS,
                "deg C": UnitOfTemperature.CELSIUS,
                "%": PERCENTAGE,
                "% RH": PERCENTAGE,
                "RH": PERCENTAGE,
                "hPa": UnitOfPressure.HPA,
                "Pa": UnitOfPressure.PA,
                "V": "V",
                "A": "A",
                "W": "W",
                "kW": "kW",
                "kWh": "kWh",
                "lux": "lx",
                "ppb": CONCENTRATION_PARTS_PER_BILLION,
                "ppm": CONCENTRATION_PARTS_PER_MILLION,
            }
            mapped = unit_mapping.get(unit, unit)
            if mapped != unit:
                logger.debug(
                    "Unit mapped for %s: '%s' -> '%s'",
                    self.unique_id,
                    unit,
                    mapped,
                )
            return mapped
        return None
