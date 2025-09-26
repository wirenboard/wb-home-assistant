"""Light entity for Wiren Board."""

import logging

from homeassistant.components.light import LightEntity

from ..const import TOPIC_COMMAND
from .base import WirenBoardEntity

logger = logging.getLogger(__name__)


class WirenBoardLight(WirenBoardEntity, LightEntity):
    """Representation of a Wiren Board light."""

    @property
    def is_on(self) -> bool:
        return self._state == "1"

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        await self._publish_command("1")

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self._publish_command("0")

    async def _publish_command(self, payload: str):
        """Publish command to MQTT."""
        if self._device_info.get("readonly"):
            logger.warning("Device %s is read-only", self.unique_id)
            return

        command_topic = TOPIC_COMMAND.format(
            device=self.device_id, control=self.control_id
        )
        await self.mqtt_client.publish(command_topic, payload, False)
