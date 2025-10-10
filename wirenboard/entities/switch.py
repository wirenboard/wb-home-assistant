"""Switch entity for Wiren Board."""

import logging

from homeassistant.components.switch import SwitchEntity

from ..const import TOPIC_COMMAND
from .base import WirenBoardEntity

logger = logging.getLogger(__name__)


class WirenBoardSwitch(WirenBoardEntity, SwitchEntity):
    """Representation of a Wiren Board switch."""

    def _handle_state_update(self, payload: str):
        """Handle state update for switch."""
        # Для switch ожидаем "0" или "1"
        self._state = payload

    @property
    def is_on(self) -> bool:
        """Get state button."""
        return self._state == "1"

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self._publish_command("1")

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self._publish_command("0")

    async def _publish_command(self, payload: str):
        """Publish command to MQTT."""
        if self._device_info.get("readonly"):
            logger.warning("Device %s is read-only", self.unique_id)
            return

        command_topic = TOPIC_COMMAND.format(
            device=self.device_id, control=self.control_id
        )

        logger.debug("Publishing command to %s: %s", command_topic, payload)
        await self.mqtt_client.publish(command_topic, payload, False)
