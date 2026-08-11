"""Button entity for Wiren Board."""

import logging

from homeassistant.components.button import ButtonEntity

from ..const import TOPIC_COMMAND
from .base import WirenBoardEntity

logger = logging.getLogger(__name__)


class WirenBoardButton(WirenBoardEntity, ButtonEntity):
    """Representation of a Wiren Board button."""

    def __init__(self, device_info, mqtt_client):
        super().__init__(device_info, mqtt_client)
        # pushbutton has no state topic — treat as available unless meta/error arrives
        self._available = True

    async def async_press(self, **kwargs):
        """Handle the button press."""
        if self._device_info.get("readonly"):
            logger.warning("Device %s is read-only", self.unique_id)
            return

        command_topic = TOPIC_COMMAND.format(
            device=self.device_id, control=self.control_id
        )
        await self.mqtt_client.publish(command_topic, "1", False)
