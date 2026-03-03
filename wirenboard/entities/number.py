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
        if (
            device_info["device_id"] == "buzzer"
            and device_info["control_id"] == "frequency"
        ):
            self._attr_native_min_value = 0
            self._attr_native_max_value = 7000
        self._attr_mode = NumberMode.SLIDER
        super().__init__(device_info, mqtt_client)

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        if self._state is None:
            return None
        try:
            return float(self._state)
        except (ValueError, TypeError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if self._device_info.get("readonly"):
            logger.warning("Device %s is read-only", self.unique_id)
            return
        command_topic = TOPIC_COMMAND.format(
            device=self.device_id, control=self.control_id
        )
        await self.mqtt_client.publish(command_topic, str(value), False)
