"""Number entity for Wiren Board."""

import logging

from homeassistant.components.number import NumberEntity, NumberMode

from ..const import TOPIC_COMMAND
from .base import WirenBoardEntity

logger = logging.getLogger(__name__)


class WirenBoardNumber(WirenBoardEntity, NumberEntity):
    """Representation of a Wiren Board number."""

    def __init__(self, device_info, mqtt_client):
        value = device_info.get("min", "0")
        if value:
            self._attr_native_min_value = int(value)
        else:
            self._attr_native_min_value = 0
        value = device_info.get("max", "100")
        if value:
            self._attr_native_max_value = int(value)
        else:
            self._attr_native_max_value = 100
        self._attr_mode = NumberMode.SLIDER
        super().__init__(device_info, mqtt_client)

    @property
    def value(self):
        """Return the current value."""
        try:
            return float(self._state) if self._state else 0.0
        except (ValueError, TypeError):
            return 0.0

    @property
    def min_value(self):
        """Return the minimum value."""
        logger.warning(f"self._device_info {self._device_info}")
        _min = self._device_info.get("min")
        if _min is None:
            _min = 0
        return float(_min)

    @property
    def max_value(self):
        """Return the maximum value."""
        _max = self._device_info.get("max")
        if _max is None:
            _max = 100
        return float(_max)

    async def async_set_value(self, value: float):
        """Set new value."""
        if self._device_info.get("readonly"):
            logger.warning("Device %s is read-only", self.unique_id)
            return
        # send to mqtt value
        command_topic = TOPIC_COMMAND.format(
            device=self.device_id, control=self.control_id
        )
        await self.mqtt_client.publish(command_topic, str(value), False)

    def set_native_value(self, value):
        """Set new native value."""
        self.native_value = value
        # send to mqtt value
        command_topic = TOPIC_COMMAND.format(
            device=self.device_id, control=self.control_id
        )
        self.mqtt_client.publish_sync(command_topic, str(value), False)
