"""Text entity for Wiren Board."""

import logging

from homeassistant.components.text import TextEntity

from ..const import TOPIC_COMMAND
from .base import WirenBoardEntity

logger = logging.getLogger(__name__)


class WirenBoardText(WirenBoardEntity, TextEntity):
    """Representation of a Wiren Board text entity."""

    @property
    def native_value(self) -> str:
        """Return the current value."""
        return self._state or ""

    @property
    def native_min(self) -> int:
        """Return the minimum length."""
        return 0

    @property
    def native_max(self) -> int:
        """Return the maximum length."""
        return 255

    async def async_set_value(self, value: str):
        """Set new value."""
        if self._device_info.get("readonly"):
            logger.warning("Device %s is read-only", self.unique_id)
            return

        command_topic = TOPIC_COMMAND.format(
            device=self.device_id, control=self.control_id
        )
        await self.mqtt_client.publish(command_topic, value, False)
