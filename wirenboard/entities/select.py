"""SELECT entity for Wiren Board enum controls."""

import json
import logging
from typing import Any, Dict

from homeassistant.components.select import SelectEntity
from homeassistant.core import callback

from ..const import TOPIC_COMMAND
from ..mqtt_client import WirenBoardMqttClient
from .base import WirenBoardEntity

logger = logging.getLogger(__name__)


class WirenBoardSelect(WirenBoardEntity, SelectEntity):
    """SELECT entity for Wiren Board enum controls."""

    _attr_icon = "mdi:list-box"

    def __init__(
        self, device_info: Dict[str, Any], mqtt_client: WirenBoardMqttClient
    ) -> None:
        """Initialize the SELECT entity."""
        super().__init__(device_info, mqtt_client)
        self._attr_options = device_info.get("enum") or []
        self._enum_data = None

        # Try to parse enum data from control meta
        if self._attr_options:
            logger.debug("SELECT entity initialized with options: %s", self._attr_options)

    @property
    def current_option(self) -> str | None:
        """Return the selected option."""
        if not self._state:
            return self._attr_options[0] if self._attr_options else None

        # Validate state is a valid option
        if self._state in self._attr_options:
            return self._state

        # Return first option if state is invalid
        return self._attr_options[0] if self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if option not in self._attr_options:
            logger.warning(
                "Invalid option %s for %s, valid options: %s",
                option,
                self.unique_id,
                self._attr_options,
            )
            return

        command_topic = TOPIC_COMMAND.format(
            device=self.device_id, control=self.control_id
        )

        try:
            await self.mqtt_client.async_publish(command_topic, option)
            logger.info(
                "Published command to %s: %s", command_topic, option
            )
        except Exception as ex:
            logger.error(
                "Failed to publish command for %s: %s", self.unique_id, ex
            )
