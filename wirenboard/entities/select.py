"""Select entity for Wiren Board."""

import logging
from typing import Any

from homeassistant.components.select import SelectEntity

from ..const import TOPIC_COMMAND
from .base import WirenBoardEntity

logger = logging.getLogger(__name__)


class WirenBoardSelect(WirenBoardEntity, SelectEntity):
    """Representation of a Wiren Board select entity (enum control)."""

    def _handle_state_update(self, payload: str):
        """Handle state update for select."""
        logger.info("📨 SELECT state update for %s: %s", self.unique_id, payload)
        self._state = payload

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        options = self.options

        # If no options, return None
        if not options:
            return None

        # If state is empty/None, use first option as default
        if not self._state or self._state.strip() == "":
            logger.debug("Empty state for %s, using first option: %s", self.unique_id, options[0])
            return options[0]

        # Ensure the state is one of the valid options
        if self._state not in options:
            logger.warning(
                "Current state '%s' not in options %s for %s, using first option",
                self._state,
                options,
                self.unique_id,
            )
            # Return first option if current state is invalid
            return options[0]

        return self._state

    @property
    def options(self) -> list[str]:
        """Return the list of available options."""
        return self._device_info.get("enum", [])

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if self._device_info.get("readonly"):
            logger.warning("Device %s is read-only", self.unique_id)
            return

        command_topic = TOPIC_COMMAND.format(
            device=self.device_id, control=self.control_id
        )

        logger.debug("Publishing command to %s: %s", command_topic, option)
        await self.mqtt_client.publish(command_topic, option, False)
