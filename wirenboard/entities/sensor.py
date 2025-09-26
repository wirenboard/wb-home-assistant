"""Sensor entity for Wiren Board."""

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfPressure, UnitOfTemperature

from .base import WirenBoardEntity

logger = logging.getLogger(__name__)


class WirenBoardSensor(WirenBoardEntity, SensorEntity):
    """Representation of a Wiren Board sensor."""

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
            logger.info(f"unit of measurement: {unit}")
            unit_mapping = {
                "°C": UnitOfTemperature.CELSIUS,
                "%": PERCENTAGE,
                "hPa": UnitOfPressure.HPA,
                "Pa": UnitOfPressure.PA,
                "V": "V",
                "A": "A",
                "W": "W",
                "kW": "kW",
                "kWh": "kWh",
                "lux": "lx",
            }
            return unit_mapping.get(unit, unit)
        return None
